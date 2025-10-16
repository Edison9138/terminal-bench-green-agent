"""
Configuration settings loader for terminal-bench green agent.

Loads configuration from:
1. config.toml (non-sensitive settings)
2. .env file (sensitive data like API keys)

Environment variables override TOML settings.
"""

import os
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """
    Configuration settings manager.

    Combines settings from config.toml and environment variables.
    Environment variables take precedence over TOML settings.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize settings.

        Args:
            config_path: Path to config.toml file. If None, searches for it
                        in the project root.
        """
        # Find project root (directory containing config.toml)
        if config_path is None:
            current = Path(__file__).resolve()
            # Go up from src/config/settings.py to project root
            project_root = current.parent.parent.parent
            config_path = project_root / "config.toml"

        self.config_path = config_path
        self._config: Dict[str, Any] = {}

        # Load TOML config if it exists
        if self.config_path.exists():
            with open(self.config_path, "rb") as f:
                self._config = tomllib.load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Dot-separated key path (e.g., "green_agent.port")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        # Try environment variable first (convert to uppercase with underscores)
        env_key = key.upper().replace(".", "_")
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        # Fall back to TOML config
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default

        return value if value is not None else default

    # =========================================================================
    # Convenience properties for commonly used settings
    # =========================================================================

    # API Keys
    @property
    def openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from environment."""
        return os.getenv("OPENAI_API_KEY")

    @property
    def anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API key from environment."""
        return os.getenv("ANTHROPIC_API_KEY")

    # Green Agent Settings
    @property
    def green_agent_host(self) -> str:
        """Get green agent host."""
        return self.get("green_agent.host", "0.0.0.0")

    @property
    def green_agent_port(self) -> int:
        """Get green agent port."""
        port = self.get("green_agent.port", 9999)
        return int(port)

    @property
    def green_agent_card_path(self) -> str:
        """Get green agent card path."""
        return self.get("green_agent.card_path", "src/green_agent/card.toml")

    # White Agent Settings
    @property
    def white_agent_host(self) -> str:
        """Get white agent host."""
        return self.get("white_agent.host", "0.0.0.0")

    @property
    def white_agent_port(self) -> int:
        """Get white agent port."""
        port = self.get("white_agent.port", 8001)
        return int(port)

    @property
    def white_agent_card_path(self) -> str:
        """Get white agent card path."""
        return self.get("white_agent.card_path", "white_agent/white_agent_card.toml")

    @property
    def white_agent_execution_root(self) -> str:
        """Get white agent execution root directory."""
        # Environment variable takes precedence
        env_root = os.getenv("WHITE_AGENT_EXECUTION_ROOT")
        if env_root:
            return env_root
        return self.get("white_agent.execution_root", os.getcwd())

    @property
    def white_agent_model(self) -> str:
        """Get white agent LLM model."""
        # Environment variable takes precedence
        env_model = os.getenv("WHITE_AGENT_MODEL")
        if env_model:
            return env_model
        return self.get("white_agent.model", "gpt-4o-mini")

    @property
    def white_agent_url(self) -> str:
        """Get white agent URL from environment or default."""
        return os.getenv("WHITE_AGENT_URL", "http://localhost:8001")

    # Evaluation Settings
    @property
    def eval_output_path(self) -> str:
        """Get evaluation output path."""
        return self.get("evaluation.output_path", "./eval_results")

    @property
    def eval_n_attempts(self) -> int:
        """Get number of evaluation attempts."""
        attempts = self.get("evaluation.n_attempts", 1)
        return int(attempts)

    @property
    def eval_n_concurrent_trials(self) -> int:
        """Get number of concurrent trials."""
        trials = self.get("evaluation.n_concurrent_trials", 1)
        return int(trials)

    @property
    def eval_timeout_multiplier(self) -> float:
        """Get timeout multiplier."""
        multiplier = self.get("evaluation.timeout_multiplier", 1.0)
        return float(multiplier)

    @property
    def eval_cleanup(self) -> bool:
        """Get cleanup setting."""
        cleanup = self.get("evaluation.cleanup", False)
        return bool(cleanup)

    @property
    def eval_task_ids(self) -> list[str]:
        """Get list of task IDs to run."""
        task_ids = self.get("evaluation.task_ids", ["hello-world"])
        # Handle case where it's a comma-separated string from env var
        if isinstance(task_ids, str):
            return [t.strip() for t in task_ids.split(",")]
        return task_ids

    # Dataset Settings
    @property
    def dataset_path(self) -> Optional[str]:
        """Get dataset path if specified."""
        # Environment variable takes precedence
        env_path = os.getenv("DATASET_PATH")
        if env_path:
            return env_path
        return self.get("dataset.path")

    # Logging Settings
    @property
    def log_level(self) -> str:
        """Get log level."""
        # Environment variable takes precedence
        env_level = os.getenv("LOG_LEVEL")
        if env_level:
            return env_level
        return self.get("logging.level", "INFO")

    @property
    def log_format(self) -> str:
        """Get log format."""
        return self.get(
            "logging.format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Safety Settings
    @property
    def blocked_commands(self) -> list[str]:
        """Get list of blocked commands."""
        return self.get(
            "safety.blocked_commands", ["rm", "sudo", "shutdown", "reboot", "halt"]
        )

    # A2A Settings
    @property
    def a2a_default_input_modes(self) -> list[str]:
        """Get default input modes."""
        return self.get("a2a.default_input_modes", ["text"])

    @property
    def a2a_default_output_modes(self) -> list[str]:
        """Get default output modes."""
        return self.get("a2a.default_output_modes", ["text"])

    @property
    def a2a_streaming(self) -> bool:
        """Get streaming setting."""
        return self.get("a2a.streaming", True)


# Global settings instance
settings = Settings()
