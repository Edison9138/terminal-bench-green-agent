"""
Kickoff script to send terminal-bench evaluation request to green agent.
"""

import asyncio
import json
from src.utils.a2a_client import send_message_to_agent


# Configuration for terminal-bench evaluation
task_config = {
    # Use local dataset path instead of downloading from registry
    "dataset_path": "../terminal-bench/tasks",
    "task_ids": [
        "accelerate-maximal-square",
        "acl-permissions-inheritance",
    ],  # Specify which tasks to run
    "white_agent_url": "http://localhost:8001",  # URL of agent being evaluated
    "n_attempts": 1,
    "n_concurrent_trials": 1,
    "timeout_multiplier": 1.0,
}

kick_off_message = f"""
Launch terminal-bench evaluation to assess the tool-calling ability of the agent located at {task_config['white_agent_url']}.

You should use the following configuration:
<task_config>
{json.dumps(task_config, indent=2)}
</task_config>

Please run the terminal-bench harness with this configuration and report back the results including:
- Number of tasks attempted
- Number of tasks resolved
- Accuracy
- Failure modes for each task
"""


async def main():
    green_agent_url = "http://localhost:9999"

    print(f"Sending evaluation request to green agent at {green_agent_url}...")
    print(f"White agent being evaluated: {task_config['white_agent_url']}")
    print(f"Tasks to run: {task_config['task_ids']}")

    response = await send_message_to_agent(kick_off_message, green_agent_url)

    print("\n" + "=" * 80)
    print("GREEN AGENT RESPONSE:")
    print("=" * 80)
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
