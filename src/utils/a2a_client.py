"""
A2A Client Utilities

Helper functions for communicating with A2A-compatible agents.
"""

import httpx
from uuid import uuid4
from typing import List

from a2a.client import A2AClient, A2ACardResolver
from a2a.types import (
    AgentCard,
    Message,
    Part,
    TextPart,
    Role,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    MessageSendParams,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)


async def send_message_to_agent(
    message: str, agent_url: str, timeout: float = 300.0
) -> str:
    """
    Send a message to an A2A-compatible agent and return the response.

    Args:
        message: The message text to send
        agent_url: The base URL of the agent (e.g., "http://localhost:8001")
        timeout: Request timeout in seconds (default: 300s for long-running tasks)

    Returns:
        String response from the agent

    Raises:
        RuntimeError: If agent card cannot be resolved or other errors occur
    """
    httpx_client = None
    try:
        # Create A2A client
        httpx_client = httpx.AsyncClient(timeout=timeout)
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=agent_url)

        card: AgentCard | None = await resolver.get_agent_card(
            relative_card_path="/.well-known/agent.json"
        )

        if card is None:
            raise RuntimeError(f"Failed to resolve agent card from {agent_url}")

        client = A2AClient(httpx_client=httpx_client, agent_card=card)

        # Create message request
        params = MessageSendParams(
            message=Message(
                role=Role.user,
                parts=[Part(TextPart(text=message))],
                messageId=uuid4().hex,
                taskId=None,
            )
        )
        req = SendStreamingMessageRequest(id=str(uuid4()), params=params)

        # Collect response chunks
        chunks: List[str] = []

        async for chunk in client.send_message_streaming(req):
            if not isinstance(chunk.root, SendStreamingMessageSuccessResponse):
                continue
            event = chunk.root.result
            if isinstance(event, TaskArtifactUpdateEvent):
                for p in event.artifact.parts:
                    if isinstance(p.root, TextPart):
                        chunks.append(p.root.text)
            elif isinstance(event, TaskStatusUpdateEvent):
                msg = event.status.message
                if msg:
                    for p in msg.parts:
                        if isinstance(p.root, TextPart):
                            chunks.append(p.root.text)

        response = "".join(chunks).strip() or "No response from agent."

        return response

    finally:
        # Clean up the httpx client to prevent resource leaks
        if httpx_client:
            await httpx_client.aclose()


async def check_agent_health(agent_url: str) -> bool:
    """
    Check if an A2A agent is healthy and responding.

    Args:
        agent_url: The base URL of the agent

    Returns:
        True if agent is healthy, False otherwise
    """
    httpx_client = None
    try:
        httpx_client = httpx.AsyncClient(timeout=5.0)
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=agent_url)
        agent_card = await resolver.get_agent_card()
        return agent_card is not None
    except Exception:
        return False
    finally:
        if httpx_client:
            await httpx_client.aclose()


async def get_agent_card(agent_url: str) -> dict | None:
    """
    Get the agent card from an A2A agent.

    Args:
        agent_url: The base URL of the agent

    Returns:
        Agent card as a dictionary, or None if failed
    """
    httpx_client = None
    try:
        httpx_client = httpx.AsyncClient(timeout=5.0)
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=agent_url)

        agent_card = await resolver.get_agent_card()

        if agent_card:
            return agent_card.model_dump(exclude_none=True)
        else:
            return None
    except Exception:
        return None
    finally:
        if httpx_client:
            await httpx_client.aclose()
