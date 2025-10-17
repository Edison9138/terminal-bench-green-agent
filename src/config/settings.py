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
from typing import Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ConfigurationError(Exception):
    """Raised when there's a configuration error."""

    pass


class Settings:
    """
    Configuration settings manager.

    Combines settings from config.toml and environment variables.
    Environment variables take precedence over TOML settings.
    """

    def __init__(self, config_path: Path | None = None):
        """
        Initialize settings.

        Args:
            config_path: Path to config.toml file. If None, searches for it
                        in the project root.

        Raises:
            ConfigurationError: If config.toml doesn't exist or has invalid syntax
        """
        # Find project root (directory containing config.toml)
        if config_path is None:
            current = Path(__file__).resolve()
            # Go up from src/config/settings.py to project root
            project_root = current.parent.parent.parent
            config_path = project_root / "config.toml"

        self.config_path = config_path
        self._config: dict[str, Any] = {}

        # Validate that config file exists
        if not self.config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create a config.toml file in the project root.\n"
                f"You can copy config.toml.example as a starting point."
            )

        # Load TOML config with error handling
        try:
            with open(self.config_path, "rb") as f:
                self._config = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationError(
                f"Invalid TOML syntax in {self.config_path}:\n{e}\n"
                f"Please check your config.toml file for syntax errors."
            ) from e
        except PermissionError as e:
            raise ConfigurationError(
                f"Permission denied reading {self.config_path}:\n{e}"
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Error loading config from {self.config_path}:\n{e}"
            ) from e

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
    def openai_api_key(self) -> str | None:
        """Get OpenAI API key from environment."""
        return os.getenv("OPENAI_API_KEY")

    @property
    def anthropic_api_key(self) -> str | None:
        """Get Anthropic API key from environment."""
        return os.getenv("ANTHROPIC_API_KEY")

    # Green Agent Settings
    @property
    def green_agent_host(self) -> str:
        """Get green agent host (required)."""
        host = self.get("green_agent.host")
        if not host:
            raise ConfigurationError(
                "green_agent.host is required. Please set it in config.toml:\n"
                "[green_agent]\n"
                'host = "0.0.0.0"  # Use 0.0.0.0 for all interfaces or 127.0.0.1 for localhost only'
            )
        return host

    @property
    def green_agent_port(self) -> int:
        """Get green agent port (required)."""
        port = self.get("green_agent.port")
        if port is None:
            raise ConfigurationError(
                "green_agent.port is required. Please set it in config.toml:\n"
                "[green_agent]\n"
                "port = 9999"
            )
        return int(port)

    @property
    def green_agent_card_path(self) -> str:
        """Get green agent card path (required)."""
        path = self.get("green_agent.card_path")
        if not path:
            raise ConfigurationError(
                "green_agent.card_path is required. Please set it in config.toml:\n"
                "[green_agent]\n"
                'card_path = "src/green_agent/card.toml"'
            )
        return path

    # White Agent Settings
    @property
    def white_agent_host(self) -> str:
        """Get white agent host (required)."""
        host = self.get("white_agent.host")
        if not host:
            raise ConfigurationError(
                "white_agent.host is required. Please set it in config.toml:\n"
                "[white_agent]\n"
                'host = "0.0.0.0"'
            )
        return host

    @property
    def white_agent_port(self) -> int:
        """Get white agent port (required)."""
        port = self.get("white_agent.port")
        if port is None:
            raise ConfigurationError(
                "white_agent.port is required. Please set it in config.toml:\n"
                "[white_agent]\n"
                "port = 8001"
            )
        return int(port)

    @property
    def white_agent_card_path(self) -> str:
        """Get white agent card path (required)."""
        path = self.get("white_agent.card_path")
        if not path:
            raise ConfigurationError(
                "white_agent.card_path is required. Please set it in config.toml:\n"
                "[white_agent]\n"
                'card_path = "white_agent/white_agent_card.toml"'
            )
        return path

    @property
    def white_agent_model(self) -> str:
        """Get white agent LLM model (required)."""
        # Environment variable takes precedence
        env_model = os.getenv("WHITE_AGENT_MODEL")
        if env_model:
            return env_model

        model = self.get("white_agent.model")
        if not model:
            raise ConfigurationError(
                "white_agent.model is required. Please set it in config.toml:\n"
                "[white_agent]\n"
                'model = "gpt-4o-mini"  # Or your preferred model\n'
                "Or set the WHITE_AGENT_MODEL environment variable"
            )
        return model

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
        """Get list of task IDs to run (required)."""
        task_ids = self.get("evaluation.task_ids")
        if not task_ids:
            raise ConfigurationError(
                "evaluation.task_ids is required. Please set it in config.toml:\n"
                "[evaluation]\n"
                'task_ids = ["hello-world"]  # Or your preferred task IDs\n'
                "Or set the EVALUATION_TASK_IDS environment variable"
            )
        # Handle case where it's a comma-separated string from env var
        if isinstance(task_ids, str):
            return [t.strip() for t in task_ids.split(",")]
        return task_ids

    # Dataset Settings
    @property
    def dataset_path(self) -> str | None:
        """Get dataset path (optional - terminal-bench manages datasets automatically)."""
        # Environment variable takes precedence
        env_path = os.getenv("DATASET_PATH")
        if env_path:
            return env_path

        # Check if dataset path is specified in config
        path = self.get("dataset.path")
        if path:
            return path

        # If no path specified, terminal-bench will use its default dataset management
        return None

    @property
    def dataset_name(self) -> str:
        """Get dataset name for automatic dataset management."""
        return self.get("dataset.name", "terminal-bench-core")

    @property
    def dataset_version(self) -> str:
        """Get dataset version for automatic dataset management."""
        return self.get("dataset.version", "head")

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

    # A2A Settings
    @property
    def a2a_message_timeout(self) -> float:
        """Get timeout for sending messages to agents in seconds (default: 300.0)."""
        timeout = self.get("a2a.message_timeout", 300.0)
        return float(timeout)

    @property
    def a2a_health_check_timeout(self) -> float:
        """Get timeout for health check requests in seconds (default: 5.0)."""
        timeout = self.get("a2a.health_check_timeout", 5.0)
        return float(timeout)

    def validate_required_settings(self) -> None:
        """
        Validate that all required settings are present and accessible.

        This should be called at application startup to fail fast if
        configuration is incomplete.

        Raises:
            ConfigurationError: If any required setting is missing or invalid
        """
        # Validate required settings by accessing their properties
        # These will raise ConfigurationError with helpful messages if missing
        _ = self.green_agent_host
        _ = self.green_agent_port
        _ = self.green_agent_card_path
        _ = self.white_agent_host
        _ = self.white_agent_port
        _ = self.white_agent_card_path
        _ = self.white_agent_model
        _ = self.eval_task_ids


# Global settings instance
settings = Settings()
