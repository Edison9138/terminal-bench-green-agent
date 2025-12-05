#!/usr/bin/env python3
"""
Post-process and print customized scoring metrics from a terminal-bench evaluation run.
This replicates the scoring logic from green_agent.py's format_results_message().

EXAMPLE USAGE: python -m scripts.print_eval_results eval_results/green_agent_eval_20251204_201512
"""

import json
import logging
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


def load_results(eval_dir: Path) -> dict[str, Any]:
    """Load results.json from evaluation directory."""
    results_path = eval_dir / "results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"results.json not found at {results_path}")

    with open(results_path, "r") as f:
        return json.load(f)


def load_run_metadata(eval_dir: Path) -> dict[str, Any]:
    """Load run_metadata.json from evaluation directory."""
    metadata_path = eval_dir / "run_metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"run_metadata.json not found at {metadata_path}")

    with open(metadata_path, "r") as f:
        return json.load(f)


def print_customized_results(eval_dir: Path) -> None:
    """
    Print customized scoring results for a terminal-bench evaluation.
    Replicates the logic from green_agent.py's format_results_message().
    """
    # Load results
    results_data = load_results(eval_dir)
    metadata = load_run_metadata(eval_dir)

    # Load scoring configuration from settings
    TASK_DIFFICULTY_MAP = settings.task_difficulty_map
    DIFFICULTY_WEIGHTS = settings.difficulty_weights

    # Initialize score tracking
    category_scores = {
        "easy": [],
        "medium": [],
        "hard": [],
        "unknown": [],
    }
    task_scores_list = []
    failure_mode_counts = {}

    # Process each result
    for result in results_data["results"]:
        task_id = result["task_id"]
        is_resolved = result["is_resolved"]
        failure_mode = result.get("failure_mode", "unset")

        # Load parser_results from individual trial directory
        parser_results = {}
        recording_path = result.get("recording_path")

        if recording_path:
            try:
                # recording_path is relative, like: green_agent_eval_20251204_201512/task-name/trial-name/sessions/agent.cast
                # Extract task and trial names (parts[1] and parts[2]), skipping the eval dir name (parts[0])
                # to avoid duplicating it when joining with eval_dir
                parts = Path(recording_path).parts
                task_name = parts[1]
                trial_name = parts[2]
                trial_results_path = eval_dir / task_name / trial_name / "results.json"

                if trial_results_path.exists():
                    with open(trial_results_path, "r") as f:
                        trial_data = json.load(f)

                    if "parser_results" in trial_data and isinstance(
                        trial_data["parser_results"], dict
                    ):
                        parser_results = trial_data["parser_results"]
                    else:
                        logger.warning(
                            f"No 'parser_results' dict found in {trial_results_path}"
                        )
                else:
                    logger.warning(f"results.json not found at {trial_results_path}")
            except Exception as e:
                logger.error(
                    f"Error loading {trial_results_path} for task {task_id}: {e}",
                    exc_info=True,
                )

        # Calculate test case score
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

        # Calculate total task score
        resolved_score_component = 0.5 if is_resolved else 0.0
        task_score = test_case_score_component + resolved_score_component

        # Categorize by difficulty
        difficulty = TASK_DIFFICULTY_MAP.get(task_id, "unknown")
        category_scores[difficulty].append(task_score)

        # Track failure modes
        if not is_resolved:
            failure_mode_key = failure_mode if failure_mode else "unknown"

            if failure_mode_key == "unset":
                failure_mode_key = "other (unset)"

            failure_mode_counts[failure_mode_key] = (
                failure_mode_counts.get(failure_mode_key, 0) + 1
            )

        # Store task score info
        task_scores_list.append(
            {
                "id": task_id,
                "score": task_score,
                "is_resolved": is_resolved,
                "tests_passed": num_passed,
                "tests_total": num_tests,
                "failure_mode": failure_mode,
                "total_input_tokens": result.get("total_input_tokens"),
                "total_output_tokens": result.get("total_output_tokens"),
            }
        )

    # Calculate category averages
    def avg(scores):
        return (sum(scores) / len(scores), len(scores)) if scores else (0.0, 0)

    easy_avg, easy_count = avg(category_scores["easy"])
    medium_avg, medium_count = avg(category_scores["medium"])
    hard_avg, hard_count = avg(category_scores["hard"])
    unknown_avg, unknown_count = avg(category_scores["unknown"])

    # Calculate weighted overall average
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

    # Calculate resolved/unresolved counts
    n_resolved = sum(1 for task in task_scores_list if task["is_resolved"])
    n_unresolved = overall_count - n_resolved

    # Format failure mode summary
    failure_summary_message = ""
    if failure_mode_counts:
        failure_summary_message = "\nFailure Mode Summary:\n"
        sorted_failures = sorted(
            failure_mode_counts.items(), key=lambda item: item[1], reverse=True
        )
        for mode, count in sorted_failures:
            failure_summary_message += f"- {mode}: {count}\n"

    # Print results
    message = f"""
Terminal-Bench Evaluation Results
=====================================
(Weighting: Easy=1, Medium=2, Hard=3)

Evaluation Summary:
- Overall Score: {weighted_overall_avg:.2%}
- Resolved: {n_resolved}/{overall_count}
- Unresolved: {n_unresolved}/{overall_count}

Scores by Difficulty (Unweighted Avg):
- Easy:   {easy_avg:.2%}
- Medium: {medium_avg:.2%}
- Hard:   {hard_avg:.2%}
"""

    if unknown_count > 0:
        message += f"- Unknown: {unknown_avg:.2%} ({unknown_count} tasks) -- *Task ID not in TASK_DIFFICULTY_MAP*\n"

    message += failure_summary_message

    # Add pass@k metrics if available
    pass_at_k = metadata.get("pass_at_k", {})
    if pass_at_k:
        message += "\nPass@k Metrics (based on is_resolved):\n"
        for k, score in pass_at_k.items():
            if score is not None:
                message += f"- Pass@{k}: {score:.2%}\n"
        message += "\n"

    # Add per-task results
    message += "Task Results:\n"
    message += "-" * 60 + "\n"

    for task in task_scores_list:
        status = "✓" if task["is_resolved"] else "✗"
        message += f"{status} Score: {task['score']:.2%} - {task['id']} (Tests: {task['tests_passed']}/{task['tests_total']})\n"

        if not task["is_resolved"] and task["failure_mode"]:
            failure_mode_val = task["failure_mode"]
            message += f"      Failure Mode: {failure_mode_val}\n"
        if task["total_input_tokens"] or task["total_output_tokens"]:
            message += f"      Tokens: {task['total_input_tokens'] or 0} in, {task['total_output_tokens'] or 0} out\n"

    message += "\n" + "=" * 60 + "\n"

    print(message)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Print customized scoring metrics from terminal-bench evaluation results"
    )
    parser.add_argument(
        "eval_dir",
        type=str,
        help="Path to evaluation directory (e.g., eval_results/green_agent_eval_20251204_201512)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: WARNING)",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    # Get evaluation directory
    eval_dir = Path(args.eval_dir)
    if not eval_dir.exists():
        print(f"Error: Evaluation directory not found: {eval_dir}")
        return 1

    # Print results
    try:
        print_customized_results(eval_dir)
        return 0
    except Exception as e:
        logger.error(f"Error processing results: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
