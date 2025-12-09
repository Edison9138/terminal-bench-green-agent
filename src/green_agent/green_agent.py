"""
Green Agent for evaluating other agents on terminal-bench.
This agent receives evaluation requests via A2A protocol and runs terminal-bench harness.
"""

import asyncio
import json
import logging
import os
import re
import sys
import tomllib
import uvicorn
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCard
from a2a.utils import new_agent_text_message

from terminal_bench.harness.harness import Harness
from terminal_bench.harness.models import BenchmarkResults

from src.config import settings
from src.config.settings import ConfigurationError

logger = logging.getLogger(__name__)

# Thread pool for running blocking harness operations
_harness_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="harness")


def _print_to_stderr(message: str) -> None:
    """Print message to stderr with immediate flush for platform visibility."""
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


class TerminalBenchGreenAgentExecutor(AgentExecutor):
    """
    Executes terminal-bench evaluation when receiving requests via A2A.
    """

    def __init__(self):
        self.evaluation_history = []
        logger.info("TerminalBenchGreenAgentExecutor initialized")

    def parse_task_config(self, user_input: str) -> dict[str, Any]:
        """
        Parse task configuration from user input.
        Extracts JSON config from <task_config> tags.
        """
        match = re.search(r"<task_config>(.*?)</task_config>", user_input, re.DOTALL)
        if match:
            config_json = match.group(1).strip()
            return json.loads(config_json)
        try:
            return json.loads(user_input)
        except json.JSONDecodeError:
            raise ValueError("Could not parse task configuration from user input")

    def parse_white_agent_url(self, user_input: str) -> str | None:
        """
        Parse white agent URL from user input.
        Extracts URL from <white_agent_url> tags.
        """
        match = re.search(
            r"<white_agent_url>(.*?)</white_agent_url>", user_input, re.DOTALL
        )
        if match:
            url = match.group(1).strip()
            logger.info(f"Extracted white_agent_url from tags: {url}")
            return url
        logger.warning("No <white_agent_url> tag found in user input")
        return None

    def run_terminal_bench_evaluation(self, config: dict[str, Any]) -> BenchmarkResults:
        """
        Run terminal-bench harness with the given configuration.

        Args:
            config: Dictionary containing evaluation configuration
                - task_ids: List of task IDs to run
                - dataset_name: Name of the dataset to run
                - dataset_version: Version of the dataset to run
                - white_agent_url: URL of the agent being evaluated
                - n_attempts: Number of attempts per task
                - n_concurrent_trials: Number of concurrent trials
                - timeout_multiplier: Timeout multiplier
        """
        logger.info(f"Starting terminal-bench evaluation with config: {config}")

        # Create output directory for this evaluation run
        # Allow run_id to be provided for resuming incomplete runs
        run_id = (
            config.get("run_id")
            or f"green_agent_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        output_path = Path(settings.eval_output_path)
        output_path.mkdir(exist_ok=True)

        # Check if this is a resume operation
        run_path = output_path / run_id
        is_resuming = run_path.exists()
        if is_resuming:
            logger.info(f"RESUMING existing run: {run_id}")
            logger.info(
                f"Will skip completed tasks and continue with incomplete tasks only"
            )
        else:
            logger.info(f"Starting NEW run: {run_id}")

        # Extract configuration (all required, no fallbacks)
        white_agent_url = config.get("white_agent_url")
        dataset_name = config.get("dataset_name")
        dataset_version = config.get("dataset_version")
        task_ids = config.get("task_ids")
        n_attempts = config.get("n_attempts")
        n_concurrent_trials = config.get("n_concurrent_trials")
        timeout_multiplier = config.get("timeout_multiplier")

        # Log configuration
        logger.info(f"Evaluating agent at: {white_agent_url}")
        logger.info(f"Dataset: {dataset_name} (version: {dataset_version})")
        logger.info(f"Task IDs: {task_ids}")

        # Create harness instance
        harness_kwargs = {
            "output_path": output_path,
            "run_id": run_id,
            "dataset_name": dataset_name,
            "dataset_version": dataset_version,
            "agent_import_path": "src.adapters.a2a_adapter:A2AAdapter",
            "agent_kwargs": {"agent_url": white_agent_url},
            "task_ids": [str(tid) for tid in task_ids] if task_ids else None,
            "n_attempts": n_attempts,
            "n_concurrent_trials": n_concurrent_trials,
            "global_timeout_multiplier": timeout_multiplier,
            "cleanup": settings.eval_cleanup,
            "log_level": getattr(logging, settings.log_level),
        }

        logger.info("=" * 60)
        logger.info("STARTING TERMINAL-BENCH EVALUATION")
        logger.info("=" * 60)
        logger.info(f"Tasks to evaluate: {task_ids}")
        logger.info(f"Attempts per task: {n_attempts}")
        logger.info(f"Concurrent trials: {n_concurrent_trials}")
        logger.info(f"Output directory: {output_path / run_id}")
        logger.info("=" * 60)

        harness = Harness(**harness_kwargs)

        # Run the evaluation
        logger.info("Running terminal-bench harness...")
        results = harness.run()

        logger.info("=" * 60)
        logger.info("EVALUATION COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Evaluation complete. Accuracy: {results.accuracy:.2%}")
        logger.info(f"Results saved to: {output_path / run_id}")

        return results

    def _calculate_customized_scoring(self, results: BenchmarkResults) -> dict[str, Any]:
        """
        Calculate customized scoring metrics for terminal-bench results.
        This extracts the scoring logic to support both logging and message formatting.
        """
        # Load scoring configuration from settings
        TASK_DIFFICULTY_MAP = settings.task_difficulty_map
        DIFFICULTY_WEIGHTS = settings.difficulty_weights

        category_scores = {
            "easy": [],
            "medium": [],
            "hard": [],
            "unknown": [],
        }
        task_scores_list = []
        failure_mode_counts = {}

        base_output_dir = Path(settings.eval_output_path)

        for result in results.results:
            parser_results = {}
            task_id = result.task_id

            if not result.recording_path:
                logger.warning(
                    f"No recording_path for task {task_id}, cannot load parser_results."
                )
            else:
                try:
                    trial_dir = (
                        base_output_dir / Path(result.recording_path).parent.parent
                    )
                    results_json_path = trial_dir / "results.json"

                    if results_json_path.exists():
                        with open(results_json_path, "r") as f:
                            trial_data = json.load(f)

                        if "parser_results" in trial_data and isinstance(
                            trial_data["parser_results"], dict
                        ):
                            parser_results = trial_data["parser_results"]
                        else:
                            logger.warning(
                                f"No 'parser_results' dict found in {results_json_path}"
                            )
                    else:
                        logger.warning(f"results.json not found at {results_json_path}")
                except Exception as e:
                    logger.error(
                        f"Error loading {results_json_path} for task {task_id}: {e}",
                        exc_info=True,
                    )

            num_tests = 0
            num_passed = 0
            test_case_score_component = 0.0

            if parser_results:
                num_tests = len(parser_results)
                if num_tests > 0:
                    num_passed = sum(
                        1 for status in parser_results.values() if status == "passed"
                    )
                    test_case_score_component = 0.5 * (num_passed / num_tests)

            resolved_score_component = 0.5 if result.is_resolved else 0.0
            task_score = test_case_score_component + resolved_score_component

            difficulty = TASK_DIFFICULTY_MAP.get(task_id, "unknown")
            category_scores[difficulty].append(task_score)

            if not result.is_resolved:
                failure_mode = result.failure_mode
                failure_mode_key = "unknown"
                if failure_mode:
                    failure_mode_key = (
                        failure_mode.value
                        if hasattr(failure_mode, "value")
                        else str(failure_mode)
                    )

                if failure_mode_key == "unset":
                    failure_mode_key = "other (unset)"

                failure_mode_counts[failure_mode_key] = (
                    failure_mode_counts.get(failure_mode_key, 0) + 1
                )

            task_scores_list.append(
                {
                    "id": task_id,
                    "score": task_score,
                    "is_resolved": result.is_resolved,
                    "tests_passed": num_passed,
                    "tests_total": num_tests,
                    "failure_mode": result.failure_mode,
                    "total_input_tokens": result.total_input_tokens,
                    "total_output_tokens": result.total_output_tokens,
                }
            )

        avg = lambda scores: (
            (sum(scores) / len(scores), len(scores)) if scores else (0.0, 0)
        )

        easy_avg, easy_count = avg(category_scores["easy"])
        medium_avg, medium_count = avg(category_scores["medium"])
        hard_avg, hard_count = avg(category_scores["hard"])
        unknown_avg, unknown_count = avg(category_scores["unknown"])

        total_weighted_score = (
            (sum(category_scores["easy"]) * DIFFICULTY_WEIGHTS["easy"])
            + (sum(category_scores["medium"]) * DIFFICULTY_WEIGHTS["medium"])
            + (sum(category_scores["hard"]) * DIFFICULTY_WEIGHTS["hard"])
            + (sum(category_scores["unknown"]) * DIFFICULTY_WEIGHTS["unknown"])
        )

        total_possible_weight = (
            (easy_count * DIFFICULTY_WEIGHTS["easy"])
            + (medium_count * DIFFICULTY_WEIGHTS["medium"])
            + (hard_count * DIFFICULTY_WEIGHTS["hard"])
            + (unknown_count * DIFFICULTY_WEIGHTS["unknown"])
        )

        if total_possible_weight == 0:
            weighted_overall_avg = 0.0
        else:
            weighted_overall_avg = total_weighted_score / total_possible_weight

        overall_count = easy_count + medium_count + hard_count + unknown_count
        n_resolved = sum(1 for task in task_scores_list if task["is_resolved"])
        n_unresolved = overall_count - n_resolved

        return {
            "weighted_overall_avg": weighted_overall_avg,
            "n_resolved": n_resolved,
            "n_unresolved": n_unresolved,
            "overall_count": overall_count,
            "easy_avg": easy_avg,
            "easy_count": easy_count,
            "medium_avg": medium_avg,
            "medium_count": medium_count,
            "hard_avg": hard_avg,
            "hard_count": hard_count,
            "unknown_avg": unknown_avg,
            "unknown_count": unknown_count,
            "failure_mode_counts": failure_mode_counts,
            "task_scores_list": task_scores_list,
            "category_scores": category_scores,
        }

    def format_results_message(
        self, results: BenchmarkResults, config: dict[str, Any]
    ) -> str:
        """Format evaluation results into a human-readable message."""
        # Use the centralized scoring calculation
        scoring = self._calculate_customized_scoring(results)

        # Extract values for readability
        weighted_overall_avg = scoring["weighted_overall_avg"]
        n_resolved = scoring["n_resolved"]
        n_unresolved = scoring["n_unresolved"]
        overall_count = scoring["overall_count"]
        easy_avg = scoring["easy_avg"]
        easy_count = scoring["easy_count"]
        medium_avg = scoring["medium_avg"]
        medium_count = scoring["medium_count"]
        hard_avg = scoring["hard_avg"]
        hard_count = scoring["hard_count"]
        unknown_avg = scoring["unknown_avg"]
        unknown_count = scoring["unknown_count"]
        failure_mode_counts = scoring["failure_mode_counts"]
        task_scores_list = scoring["task_scores_list"]

        # Build failure summary in markdown
        failure_summary_message = ""
        if failure_mode_counts:
            failure_summary_message = "\n### Failure Mode Summary\n\n"
            sorted_failures = sorted(
                failure_mode_counts.items(), key=lambda item: item[1], reverse=True
            )
            for mode, count in sorted_failures:
                failure_summary_message += f"- **{mode}**: {count}\n"

        # Build markdown-formatted message
        message = f"""# Terminal-Bench Evaluation Results

**Weighting**: Easy=1, Medium=2, Hard=3
## Evaluation Summary

- **Overall Score**: `{weighted_overall_avg:.2%}`
- **Resolved**: `{n_resolved}/{overall_count}`
- **Unresolved**: `{n_unresolved}/{overall_count}`

## Scores by Difficulty (Unweighted Average)

| Difficulty | Average Score | Count |
|------------|---------------|-------|
| Easy       | `{easy_avg:.2%}` | {easy_count} |
| Medium     | `{medium_avg:.2%}` | {medium_count} |
| Hard       | `{hard_avg:.2%}` | {hard_count} |"""

        if unknown_count > 0:
            message += f"\n| Unknown     | `{unknown_avg:.2%}` | {unknown_count} | *Task ID not in TASK_DIFFICULTY_MAP* |"
        message += failure_summary_message

        if results.pass_at_k:
            message += "\n### Pass@k Metrics (based on is_resolved)\n\n"
            for k, score in results.pass_at_k.items():
                if score is not None:
                    message += f"- **Pass@{k}**: `{score:.2%}`\n"
            message += "\n"

        # Add per-task results in markdown table
        message += "\n## Task Results\n\n"
        message += "| Status | Score | Task ID | Tests Passed | Failure Mode | Tokens (in/out) |\n"
        message += "|--------|-------|---------|--------------|--------------|-----------------|\n"

        for task in task_scores_list:
            status = "✅" if task["is_resolved"] else "❌"
            failure_mode_val = ""
            if not task["is_resolved"] and task["failure_mode"]:
                failure_mode_val = (
                    task["failure_mode"].value
                    if hasattr(task["failure_mode"], "value")
                    else str(task["failure_mode"])
                )
                if failure_mode_val == "unset":
                    failure_mode_val = "other (unset)"
            tokens_str = f"{task['total_input_tokens'] or 0} / {task['total_output_tokens'] or 0}"

            message += f"| {status} | `{task['score']:.2%}` | `{task['id']}` | {task['tests_passed']}/{task['tests_total']} | {failure_mode_val or '-'} | {tokens_str} |\n"

        return message

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute the green agent - run terminal-bench evaluation.
        Runs evaluation synchronously and returns a Message with results.

        This approach matches how the chess-bench green agent works:
        - Run evaluation synchronously (blocking the HTTP request)
        - Return a Message object (not a Task) when complete
        - Platform interprets Message as "done" vs Task(working) as "still processing"

        Requires Cloudflare proxy timeout to be extended or disabled.
        """
        logger.info("Green agent execute() called")

        try:
            # Parse configuration
            agent_url = os.getenv("AGENT_URL")
            if agent_url:
                # Use Agentbeats to run eval
                task_config = {
                    "task_ids": settings.eval_task_ids,
                    "white_agent_url": self.parse_white_agent_url(
                        context.get_user_input()
                    ),
                    "n_attempts": settings.eval_n_attempts,
                    "n_concurrent_trials": settings.eval_n_concurrent_trials,
                    "timeout_multiplier": settings.eval_timeout_multiplier,
                    "dataset_name": settings.dataset_name,
                    "dataset_version": settings.dataset_version,
                }
            else:
                # Use kickoff script to run eval
                # Parse task configuration from user input
                user_input = context.get_user_input()
                logger.info(f"Received user input: {user_input}")
                task_config = self.parse_task_config(user_input)

            logger.info(f"Parsed task config: {task_config}")

            # Log start of evaluation
            _print_to_stderr("=" * 60)
            _print_to_stderr(f"STARTING EVALUATION - Running synchronously")
            _print_to_stderr(f"White agent URL: {task_config.get('white_agent_url')}")
            _print_to_stderr("=" * 60)

            # Run evaluation SYNCHRONOUSLY (blocking)
            # This keeps the HTTP connection open until evaluation completes
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                _harness_executor, self.run_terminal_bench_evaluation, task_config
            )

            # Store in history
            self.evaluation_history.append(
                {
                    "config": task_config,
                    "results": results,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Log results to stderr for platform visibility
            _print_to_stderr("=" * 60)
            _print_to_stderr("EVALUATION COMPLETED")
            _print_to_stderr("=" * 60)

            # Calculate and log scoring summary
            scoring_summary = self._calculate_customized_scoring(results)
            _print_to_stderr(f"Overall Score: {scoring_summary['weighted_overall_avg']:.2%}")
            _print_to_stderr(f"Resolved: {scoring_summary['n_resolved']}/{scoring_summary['overall_count']}")
            _print_to_stderr("=" * 60)

            # Format results message
            results_message = self.format_results_message(results, task_config)

            # Return a Message directly (not a Task)
            # This signals to the platform that the work is complete
            # Similar to how chess-bench returns: result=Message(...)
            await event_queue.enqueue_event(
                new_agent_text_message(
                    f"Finished. Results:\n\n{results_message}",
                    context.context_id,
                    None  # task_id=None indicates this is a direct response
                )
            )

            logger.info("Evaluation complete, Message response sent")

        except Exception as e:
            logger.error(f"Error during evaluation: {e}", exc_info=True)
            import traceback

            error_details = traceback.format_exc()
            logger.error(f"Full traceback:\n{error_details}")
            error_message = (
                f"Error during evaluation: {str(e)}\n\nTraceback:\n{error_details}"
            )

            # Return error as Message
            await event_queue.enqueue_event(
                new_agent_text_message(
                    f"Evaluation failed: {error_message}",
                    context.context_id,
                    None
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel the current evaluation (not implemented)."""
        raise NotImplementedError("cancel not supported")


def create_green_agent_app(agent_card_path: str) -> A2AStarletteApplication:
    """Create A2A application for the green agent."""

    # Load agent card
    with open(agent_card_path, "rb") as f:
        agent_card_data = tomllib.load(f)

    # Create A2A application
    app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_data),
        http_handler=DefaultRequestHandler(
            agent_executor=TerminalBenchGreenAgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()

    return app


def create_green_agent_app_from_dict(agent_card_data: dict) -> A2AStarletteApplication:
    """Create A2A application from agent card dictionary."""
    app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_data),
        http_handler=DefaultRequestHandler(
            agent_executor=TerminalBenchGreenAgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()
    return app


def main(host: str | None = None, port: int | None = None):
    """Main entry point for the green agent."""
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
    )

    # Ensure terminal_bench logs are visible
    logging.getLogger("terminal_bench").setLevel(logging.INFO)
    logging.getLogger("src").setLevel(logging.INFO)

    # Configuration is validated automatically when properties are accessed
    logger.info("Starting green agent with config from config.toml")

    # Use provided host/port or fall back to config
    agent_host = host if host is not None else settings.green_agent_host
    agent_port = port if port is not None else settings.green_agent_port

    logger.info(f"Starting Terminal-Bench Green Agent on {agent_host}:{agent_port}")
    logger.info(f"Using agent card: {settings.green_agent_card_path}")

    # Load agent card
    with open(settings.green_agent_card_path, "rb") as f:
        agent_card_data = tomllib.load(f)

    # Use AGENT_URL from environment if available (for AgentBeats)
    agent_url = os.getenv("AGENT_URL")
    if agent_url:
        agent_card_data["url"] = agent_url
        logger.info(f"Using AGENT_URL from environment: {agent_url}")

    # Create and run app
    app = create_green_agent_app_from_dict(agent_card_data)
    # Configure uvicorn with extended timeouts for long-running evaluations
    config = uvicorn.Config(
        app,
        host=settings.green_agent_host,
        port=settings.green_agent_port,
        timeout_keep_alive=3600,  # 1 hour keep-alive for long-running evaluations
        timeout_notify=3600,  # 1 hour notify timeout
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
