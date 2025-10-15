"""
Example White Agent for Testing

This is a simple white agent implementation that can be evaluated by the green agent.
It uses a basic LLM to respond to terminal-bench tasks.

This serves as a reference implementation for building your own white agents.
"""

import os
import tomllib
import uvicorn
from typing import List, Any

from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCard, Part, TextPart, TaskState
from a2a.utils import new_task, new_agent_text_message
from a2a.server.tasks import TaskUpdater


class SimpleWhiteAgentExecutor(AgentExecutor):
    """
    A simple white agent that responds to terminal-bench tasks.

    In a real implementation, this would:
    - Parse the task instruction
    - Use an LLM to generate a solution
    - Execute terminal commands via provided tools
    - Return the result
    """

    def __init__(self):
        """Initialize the white agent."""
        self.conversation_history = []

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute a task received from the green agent."""

        # Create or get current task
        task = context.current_task
        if task is None:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # Set status to working
        await updater.update_status(
            TaskState.working,
            new_agent_text_message("Processing task...", task.context_id, task.id),
        )

        # Get user input (task instruction from green agent)
        user_input = context.get_user_input()
        self.conversation_history.append({"role": "user", "content": user_input})

        # TODO: In a real implementation, you would:
        # 1. Parse the task instruction
        # 2. Call an LLM to generate a solution
        # 3. Execute terminal commands via tools
        # 4. Verify the solution

        # For this example, we just acknowledge receipt
        response = f"""
I received the following task:

{user_input}

This is a simple example white agent. In a real implementation, I would:
1. Analyze the task requirements
2. Generate a solution using an LLM
3. Execute the necessary terminal commands
4. Verify the results

To make this agent functional, you would need to:
- Integrate an LLM (OpenAI, Anthropic, etc.)
- Add terminal execution tools
- Implement task-specific logic
"""

        self.conversation_history.append({"role": "assistant", "content": response})

        # Send response
        await updater.add_artifact(
            [Part(root=TextPart(text=response))],
            name="response",
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel the current task (not implemented)."""
        raise NotImplementedError("cancel not supported")


def create_white_agent_app(agent_card_path: str) -> A2AStarletteApplication:
    """Create A2A application for the white agent."""

    # Load agent card
    with open(agent_card_path, "rb") as f:
        agent_card_data = tomllib.load(f)

    # Create A2A application
    app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_data),
        http_handler=DefaultRequestHandler(
            agent_executor=SimpleWhiteAgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()

    return app


def main():
    """Main entry point for the example white agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Example White Agent")
    parser.add_argument("--port", type=int, default=8001, help="Port to run on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument(
        "--card",
        type=str,
        default="example_white_agent_card.toml",
        help="Path to agent card",
    )

    args = parser.parse_args()

    print(f"Starting Example White Agent on {args.host}:{args.port}")
    print(f"Using agent card: {args.card}")
    print("\nThis is a simple example agent for testing.")
    print("Replace this with your actual agent implementation.\n")

    # Create and run app
    app = create_white_agent_app(args.card)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
