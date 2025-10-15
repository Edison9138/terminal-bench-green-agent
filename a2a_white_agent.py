"""
A2A White Agent Adapter for Terminal-Bench

This module provides an adapter that implements terminal-bench's BaseAgent interface
while communicating with an A2A-compatible agent over HTTP.

This allows terminal-bench to evaluate any agent that exposes an A2A interface,
regardless of the underlying implementation (OpenAI Agents SDK, LangChain, custom, etc.)
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

from terminal_bench.agents.base_agent import BaseAgent, AgentResult
from terminal_bench.agents.failure_mode import FailureMode
from terminal_bench.terminal.tmux_session import TmuxSession

from utils.a2a_client import send_message_to_agent

logger = logging.getLogger(__name__)


class A2AWhiteAgent(BaseAgent):
    """
    Terminal-Bench agent that communicates with an A2A-compatible agent.

    This adapter allows terminal-bench to evaluate any agent that implements
    the A2A (Agent-to-Agent) protocol.
    """

    def __init__(self, agent_url: str, **kwargs):
        """
        Initialize the A2A white agent adapter.

        Args:
            agent_url: URL of the A2A-compatible agent being evaluated
            **kwargs: Additional arguments (ignored)
        """
        self.agent_url = agent_url
        self._timestamped_markers = []
        logger.info(f"A2AWhiteAgent initialized with agent at: {agent_url}")

    @classmethod
    def name(cls) -> str:
        """Return the name of this agent type."""
        return "a2a-agent"

    def _format_task_instruction(self, instruction: str, session: TmuxSession) -> str:
        """
        Format the task instruction for the white agent.

        Provides the agent with:
        - The task instruction
        - Information about available tools/capabilities
        - Terminal session context (if needed)
        """
        message = f"""
You are being evaluated on the Terminal-Bench benchmark.

TASK:
{instruction}

You have access to a terminal session where you can execute commands.
When you need to run a command, use the appropriate tool to execute it.

Important:
- Complete the task as instructed
- You can execute multiple commands if needed
- When you believe the task is complete, indicate completion
- If you encounter errors, explain what went wrong

Please proceed with the task.
"""
        return message

    async def _send_to_agent_async(self, message: str) -> str:
        """
        Send a message to the A2A agent asynchronously.

        Args:
            message: The message to send

        Returns:
            The agent's response as a string
        """
        try:
            logger.info(f"Sending message to agent at {self.agent_url}")
            logger.debug(f"Message: {message[:200]}...")

            # send_message_to_agent now returns a string directly
            response = await send_message_to_agent(message, self.agent_url)

            logger.info(f"Received response from agent ({len(response)} chars)")
            logger.debug(f"Response: {response[:200]}...")
            return response

        except Exception as e:
            logger.error(f"Error communicating with agent: {e}", exc_info=True)
            return f"Error: {str(e)}"

    def _check_for_errors(self, response: str) -> FailureMode:
        """
        Check the agent's response for error indicators.

        Args:
            response: The agent's response text

        Returns:
            FailureMode indicating if an error was detected
        """
        if "Error:" in response:
            return FailureMode.UNKNOWN_AGENT_ERROR
        return FailureMode.NONE

    def perform_task(
        self,
        instruction: str,
        session: TmuxSession,
        logging_dir: Path,
    ) -> AgentResult:
        """
        Perform a terminal-bench task by communicating with the A2A agent.

        Args:
            instruction: The task instruction from terminal-bench
            session: The tmux session for terminal interaction
            logging_dir: Directory for logging agent outputs

        Returns:
            AgentResult with completion status and metadata
        """
        logger.info(f"Starting task: {instruction[:100]}...")

        # Format the instruction for the agent
        formatted_message = self._format_task_instruction(instruction, session)

        # Send to agent and get response (using asyncio)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                self._send_to_agent_async(formatted_message)
            )
        finally:
            loop.close()

        # Log the interaction
        log_file = logging_dir / "agent_interaction.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write("=" * 80 + "\n")
            f.write("INSTRUCTION:\n")
            f.write(formatted_message + "\n")
            f.write("-" * 80 + "\n")
            f.write("RESPONSE:\n")
            f.write(response + "\n")
            f.write("=" * 80 + "\n\n")

        # Check for errors in response
        failure_mode = self._check_for_errors(response)

        if failure_mode != FailureMode.NONE:
            logger.warning(f"Agent reported failure: {failure_mode}")
        else:
            logger.info("Agent completed task successfully")

        # Create result
        # Note: Token counting would require parsing the A2A response more carefully
        # For now, we return None for token counts
        result = AgentResult(
            failure_mode=failure_mode,
            timestamped_markers=self._timestamped_markers,
            total_input_tokens=None,
            total_output_tokens=None,
        )

        return result

    def cleanup(self) -> None:
        """Cleanup any resources (optional)."""
        pass
