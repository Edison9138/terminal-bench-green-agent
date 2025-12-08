"""Task-scoped MCP server for terminal-bench Docker containers."""
"""We start and stop the server for each task."""

import asyncio
import json
import logging
import socket
import threading
import time
from typing import Any

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

logger = logging.getLogger(__name__)


class TaskMCPServer:
    """MCP server bound to a specific Docker container."""

    def __init__(self, container_name: str, port: int):
        self.container_name = container_name
        self.port = port
        self.server = Server(f"terminal-bench-task-{container_name}")
        self.sse_transport = SseServerTransport("/messages/")
        self.uvicorn_server = None
        self.server_thread = None
        self._setup_tools()
        logger.info(f"MCP server: {container_name} on port {port}")

    def _setup_tools(self):
        """Register execute_bash_command tool."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="execute_bash_command",
                    description=f"Execute bash command in container '{self.container_name}' at /app",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Bash command"}
                        },
                        "required": ["command"],
                    },
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            if name != "execute_bash_command":
                return [TextContent(type="text", text=f"Error: Unknown tool {name}")]

            command = arguments.get("command")
            if not command:
                return [TextContent(type="text", text="Error: Command is required")]

            result = await self._execute_bash_command(command)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _execute_bash_command(self, command: str, timeout_sec: float = 1800.0) -> dict[str, Any]:
        """Execute bash command in Docker container.

        Args:
            command: The bash command to execute
            timeout_sec: Maximum time to wait for the command (default: 30 minutes)
        """
        logger.info(f"Exec: {command}")

        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                "-w",
                "/app",
                self.container_name,
                "bash",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_sec
                )
            except asyncio.TimeoutError:
                logger.warning(f"Command timed out after {timeout_sec}s: {command}")
                process.kill()
                await process.wait()
                return {
                    "command": command,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout_sec} seconds",
                }

            return {
                "command": command,
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            logger.error(f"Exec error: {e}")
            return {
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    async def handle_sse(self, request: Request) -> Response:
        """Handle SSE connections."""
        async with self.sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await self.server.run(
                streams[0], streams[1], self.server.create_initialization_options()
            )
        return Response()

    def _create_app(self) -> Starlette:
        """Create Starlette app."""
        return Starlette(
            debug=False,
            routes=[
                Route("/sse", endpoint=self.handle_sse),
                Mount("/messages/", app=self.sse_transport.handle_post_message),
            ],
        )

    def start(self):
        """Start MCP server in background thread.

        Note: Using daemon=False to ensure the server thread completes gracefully
        when shutdown() is called, rather than being killed abruptly when the
        main thread exits. This prevents "peer closed connection" errors.
        """
        config = uvicorn.Config(
            self._create_app(),
            host="0.0.0.0",
            port=self.port,
            log_level="error",
            timeout_keep_alive=3600,  # 1 hour keep-alive to support long-running commands
            timeout_notify=3600,  # 1 hour notify timeout
        )
        self.uvicorn_server = uvicorn.Server(config)

        self.server_thread = threading.Thread(
            target=lambda: asyncio.run(self.uvicorn_server.serve()),
            daemon=False,  # Use non-daemon thread for graceful shutdown
            name=f"MCP-{self.container_name}",
        )
        self.server_thread.start()
        time.sleep(2.0)  # Wait for server to initialize
        logger.info(f"MCP started on port {self.port}")

    def shutdown(self):
        """Shutdown MCP server gracefully.

        Gives the server up to 5 seconds to complete ongoing requests before
        forcing termination.
        """
        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True
            if self.server_thread:
                self.server_thread.join(timeout=5.0)  # Allow more time for graceful shutdown
                if self.server_thread.is_alive():
                    logger.warning("MCP server thread did not exit cleanly within timeout")
            logger.info("MCP shutdown")

    def is_ready(self) -> bool:
        """Check if server is ready."""
        if not self.uvicorn_server:
            return False
        try:
            with socket.create_connection(("localhost", self.port), timeout=1.0):
                return True
        except (socket.error, socket.timeout):
            return False


def create_task_mcp_server(container_name: str, port: int) -> TaskMCPServer:
    """Create task-scoped MCP server."""
    return TaskMCPServer(container_name, port)
