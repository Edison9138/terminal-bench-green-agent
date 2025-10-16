"""
Kickoff script to send terminal-bench evaluation request to green agent.
"""

import asyncio
import json
from src.utils.a2a_client import send_message_to_agent
from src.config.settings import settings


# Configuration for terminal-bench evaluation loaded from config.toml
task_config = {
    "dataset_path": settings.dataset_path,
    "task_ids": settings.eval_task_ids,
    "white_agent_url": settings.white_agent_url,
    "n_attempts": settings.eval_n_attempts,
    "n_concurrent_trials": settings.eval_n_concurrent_trials,
    "timeout_multiplier": settings.eval_timeout_multiplier,
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
