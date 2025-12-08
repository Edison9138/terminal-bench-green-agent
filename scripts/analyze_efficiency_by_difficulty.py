#!/usr/bin/env python3
"""
Analyze white agent efficiency metrics by task difficulty level.

Extracts timing and token usage statistics for easy/medium/hard tasks.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


# Task difficulty mapping (from config.toml)
TASK_DIFFICULTY_MAP = {
    # Easy tasks
    "count-dataset-tokens": "easy",
    "create-bucket": "easy",
    "csv-to-parquet": "easy",
    "extract-safely": "easy",
    "fix-permissions": "easy",
    "git-workflow-hack": "easy",
    "grid-pattern-transform": "easy",
    "hello-world": "easy",
    "modernize-fortran-build": "easy",
    "processing-pipeline": "easy",
    "security-vulhub-minio": "easy",
    "simple-web-scraper": "easy",
    # Medium tasks
    "blind-maze-explorer-algorithm": "medium",
    "blind-maze-explorer-algorithm.easy": "medium",
    "blind-maze-explorer-algorithm.hard": "medium",
    "build-initramfs-qemu": "medium",
    "build-linux-kernel-qemu": "medium",
    "build-tcc-qemu": "medium",
    "chess-best-move": "medium",
    "conda-env-conflict-resolution": "medium",
    "crack-7z-hash": "medium",
    "crack-7z-hash.easy": "medium",
    "crack-7z-hash.hard": "medium",
    "cron-broken-network": "medium",
    "decommissioning-service-with-sensitive-data": "medium",
    "download-youtube": "medium",
    "eval-mteb": "medium",
    "eval-mteb.hard": "medium",
    "fibonacci-server": "medium",
    "fix-git": "medium",
    "fix-pandas-version": "medium",
    "get-bitcoin-nodes": "medium",
    "heterogeneous-dates": "medium",
    "hf-model-inference": "medium",
    "incompatible-python-fasttext": "medium",
    "incompatible-python-fasttext.base_with_hint": "medium",
    "jupyter-notebook-server": "medium",
    "new-encrypt-command": "medium",
    "nginx-request-logging": "medium",
    "openssl-selfsigned-cert": "medium",
    "polyglot-c-py": "medium",
    "qemu-alpine-ssh": "medium",
    "qemu-startup": "medium",
    "raman-fitting": "medium",
    "raman-fitting.easy": "medium",
    "reshard-c4-data": "medium",
    "sanitize-git-repo": "medium",
    "sanitize-git-repo.hard": "medium",
    "simple-sheets-put": "medium",
    "solana-data": "medium",
    "sqlite-db-truncate": "medium",
    "sqlite-with-gcov": "medium",
    "swe-bench-fsspec": "medium",
    "swe-bench-langcodes": "medium",
    "tmux-advanced-workflow": "medium",
    "vim-terminal-task": "medium",
    # Hard tasks
    "blind-maze-explorer-5x5": "hard",
    "cartpole-rl-training": "hard",
    "configure-git-webserver": "hard",
    "extract-moves-from-video": "hard",
    "git-multibranch": "hard",
    "gpt2-codegolf": "hard",
    "intrusion-detection": "hard",
    "oom": "hard",
    "organization-json-generator": "hard",
    "password-recovery": "hard",
    "path-tracing": "hard",
    "path-tracing-reverse": "hard",
    "play-zork": "hard",
    "polyglot-rust-c": "hard",
    "prove-plus-comm": "hard",
    "pytorch-model-cli": "hard",
    "pytorch-model-cli.easy": "hard",
    "pytorch-model-cli.hard": "hard",
    "run-pdp11-code": "hard",
    "super-benchmark-upet": "hard",
    "swe-bench-astropy-1": "hard",
    "swe-bench-astropy-2": "hard",
    "train-fasttext": "hard",
    "write-compressor": "hard",
}


def parse_duration(start_str: Optional[str], end_str: Optional[str]) -> Optional[float]:
    """Calculate duration in seconds from ISO format timestamps."""
    if not start_str or not end_str:
        return None
    try:
        start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        return (end - start).total_seconds()
    except Exception:
        return None


def load_task_results(eval_dir: Path) -> List[Dict]:
    """Load all task results from evaluation directory."""
    tasks = []

    for task_dir in sorted(eval_dir.iterdir()):
        if not task_dir.is_dir():
            continue

        # Find results.json file
        results_files = list(task_dir.glob("*/results.json"))
        if not results_files:
            continue

        try:
            with open(results_files[0]) as f:
                data = json.load(f)

            task_name = task_dir.name
            difficulty = TASK_DIFFICULTY_MAP.get(task_name, "unknown")

            # Extract metrics
            is_resolved = data.get("is_resolved", False)
            input_tokens = data.get("total_input_tokens", 0)
            output_tokens = data.get("total_output_tokens", 0)
            total_tokens = input_tokens + output_tokens

            # Calculate agent execution time
            duration = parse_duration(
                data.get("agent_started_at"),
                data.get("agent_ended_at")
            )

            # Get test results
            parser_results = data.get("parser_results") or {}
            passed = sum(1 for v in parser_results.values() if v == "passed")
            total = len(parser_results)
            score = (passed / total * 100) if total > 0 else 0

            tasks.append({
                "name": task_name,
                "difficulty": difficulty,
                "resolved": is_resolved,
                "duration_seconds": duration,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "score": score,
            })
        except Exception as e:
            print(f"Warning: Error reading {task_name}: {e}", file=sys.stderr)
            continue

    return tasks


def calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calculate min, max, average for a list of values."""
    if not values:
        return {"min": 0, "max": 0, "avg": 0, "count": 0}

    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "count": len(values)
    }


def analyze_by_difficulty(tasks: List[Dict], resolved_only: bool = True) -> Dict:
    """Analyze timing and token metrics grouped by difficulty."""

    # Filter to resolved tasks if requested
    if resolved_only:
        tasks = [t for t in tasks if t["resolved"]]

    # Group by difficulty
    by_difficulty = {
        "easy": [],
        "medium": [],
        "hard": []
    }

    for task in tasks:
        difficulty = task["difficulty"]
        if difficulty in by_difficulty:
            by_difficulty[difficulty].append(task)

    # Calculate statistics for each difficulty
    results = {}

    for difficulty in ["easy", "medium", "hard"]:
        tasks_in_diff = by_difficulty[difficulty]

        # Extract times (filter out None values)
        times = [t["duration_seconds"] for t in tasks_in_diff if t["duration_seconds"] is not None]

        # Extract tokens
        tokens = [t["total_tokens"] for t in tasks_in_diff]

        results[difficulty] = {
            "time": calculate_stats(times),
            "tokens": calculate_stats(tokens),
            "tasks": tasks_in_diff
        }

    return results


def print_report(results: Dict, include_all: bool = False):
    """Print formatted efficiency report."""

    print("=" * 100)
    print("WHITE AGENT EFFICIENCY ANALYSIS BY DIFFICULTY LEVEL")
    print("=" * 100)
    print()

    for difficulty in ["easy", "medium", "hard"]:
        stats = results[difficulty]
        time_stats = stats["time"]
        token_stats = stats["tokens"]
        tasks = stats["tasks"]

        print(f"{difficulty.upper()} TASKS")
        print("-" * 100)
        print(f"  Resolved Tasks: {token_stats['count']}")
        print()

        if token_stats["count"] > 0:
            print(f"  TIME (seconds):")
            if time_stats["count"] > 0:
                print(f"    • Minimum:    {time_stats['min']:>10.1f}s")
                print(f"    • Maximum:    {time_stats['max']:>10.1f}s")
                print(f"    • Average:    {time_stats['avg']:>10.1f}s")
            else:
                print(f"    • No timing data available")
            print()

            print(f"  TOKENS:")
            print(f"    • Minimum:    {token_stats['min']:>10,.0f}")
            print(f"    • Maximum:    {token_stats['max']:>10,.0f}")
            print(f"    • Average:    {token_stats['avg']:>10,.0f}")
            print()

            if include_all:
                print(f"  TASK BREAKDOWN:")
                print(f"    {'Task Name':<45} {'Duration(s)':>12} {'Tokens':>15}")
                print(f"    {'-'*45} {'-'*12} {'-'*15}")
                for task in sorted(tasks, key=lambda x: x["total_tokens"]):
                    dur_str = f"{task['duration_seconds']:.1f}" if task['duration_seconds'] else "N/A"
                    print(f"    {task['name'][:44]:<45} {dur_str:>12} {task['total_tokens']:>15,}")
                print()
        else:
            print(f"  No resolved tasks in this difficulty level.")
            print()

        print()

    # Summary comparison
    print("=" * 100)
    print("SUMMARY COMPARISON")
    print("=" * 100)
    print()
    print(f"{'Difficulty':<12} {'Resolved':>10} {'Avg Time(s)':>15} {'Avg Tokens':>15}")
    print("-" * 100)
    for difficulty in ["easy", "medium", "hard"]:
        stats = results[difficulty]
        count = stats["tokens"]["count"]
        avg_time = stats["time"]["avg"] if stats["time"]["count"] > 0 else 0
        avg_tokens = stats["tokens"]["avg"]
        print(f"{difficulty.capitalize():<12} {count:>10} {avg_time:>15.1f} {avg_tokens:>15,.0f}")
    print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze white agent efficiency by difficulty level"
    )
    parser.add_argument(
        "eval_dir",
        type=Path,
        help="Path to evaluation results directory"
    )
    parser.add_argument(
        "--include-unresolved",
        action="store_true",
        help="Include unresolved tasks in analysis"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed task breakdown"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    if not args.eval_dir.exists():
        print(f"Error: Directory not found: {args.eval_dir}", file=sys.stderr)
        sys.exit(1)

    # Load task results
    tasks = load_task_results(args.eval_dir)

    if not tasks:
        print("Error: No task results found", file=sys.stderr)
        sys.exit(1)

    # Analyze by difficulty
    results = analyze_by_difficulty(tasks, resolved_only=not args.include_unresolved)

    # Output results
    if args.json:
        # JSON output for programmatic use
        json_output = {}
        for difficulty in ["easy", "medium", "hard"]:
            stats = results[difficulty]
            json_output[difficulty] = {
                "time": stats["time"],
                "tokens": stats["tokens"],
                "task_count": stats["tokens"]["count"]
            }
        print(json.dumps(json_output, indent=2))
    else:
        # Human-readable output
        print_report(results, include_all=args.detailed)


if __name__ == "__main__":
    main()
