"""
Green Agent for evaluating other agents on terminal-bench.
This agent receives evaluation requests via A2A protocol and runs terminal-bench harness.
"""

import json
import logging
import re
import tomllib
import uvicorn
from datetime import datetime
from pathlib import Path
from typing import Any

from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCard, Part, TextPart, TaskState
from a2a.utils import new_task, new_agent_text_message
from a2a.server.tasks import TaskUpdater

from terminal_bench.harness.harness import Harness
from terminal_bench.harness.models import BenchmarkResults

from src.config import settings

logger = logging.getLogger(__name__)


class TerminalBenchGreenAgentExecutor(AgentExecutor):
    """
    Executes terminal-bench evaluation when receiving requests via A2A.
    """

    def __init__(self):
        """Initialize the green agent executor."""
        self.evaluation_history = []
        logger.info("TerminalBenchGreenAgentExecutor initialized")

    def parse_task_config(self, user_input: str) -> dict[str, Any]:
        """
        Parse task configuration from user input.
        Extracts JSON config from <task_config> tags.
        """
        # Try to extract JSON from <task_config> tags
        match = re.search(r"<task_config>(.*?)</task_config>", user_input, re.DOTALL)
        if match:
            config_json = match.group(1).strip()
            return json.loads(config_json)

        # If no tags found, try to parse the entire message as JSON
        try:
            return json.loads(user_input)
        except json.JSONDecodeError:
            raise ValueError("Could not parse task configuration from user input")

    def run_terminal_bench_evaluation(self, config: dict[str, Any]) -> BenchmarkResults:
        """
        Run terminal-bench harness with the given configuration.

        Args:
            config: Dictionary containing evaluation configuration
                - dataset_path: Path to the local dataset
                - task_ids: List of task IDs to run
                - white_agent_url: URL of the agent being evaluated
                - n_attempts: Number of attempts per task
                - n_concurrent_trials: Number of concurrent trials
                - timeout_multiplier: Timeout multiplier

        Returns:
            BenchmarkResults object with evaluation results
        """
        logger.info(f"Starting terminal-bench evaluation with config: {config}")

        # Create output directory for this evaluation run
        run_id = f"green_agent_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_path = Path(settings.eval_output_path)
        output_path.mkdir(exist_ok=True)

        # Extract configuration (with defaults from settings)
        white_agent_url = config.get("white_agent_url", settings.white_agent_url)
        dataset_path = config.get("dataset_path", settings.dataset_path)
        dataset_name = config.get("dataset_name", settings.dataset_name)
        dataset_version = config.get("dataset_version", settings.dataset_version)
        task_ids = config.get("task_ids")
        n_attempts = config.get("n_attempts", settings.eval_n_attempts)
        n_concurrent_trials = config.get(
            "n_concurrent_trials", settings.eval_n_concurrent_trials
        )
        timeout_multiplier = config.get(
            "timeout_multiplier", settings.eval_timeout_multiplier
        )

        logger.info(f"Evaluating agent at: {white_agent_url}")
        if dataset_path:
            logger.info(f"Dataset path: {dataset_path}")
        else:
            logger.info(f"Dataset: {dataset_name} (version: {dataset_version})")
        logger.info(f"Task IDs: {task_ids}")

        # Create harness instance
        # Note: We use agent_import_path to specify our custom A2A agent adapter
        # Terminal-bench supports either dataset_path OR dataset_name/version
        harness_kwargs = {
            "output_path": output_path,
            "run_id": run_id,
            "agent_import_path": "src.adapters.a2a_white_agent:A2AWhiteAgent",
            "agent_kwargs": {"agent_url": white_agent_url},
            "task_ids": [str(tid) for tid in task_ids] if task_ids else None,
            "n_attempts": n_attempts,
            "n_concurrent_trials": n_concurrent_trials,
            "global_timeout_multiplier": timeout_multiplier,
            "cleanup": settings.eval_cleanup,
            "log_level": getattr(logging, settings.log_level),
        }

        # Add dataset configuration - either path or name/version
        if dataset_path:
            harness_kwargs["dataset_path"] = Path(dataset_path)
        else:
            harness_kwargs["dataset_name"] = dataset_name
            harness_kwargs["dataset_version"] = dataset_version

        harness = Harness(**harness_kwargs)

        # Run the evaluation
        logger.info("Running terminal-bench harness...")
        results = harness.run()

        logger.info(f"Evaluation complete. Accuracy: {results.accuracy:.2%}")
        logger.info(f"Results saved to: {output_path / run_id}")

        return results

    def format_results_message(
        self, results: BenchmarkResults, config: dict[str, Any]
    ) -> str:
        """Format evaluation results into a human-readable message."""

        message = f"""
Terminal-Bench Evaluation Results
=====================================

Agent Under Test: {config.get('white_agent_url', 'Unknown')}
Dataset: {config.get('dataset_name', 'terminal-bench')}
Tasks Evaluated: {len(results.results)}

Overall Performance:
- Accuracy: {results.accuracy:.2%}
- Resolved: {results.n_resolved}/{len(results.results)}
- Unresolved: {results.n_unresolved}/{len(results.results)}

"""

        if results.pass_at_k:
            message += "Pass@k Metrics:\n"
            for k, score in results.pass_at_k.items():
                if score is not None:
                    message += f"- Pass@{k}: {score:.2%}\n"
            message += "\n"

        # Add per-task results
        message += "Task Results:\n"
        message += "-" * 60 + "\n"

        for result in results.results:
            status = "✓ PASS" if result.is_resolved else "✗ FAIL"
            message += f"{status} - {result.task_id}\n"
            if not result.is_resolved and result.failure_mode:
                message += f"      Failure Mode: {result.failure_mode.value}\n"
            if result.total_input_tokens or result.total_output_tokens:
                message += f"      Tokens: {result.total_input_tokens or 0} in, {result.total_output_tokens or 0} out\n"

        message += "\n" + "=" * 60 + "\n"

        return message

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute the green agent - run terminal-bench evaluation.
        """
        logger.info("Green agent execute() called")

        # Create or get current task
        task = context.current_task
        if task is None:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        logger.info("Task created, sending initial status")

        # Set status to working
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(
                "Received evaluation request. Parsing configuration...",
                task.context_id,
                task.id,
            ),
        )

        logger.info("Initial status sent")

        try:
            # Parse task configuration from user input
            user_input = context.get_user_input()
            logger.info(f"Received user input: {user_input}")

            task_config = self.parse_task_config(user_input)
            logger.info(f"Parsed task config: {task_config}")

            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    f"Configuration parsed. Starting evaluation of agent at {task_config.get('white_agent_url')}...",
                    task.context_id,
                    task.id,
                ),
            )

            # Run terminal-bench evaluation
            results = self.run_terminal_bench_evaluation(task_config)

            # Store in history
            self.evaluation_history.append(
                {
                    "config": task_config,
                    "results": results,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Format results message
            results_message = self.format_results_message(results, task_config)

            # Send final response
            await updater.add_artifact(
                [Part(root=TextPart(text=results_message))],
                name="evaluation_results",
            )
            await updater.complete()

        except Exception as e:
            logger.error(f"Error during evaluation: {e}", exc_info=True)
            import traceback

            error_details = traceback.format_exc()
            logger.error(f"Full traceback:\n{error_details}")
            error_message = (
                f"Error during evaluation: {str(e)}\n\nTraceback:\n{error_details}"
            )

            try:
                await updater.add_artifact(
                    [Part(root=TextPart(text=error_message))],
                    name="error",
                )
                await updater.update_status(
                    TaskState.failed,
                    new_agent_text_message(error_message, task.context_id, task.id),
                )
                await updater.complete()
            except Exception as update_error:
                logger.error(f"Failed to send error update: {update_error}")

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


def main():
    """Main entry point for the green agent."""
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
    )

    # Validate configuration before starting
    try:
        settings.validate_required_settings()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your config.toml and .env files")
        raise SystemExit(1)

    logger.info(
        f"Starting Terminal-Bench Green Agent on {settings.green_agent_host}:{settings.green_agent_port}"
    )
    logger.info(f"Using agent card: {settings.green_agent_card_path}")

    # Create and run app
    app = create_green_agent_app(settings.green_agent_card_path)
    uvicorn.run(app, host=settings.green_agent_host, port=settings.green_agent_port)


if __name__ == "__main__":
    main()
