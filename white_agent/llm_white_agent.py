"""
LLM-Powered White Agent for Terminal-Bench

This white agent uses OpenAI's GPT models with function calling to solve terminal tasks.
It can execute bash commands and use the LLM to reason about tasks.
"""

import asyncio
import json
import logging
import tomllib
import uvicorn
from typing import Any

from openai import OpenAI

from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCard, Part, TextPart, TaskState
from a2a.utils import new_task, new_agent_text_message
from a2a.server.tasks import TaskUpdater

from src.config import settings


class LLMWhiteAgentExecutor(AgentExecutor):
    """
    LLM-powered white agent that uses OpenAI with function calling
    to solve terminal-bench tasks.
    """

    def __init__(self):
        """Initialize the LLM white agent."""
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.white_agent_model  # Get model from config
        self.conversation_history = []
        self.container_name = None  # Will be extracted from task instruction

        # Define tools for function calling
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "execute_bash_command",
                    "description": "Execute a bash command in the Docker container terminal and return the output. Use this to interact with the filesystem, run programs, or perform system operations in the container.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The bash command to execute in the container (e.g., 'ls -la', 'cat file.txt', 'echo \"text\" > file.txt')",
                            }
                        },
                        "required": ["command"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

    async def _execute_bash_command(self, command: str) -> dict[str, Any]:
        """
        Execute a bash command inside the Docker container and return the result.

        Args:
            command: The bash command to execute

        Returns:
            Dict with command, returncode, stdout, stderr
        """
        # Safety check
        blocked = set(settings.blocked_commands)
        first_token = command.split()[0] if command.split() else ""

        if first_token in blocked:
            return {
                "command": command,
                "returncode": 126,
                "stdout": "",
                "stderr": f"Command '{first_token}' is blocked for safety reasons.",
            }

        if not self.container_name:
            return {
                "command": command,
                "returncode": 1,
                "stdout": "",
                "stderr": "Error: Container name not set. Cannot execute command.",
            }

        try:
            # Execute command inside the Docker container using docker exec
            # Use -w to set working directory to /app
            docker_command = [
                "docker",
                "exec",
                "-w",
                "/app",  # Set working directory
                self.container_name,
                "bash",
                "-c",
                command,
            ]

            process = await asyncio.create_subprocess_exec(
                *docker_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await process.communicate()

            return {
                "command": command,
                "returncode": process.returncode,
                "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                "stderr": stderr_bytes.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {
                "command": command,
                "returncode": 1,
                "stdout": "",
                "stderr": f"Error executing command in container: {str(e)}",
            }

    async def _run_agent_loop(self, user_input: str) -> str:
        """
        Run the LLM agent loop with function calling.

        Args:
            user_input: The task instruction

        Returns:
            Final response from the agent

        Raises:
            ValueError: If container name cannot be extracted from task instruction
        """
        # Extract container name from user input
        import re

        container_match = re.search(r"The container name is: (.+)", user_input)
        if not container_match:
            raise ValueError(
                "Container name not found in task instruction. "
                "Cannot execute commands without container context. "
                "Expected format: 'The container name is: <container_name>'"
            )
        self.container_name = container_match.group(1).strip()

        # Initialize conversation
        messages = [
            {
                "role": "system",
                "content": """You are a helpful assistant being evaluated on the Terminal-Bench benchmark.

Your goal is to complete terminal tasks by executing bash commands using the execute_bash_command function.
All commands will be executed inside a Docker container at the /app directory.

Guidelines:
- Break down complex tasks into simple steps
- Execute one command at a time and check the result
- If a command fails, analyze the error and try a different approach
- Use standard bash commands (ls, cat, echo, mkdir, etc.)
- Remember that all file paths should be relative to /app or use absolute paths starting with /app
- When the task is complete, provide a clear summary
- Be concise but thorough in your responses

Remember: You're being evaluated on your ability to correctly complete the task!""",
            },
            {"role": "user", "content": user_input},
        ]

        iteration = 0

        while iteration < settings.agent_max_iterations:
            iteration += 1

            # Call the LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
            )

            assistant_message = response.choices[0].message

            # Add assistant's response to messages
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": (
                        [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in assistant_message.tool_calls
                        ]
                        if assistant_message.tool_calls
                        else None
                    ),
                }
            )

            # If no tool calls, we're done
            if not assistant_message.tool_calls:
                return assistant_message.content or "Task completed."

            # Execute tool calls
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                if function_name == "execute_bash_command":
                    command = function_args["command"]
                    result = await self._execute_bash_command(command)

                    # Format the result for the LLM
                    result_message = f"Command: {result['command']}\n"
                    result_message += f"Exit code: {result['returncode']}\n"
                    if result["stdout"]:
                        result_message += f"Output:\n{result['stdout']}"
                    if result["stderr"]:
                        result_message += f"Error:\n{result['stderr']}"

                    # Add tool result to messages
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_message,
                        }
                    )

        # If we hit max iterations, return what we have
        return "Task execution completed (reached iteration limit)."

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute a task using the LLM agent."""
        task = context.current_task
        if task is None:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        await updater.update_status(
            TaskState.working,
            new_agent_text_message(
                "Processing task with LLM agent...", task.context_id, task.id
            ),
        )

        try:
            user_input = context.get_user_input()

            # Run the agent loop
            response = await self._run_agent_loop(user_input)

            # Send final response
            await updater.add_artifact(
                [Part(root=TextPart(text=response))],
                name="response",
            )
            await updater.complete()

        except Exception as e:
            error_message = f"Error: {str(e)}"
            await updater.add_artifact(
                [Part(root=TextPart(text=error_message))],
                name="error",
            )
            await updater.failed(
                new_agent_text_message(error_message, task.context_id, task.id)
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel the current task."""
        raise NotImplementedError("cancel not supported")


def create_llm_white_agent_app(agent_card_path: str) -> A2AStarletteApplication:
    """Create A2A application for the LLM white agent."""
    with open(agent_card_path, "rb") as f:
        agent_card_data = tomllib.load(f)

    app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_data),
        http_handler=DefaultRequestHandler(
            agent_executor=LLMWhiteAgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()

    return app


def main():
    """Main entry point for the LLM white agent."""
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
    )
    logger = logging.getLogger(__name__)

    # Validate configuration before starting
    try:
        settings.validate_required_settings()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your config.toml and .env files")
        raise SystemExit(1)

    print(
        f"Starting LLM-Powered White Agent on {settings.white_agent_host}:{settings.white_agent_port}"
    )
    print(f"Using agent card: {settings.white_agent_card_path}")
    print(f"Model: {settings.white_agent_model}")
    print()

    app = create_llm_white_agent_app(settings.white_agent_card_path)
    uvicorn.run(app, host=settings.white_agent_host, port=settings.white_agent_port)


if __name__ == "__main__":
    main()
