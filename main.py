"""CLI entry point for terminal-bench-green-agent."""

import typer
import os
import tomllib
from pathlib import Path
from pydantic_settings import BaseSettings
import uvicorn

app = typer.Typer(help="Terminal-Bench Green/White Agent")


class AgentSettings(BaseSettings):
    role: str = "unspecified"
    host: str = "127.0.0.1"
    agent_port: int = 9000


@app.command()
def run():
    """Start the agent with explicit role/host/port from controller."""
    settings = AgentSettings()
    
    if settings.role == "green":
        start_green_agent(host=settings.host, port=settings.agent_port)
    elif settings.role == "white":
        start_white_agent(host=settings.host, port=settings.agent_port)
    else:
        raise ValueError(f"Unknown role: {settings.role}. Must be 'green' or 'white'")


def start_green_agent(host: str, port: int):
    """Start the green agent with specified host and port."""
    from src.green_agent.green_agent import create_green_agent_app_from_dict
    from src.config import settings as config_settings
    import logging
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config_settings.log_level),
        format=config_settings.log_format,
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Terminal-Bench Green Agent on {host}:{port}")
    
    # Load agent card
    card_path = Path(config_settings.green_agent_card_path)
    with open(card_path, "rb") as f:
        agent_card_data = tomllib.load(f)
    
    # Override URL with AGENT_URL from environment (controller sets this)
    agent_url = os.getenv("AGENT_URL")
    if agent_url:
        agent_card_data["url"] = agent_url
        logger.info(f"Using AGENT_URL from environment: {agent_url}")
    else:
        logger.info(f"Using agent card URL: {agent_card_data.get('url', 'not set')}")
    
    # Create app
    app_instance = create_green_agent_app_from_dict(agent_card_data)
    
    # Start server
    uvicorn.run(app_instance, host=host, port=port)


def start_white_agent(host: str, port: int):
    """Start the white agent with specified host and port."""
    from white_agent.white_agent import create_llm_white_agent_app
    from src.config import settings as config_settings
    import logging
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config_settings.log_level),
        format=config_settings.log_format,
    )
    
    logger = logging.getLogger(__name__)
    
    # Use AGENT_URL from environment if available (for AgentBeats), otherwise construct from host/port
    agent_url = os.getenv("AGENT_URL")
    if not agent_url:
        agent_url = f"http://{host}:{port}"
    
    logger.info(f"Starting White Agent on {host}:{port}")
    logger.info(f"Agent URL: {agent_url} | Model: {config_settings.white_agent_model}")
    
    # Create app
    app_instance = create_llm_white_agent_app(agent_url)
    
    # Start server
    uvicorn.run(app_instance, host=host, port=port)


@app.command()
def green():
    """Start the green agent directly (for local testing)."""
    from src.green_agent.green_agent import main
    main()


@app.command()
def white():
    """Start the white agent directly (for local testing)."""
    from white_agent.white_agent import main
    main()


if __name__ == "__main__":
    app()

