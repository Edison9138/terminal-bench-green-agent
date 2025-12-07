"""Helper for solving tasks using LLM with MCP tools."""

import json
import logging
from typing import Any
from openai import OpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client
from src.config.settings import settings

logger = logging.getLogger(__name__)


class MCPConnection:
    """Context manager for MCP connections with proper cleanup."""

    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self.sse_context = None
        self.session = None
        self.read_stream = None
        self.write_stream = None

    async def __aenter__(self) -> ClientSession:
        """Connect to MCP server."""
        sse_url = f"{self.mcp_url}/sse"
        logger.info(f"Connecting to {sse_url}")

        self.sse_context = sse_client(sse_url)
        self.read_stream, self.write_stream = await self.sse_context.__aenter__()

        self.session = ClientSession(self.read_stream, self.write_stream)
        await self.session.__aenter__()
        await self.session.initialize()

        tools = await self.session.list_tools()
        logger.info(f"Connected. Tools: {[t.name for t in tools.tools]}")

        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup MCP resources."""
        if self.session:
            try:
                await self.session.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.warning(f"Session close error: {e}")

        if self.sse_context:
            try:
                await self.sse_context.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.warning(f"SSE close error: {e}")

        logger.info("MCP closed")


def connect_to_mcp(mcp_url: str) -> MCPConnection:
    """Create MCP connection context manager."""
    return MCPConnection(mcp_url)


def convert_mcp_tools_to_openai_responses_api(tools_result) -> list[dict]:
    """Convert MCP tools to OpenAI Responses API format.

    For Responses API, tools have a flatter structure with name/description/parameters
    at the top level, unlike Chat Completions API which nests them under 'function'.
    """
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema,
        }
        for tool in tools_result.tools
    ]


def convert_mcp_tools_to_openai_chat_completions(tools_result) -> list[dict]:
    """Convert MCP tools to OpenAI Chat Completions API format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            },
        }
        for tool in tools_result.tools
    ]


async def call_mcp_tool(
    session: ClientSession, tool_name: str, arguments: dict
) -> dict[str, Any]:
    """Call MCP tool and return result."""
    logger.debug(f"Calling {tool_name}: {arguments}")

    result = await session.call_tool(tool_name, arguments=arguments)

    if result.content and len(result.content) > 0:
        return json.loads(result.content[0].text)
    return {"error": "No result from MCP server"}


async def solve_task_with_responses_api(
    user_input: str,
    mcp_session: ClientSession,
    openai_client: OpenAI,
    model: str,
    max_iterations: int = 10,
) -> tuple[str, int, int]:
    """Solve task using LLM with MCP tools using the Responses API.

    This function uses the OpenAI Responses API (client.responses.create) which is
    required for models like gpt-5.1-codex-mini that only support v1/responses endpoint.

    Returns:
        tuple: (response_text, total_input_tokens, total_output_tokens)
    """
    tools_result = await mcp_session.list_tools()
    openai_tools = convert_mcp_tools_to_openai_responses_api(tools_result)
    logger.info(f"Using {len(openai_tools)} MCP tools")

    # Initialize token counters
    total_input_tokens = 0
    total_output_tokens = 0

    # System instructions for the Responses API
    system_instructions = """You are an expert system administrator being evaluated on the Terminal-Bench, a benchmark for ai agents in terminal environments.

    Your task is to solve terminal challenges by executing bash commands step-by-step.

    ## ReAct Framework
    For each step, follow this pattern:

    **Thought**: Analyze the current situation and decide what to do next
    **Action**: Execute a bash command to make progress
    **Observation**: Examine the command output carefully
    **Reflection**: Assess if you're moving toward the goal or need to adjust

    ## Key Principles
    1. **Read before acting**: Use ls, cat, head to understand the environment first
    2. **One step at a time**: Execute simple commands, verify results, then proceed
    3. **Learn from errors**: If a command fails, analyze stderr and try a different approach
    4. **Verify completion**: Before finishing, confirm all requirements are met
    5. **Stay focused**: Each command should directly contribute to the task goal

    ## Common Patterns
    - Start with exploration: ls, pwd, cat README.md
    - Check dependencies: which <tool>, <tool> --version
    - Test incrementally: Don't write complex scripts without testing parts first
    - Verify output: After creating/modifying files, cat or grep to confirm

    When you believe the task is complete, explain what you did and why it satisfies all requirements."""

    # Track previous response ID for multi-turn conversation
    previous_response_id = None

    for iteration in range(1, max_iterations + 1):
        logger.info(f"=== Iteration {iteration}/{max_iterations} ===")

        # Build request parameters
        request_params = {
            "model": model,
            "instructions": system_instructions,
            "tools": openai_tools,
        }

        # For first iteration, send user input; for subsequent iterations, use previous_response_id
        if previous_response_id is None:
            request_params["input"] = [{"role": "user", "content": user_input}]
        else:
            request_params["previous_response_id"] = previous_response_id

        # Use Responses API instead of Chat Completions API
        response = openai_client.responses.create(**request_params)

        # Track token usage from this API call (Responses API uses different field names)
        if hasattr(response, "usage") and response.usage:
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens
            logger.debug(
                f"Tokens this iteration: {response.usage.input_tokens} in, {response.usage.output_tokens} out"
            )

        # Process response - keep checking for function calls and executing them
        while True:
            # Extract text output and function calls from response.output
            text_output = ""
            function_calls = []

            for output_item in response.output:
                if output_item.type == "message":
                    # Extract text content from message
                    for content_item in output_item.content:
                        if content_item.type == "output_text":
                            text_output += content_item.text
                elif output_item.type == "function_call":
                    # Collect function calls
                    function_calls.append(output_item)

            logger.info(
                f"LLM: {text_output[:200] if text_output else 'None'} | "
                f"Tools: {len(function_calls)}"
            )

            # If no function calls, we're done with this iteration
            if not function_calls:
                # If we have text output, the task is complete
                if text_output or iteration == max_iterations:
                    logger.info("No tool calls. Done.")
                    logger.info(
                        f"Total tokens used: {total_input_tokens} in, {total_output_tokens} out"
                    )
                    return (
                        text_output or "Task completed.",
                        total_input_tokens,
                        total_output_tokens,
                    )
                # Otherwise, continue to next iteration
                break

            # Execute function calls and send results back
            logger.info(f"Executing {len(function_calls)} tool(s)")

            # Collect all function call outputs
            function_outputs = []
            for func_call in function_calls:
                fn_name = func_call.name
                fn_args = json.loads(func_call.arguments)
                logger.info(f"Tool: {fn_name} | Args: {fn_args}")

                result = await call_mcp_tool(mcp_session, fn_name, fn_args)
                logger.debug(f"Result: {result}")

                # Format result message
                if "error" in result:
                    result_msg = f"Error: {result['error']}"
                else:
                    result_msg = f"Command: {result.get('command', 'N/A')}\n"
                    result_msg += f"Exit code: {result.get('returncode', 'N/A')}\n"
                    if result.get("stdout"):
                        result_msg += f"Output:\n{result['stdout']}"
                    if result.get("stderr"):
                        result_msg += f"Error:\n{result['stderr']}"

                # Collect function call output
                function_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": func_call.call_id,
                        "output": result_msg,
                    }
                )

            # Send function outputs back and get new response
            # For Responses API, we send function outputs as input with previous_response_id
            logger.info(
                f"Sending {len(function_outputs)} function outputs back to model"
            )
            response = openai_client.responses.create(
                model=model,
                instructions=system_instructions,
                input=function_outputs,
                tools=openai_tools,
                previous_response_id=response.id,
            )

            # Track tokens from this API call
            if hasattr(response, "usage") and response.usage:
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

            # Continue the while loop to check if this response has more function calls

        # Update previous_response_id for next iteration
        previous_response_id = response.id

    logger.info(
        f"Total tokens used: {total_input_tokens} in, {total_output_tokens} out"
    )
    return (
        "Task completed (reached iteration limit).",
        total_input_tokens,
        total_output_tokens,
    )


async def solve_task_with_chat_completions_api(
    user_input: str,
    mcp_session: ClientSession,
    openai_client: OpenAI,
    model: str,
    max_iterations: int = 10,
) -> tuple[str, int, int]:
    """Solve task using LLM with MCP tools using the Chat Completions API.

    This function uses the OpenAI Chat Completions API (client.chat.completions.create)
    which is required for models like gpt-4o-mini that only support v1/chat/completions endpoint.

    Returns:
        tuple: (response_text, total_input_tokens, total_output_tokens)
    """
    tools_result = await mcp_session.list_tools()
    openai_tools = convert_mcp_tools_to_openai_chat_completions(tools_result)
    logger.info(f"Using {len(openai_tools)} MCP tools")

    # Initialize token counters
    total_input_tokens = 0
    total_output_tokens = 0

    messages = [
        {
            "role": "system",
            "content": """You are a helpful assistant being evaluated on Terminal-Bench.

Your goal is to complete terminal tasks by executing bash commands.

Guidelines:
- Break down complex tasks into simple steps
- Execute one command at a time and check the result
- If a command fails, analyze the error and try a different approach
- When complete, provide a clear summary
- Be concise but thorough""",
        },
        {"role": "user", "content": user_input},
    ]

    for iteration in range(1, max_iterations + 1):
        logger.info(f"=== Iteration {iteration}/{max_iterations} ===")

        response = openai_client.chat.completions.create(
            model=model, messages=messages, tools=openai_tools, tool_choice="auto"
        )

        # Track token usage from this API call
        if response.usage:
            total_input_tokens += response.usage.prompt_tokens
            total_output_tokens += response.usage.completion_tokens
            logger.debug(f"Tokens this iteration: {response.usage.prompt_tokens} in, {response.usage.completion_tokens} out")

        assistant_msg = response.choices[0].message
        logger.info(
            f"LLM: {assistant_msg.content[:200] if assistant_msg.content else 'None'} | "
            f"Tools: {len(assistant_msg.tool_calls) if assistant_msg.tool_calls else 0}"
        )

        messages.append(
            {
                "role": "assistant",
                "content": assistant_msg.content,
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
                        for tc in assistant_msg.tool_calls
                    ]
                    if assistant_msg.tool_calls
                    else None
                ),
            }
        )

        if not assistant_msg.tool_calls:
            logger.info("No tool calls. Done.")
            logger.info(f"Total tokens used: {total_input_tokens} in, {total_output_tokens} out")
            return (
                assistant_msg.content or "Task completed.",
                total_input_tokens,
                total_output_tokens,
            )

        logger.info(f"Executing {len(assistant_msg.tool_calls)} tool(s)")
        for tool_call in assistant_msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            logger.info(f"Tool: {fn_name} | Args: {fn_args}")

            result = await call_mcp_tool(mcp_session, fn_name, fn_args)
            logger.debug(f"Result: {result}")

            if "error" in result:
                result_msg = f"Error: {result['error']}"
            else:
                result_msg = f"Command: {result.get('command', 'N/A')}\n"
                result_msg += f"Exit code: {result.get('returncode', 'N/A')}\n"
                if result.get("stdout"):
                    result_msg += f"Output:\n{result['stdout']}"
                if result.get("stderr"):
                    result_msg += f"Error:\n{result['stderr']}"

            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result_msg}
            )

    logger.info(f"Total tokens used: {total_input_tokens} in, {total_output_tokens} out")
    return (
        "Task completed (reached iteration limit).",
        total_input_tokens,
        total_output_tokens,
    )


async def solve_task_with_llm_and_mcp(
    user_input: str,
    mcp_session: ClientSession,
    openai_client: OpenAI,
    model: str,
    max_iterations: int = 10,
) -> tuple[str, int, int]:
    """Solve task using LLM with MCP tools.

    This router function automatically selects the appropriate API implementation
    based on the model being used:
    - gpt-4o-mini and similar models: Chat Completions API
    - gpt-5.1-codex-mini and similar models: Responses API

    Returns:
        tuple: (response_text, total_input_tokens, total_output_tokens)
    """
    # Models that only support Chat Completions API
    chat_completions_models = [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ]

    # Check if model uses Chat Completions API
    uses_chat_completions = any(
        chat_model in model for chat_model in chat_completions_models
    )

    if uses_chat_completions:
        logger.info(f"Using Chat Completions API for model: {model}")
        return await solve_task_with_chat_completions_api(
            user_input, mcp_session, openai_client, model, max_iterations
        )
    else:
        logger.info(f"Using Responses API for model: {model}")
        return await solve_task_with_responses_api(
            user_input, mcp_session, openai_client, model, max_iterations
        )
