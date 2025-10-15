"""
Example White Agent for Testing

This is a simple white agent implementation that can be evaluated by the green agent.
It uses a basic LLM to respond to terminal-bench tasks.

This serves as a reference implementation for building your own white agents.
"""

import asyncio
import re
import shlex
import tomllib
import uvicorn
from dataclasses import dataclass
from typing import Any

from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCard, Part, TextPart, TaskState
from a2a.utils import new_task, new_agent_text_message
from a2a.server.tasks import TaskUpdater

from src.config import settings


class SimpleWhiteAgentExecutor(AgentExecutor):
    """
    A simple white agent that responds to terminal-bench tasks.

    Parses task instructions, generates command plans, executes them,
    and returns results with verification.
    """

    def __init__(self):
        """Initialize the white agent."""
        self.conversation_history = []
        self.execution_root = os.path.abspath(settings.white_agent_execution_root)

    @dataclass
    class CommandResult:
        """Structure for executed command results."""

        command: str
        returncode: int
        stdout: str
        stderr: str

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

        await updater.update_status(
            TaskState.working,
            new_agent_text_message("Processing task...", task.context_id, task.id),
        )
        user_input = context.get_user_input()
        self.conversation_history.append({"role": "user", "content": user_input})

        parsed_task = self._parse_task_instruction(user_input)
        command_plan = self._generate_command_plan(user_input, parsed_task)
        command_results: list[SimpleWhiteAgentExecutor.CommandResult] = []

        if command_plan:
            command_results = await self._execute_command_plan(command_plan)

        verification_passed, verification_message = self._verify_execution(
            command_plan, command_results
        )

        response = self._build_response(
            user_input,
            command_plan,
            command_results,
            verification_message,
        )

        self.conversation_history.append({"role": "assistant", "content": response})

        await updater.add_artifact(
            [Part(root=TextPart(text=response))],
            name="response",
        )

        if verification_passed:
            await updater.complete()
        else:
            await updater.failed(
                new_agent_text_message(
                    verification_message,
                    task.context_id,
                    task.id,
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel the current task (not implemented)."""
        raise NotImplementedError("cancel not supported")

    def _parse_task_instruction(self, instruction: str) -> dict[str, Any]:
        """Extract shell commands from instruction text."""
        commands: list[str] = []
        if not instruction:
            return {"commands": commands}
        for block in re.findall(r"```(?:bash|sh)?\n(.*?)```", instruction, flags=re.S):
            for line in block.splitlines():
                command = self._normalize_shell_line(line)
                if command:
                    commands.append(command)

        for line in instruction.splitlines():
            if line.strip().startswith("$"):
                command = self._normalize_shell_line(line)
                if command:
                    commands.append(command)

        return {"commands": commands}

    def _generate_command_plan(
        self,
        instruction: str,
        parsed_task: dict[str, Any],
    ) -> list[str]:
        """Generate a command execution plan from the instruction."""
        commands = list(parsed_task.get("commands", []))
        if commands:
            return commands
        lower_instruction = instruction.lower()
        heuristics: list[str] = []

        if any(keyword in lower_instruction for keyword in ("list files", "list the files", "show files", "list directory")):
            heuristics.append("ls")

        if any(keyword in lower_instruction for keyword in ("current directory", "working directory", "pwd")):
            heuristics.append("pwd")

        if "print file" in lower_instruction or "show file" in lower_instruction or "view file" in lower_instruction:
            targets = self._extract_file_targets(instruction)
            for target in targets:
                heuristics.append(f"cat {shlex.quote(target)}")

        return heuristics

    async def _execute_command_plan(
        self, commands: list[str]
    ) -> list[CommandResult]:
        """Run each command sequentially, stopping on failure."""
        results: list[SimpleWhiteAgentExecutor.CommandResult] = []
        for command in commands:
            if not self._is_command_allowed(command):
                results.append(
                    SimpleWhiteAgentExecutor.CommandResult(
                        command=command,
                        returncode=126,
                        stdout="",
                        stderr="Command blocked by safety rules.",
                    )
                )
                break

            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=self.execution_root,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout_bytes, stderr_bytes = await process.communicate()
            except FileNotFoundError as exc:
                results.append(
                    SimpleWhiteAgentExecutor.CommandResult(
                        command=command,
                        returncode=127,
                        stdout="",
                        stderr=str(exc),
                    )
                )
                break

            result = SimpleWhiteAgentExecutor.CommandResult(
                command=command,
                returncode=process.returncode,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
            )
            results.append(result)
            if process.returncode != 0:
                break

        return results

    def _verify_execution(
        self,
        commands: list[str],
        results: list[CommandResult],
    ) -> tuple[bool, str]:
        """Perform a simple verification pass on the execution results."""
        if not commands:
            return (
                True,
                "No executable commands detected; provided analysis only.",
            )

        if not results:
            return (
                False,
                "Command execution plan was empty or failed to start.",
            )

        failed = [res for res in results if res.returncode != 0]
        if failed:
            failure = failed[0]
            return (
                False,
                f"Command `{failure.command}` failed with exit code {failure.returncode}.",
            )

        return True, "All commands executed successfully."

    def _build_response(
        self,
        instruction: str,
        commands: list[str],
        results: list[CommandResult],
        verification_message: str,
    ) -> str:
        """Construct the text response shared with the green agent."""
        lines: list[str] = []
        lines.append("Task instruction received:")
        lines.append(instruction.strip() or "<empty instruction>")
        lines.append("")
        lines.append("Plan:")
        if commands:
            for command in commands:
                lines.append(f"- {command}")
        else:
            lines.append("- No executable commands identified; responding with guidance only.")

        lines.append("")
        lines.append("Execution:")
        if results:
            for result in results:
                lines.append(
                    f"- `{result.command}` -> exit {result.returncode}"
                )
                if result.stdout.strip():
                    lines.append(f"  stdout:\n{self._indent_block(result.stdout.strip())}")
                if result.stderr.strip():
                    lines.append(f"  stderr:\n{self._indent_block(result.stderr.strip())}")
        else:
            lines.append("- No commands were executed.")

        lines.append("")
        lines.append(f"Verification: {verification_message}")
        return "\n".join(lines)

    def _normalize_shell_line(self, line: str) -> str | None:
        """Normalize a shell line by stripping prompts and whitespace."""
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return None
        if stripped.startswith("$"):
            stripped = stripped[1:].strip()
        return stripped or None

    def _extract_file_targets(self, instruction: str) -> list[str]:
        """Attempt to pull file names from the instruction."""
        targets: list[str] = []
        pattern = re.compile(
            r"(?:file|path|for)\s+['\"]?([A-Za-z0-9_\-./]+)['\"]?",
            flags=re.I,
        )
        for match in pattern.findall(instruction):
            targets.append(match)
        return targets

    def _is_command_allowed(self, command: str) -> bool:
        """Block obviously unsafe commands."""
        try:
            tokens = shlex.split(command)
        except ValueError:
            return False
        if not tokens:
            return False
        blocked = set(settings.blocked_commands)
        return tokens[0] not in blocked

    @staticmethod
    def _indent_block(block: str) -> str:
        """Indent multi-line text blocks for readability."""
        indented_lines = [f"    {line}" for line in block.splitlines()]
        return "\n".join(indented_lines)


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
    parser.add_argument(
        "--port",
        type=int,
        default=settings.white_agent_port,
        help="Port to run on"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=settings.white_agent_host,
        help="Host to bind to"
    )
    parser.add_argument(
        "--card",
        type=str,
        default=settings.white_agent_card_path,
        help="Path to agent card",
    )

    args = parser.parse_args()

    print(f"Starting Example White Agent on {args.host}:{args.port}")
    print(f"Using agent card: {args.card}")
    print(f"Execution root: {settings.white_agent_execution_root}")
    print("\nThis is a simple example agent for testing.")
    print("Replace this with your actual agent implementation.\n")

    # Create and run app
    app = create_white_agent_app(args.card)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
