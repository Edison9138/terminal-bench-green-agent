#!/usr/bin/env python3
"""Check the status of an evaluation run to see which tasks are completed."""

import json
import sys
from pathlib import Path


def check_run_status(run_id: str, eval_results_dir: str = "./eval_results"):
    """Check which tasks are completed in a run."""
    run_path = Path(eval_results_dir) / run_id

    if not run_path.exists():
        print(f"❌ Run directory not found: {run_path}")
        sys.exit(1)

    # Load main results.json
    results_json_path = run_path / "results.json"
    if not results_json_path.exists():
        print(f"❌ results.json not found in {run_path}")
        sys.exit(1)

    with open(results_json_path) as f:
        results = json.load(f)

    # Load tb.lock to get full task list
    lock_path = run_path / "tb.lock"
    all_task_ids = []
    if lock_path.exists():
        with open(lock_path) as f:
            lock_data = json.load(f)
            all_task_ids = lock_data.get("dataset", {}).get("task_ids", [])

    completed_tasks = set()
    failed_tasks = []

    # Check completed tasks from results
    for result in results.get("results", []):
        task_id = result["task_id"]
        completed_tasks.add(task_id)
        if not result.get("is_resolved", False):
            failed_tasks.append({
                "id": task_id,
                "failure_mode": result.get("failure_mode", "unknown")
            })

    # Calculate incomplete tasks
    incomplete_tasks = [tid for tid in all_task_ids if tid not in completed_tasks]

    # Print summary
    print("=" * 80)
    print(f"Run Status: {run_id}")
    print("=" * 80)
    print(f"\nRun directory: {run_path}")
    print(f"\nTotal tasks in run: {len(all_task_ids)}")
    print(f"✅ Completed: {len(completed_tasks)}")
    print(f"⏳ Incomplete: {len(incomplete_tasks)}")
    print(f"❌ Failed (completed but not resolved): {len(failed_tasks)}")

    if results.get("accuracy") is not None:
        print(f"\nCurrent accuracy: {results['accuracy']:.2%}")

    # Show completed tasks
    if completed_tasks:
        print(f"\n✅ Completed Tasks ({len(completed_tasks)}):")
        for task_id in sorted(completed_tasks):
            print(f"   • {task_id}")

    # Show failed tasks
    if failed_tasks:
        print(f"\n❌ Failed Tasks ({len(failed_tasks)}):")
        for task in failed_tasks:
            print(f"   • {task['id']} (failure: {task['failure_mode']})")

    # Show incomplete tasks
    if incomplete_tasks:
        print(f"\n⏳ Incomplete Tasks ({len(incomplete_tasks)}):")
        for task_id in incomplete_tasks:
            print(f"   • {task_id}")
        print(f"\nTo resume this run, use: python -m src.kickoff_resume")
        print(f"(Make sure to set RESUME_RUN_ID = '{run_id}' in kickoff_resume.py)")
    else:
        print("\n🎉 All tasks completed!")

    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Try to find the most recent run
        eval_results = Path("./eval_results")
        if eval_results.exists():
            runs = sorted(
                [d for d in eval_results.iterdir() if d.is_dir()],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            if runs:
                print(f"No run_id provided. Checking most recent run...\n")
                check_run_status(runs[0].name)
            else:
                print("Usage: python scripts/check_run_status.py <run_id>")
                print("Example: python scripts/check_run_status.py green_agent_eval_20251206_124845")
                sys.exit(1)
        else:
            print("Usage: python scripts/check_run_status.py <run_id>")
            print("Example: python scripts/check_run_status.py green_agent_eval_20251206_124845")
            sys.exit(1)
    else:
        run_id = sys.argv[1]
        check_run_status(run_id)
