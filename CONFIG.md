# Configuration Guide

This project uses a hybrid configuration approach with TOML and environment variables.

## Configuration Files

### 1. `config.toml` (Non-sensitive settings)

- Contains all non-sensitive configuration
- Safe to commit to version control
- Covers: ports, paths, evaluation settings, logging, etc.

### 2. `.env` (Sensitive data)

- Contains API keys and secrets
- **Already gitignored** - never commit this file
- Use `.env.example` as a template

### 3. `.env.example` (Template)

- Template showing required environment variables
- Safe to commit (contains no actual secrets)
- Copy to `.env` and fill in your values

## Setup Instructions

1. **Copy the template:**

   ```bash
   cp .env.example .env
   ```

2. **Add your API keys to `.env`:**

   ```bash
   # Edit .env and add your actual API key
   OPENAI_API_KEY="sk-your-actual-key-here"
   ```

3. **Customize settings in `config.toml`** (optional):
   - Adjust ports, paths, timeouts, etc.
   - No secrets should go here!

## Configuration Hierarchy

Environment variables override TOML settings:

1. **Environment variables** (highest priority)
2. **config.toml** defaults
3. **Code defaults** (lowest priority)

## Usage in Code

```python
from src.config import settings

# Access settings via properties
api_key = settings.openai_api_key
port = settings.green_agent_port
log_level = settings.log_level

# Or use the generic get method
custom_value = settings.get("custom.nested.key", "default_value")
```

## Common Settings

### API Keys (in `.env`)

- `OPENAI_API_KEY` - Required for LLM-based agents
- `ANTHROPIC_API_KEY` - Optional, if using Claude

### URLs (in `.env` or config.toml)

- `WHITE_AGENT_URL` - URL of agent being evaluated

### Execution (in `.env` or config.toml)

- `WHITE_AGENT_EXECUTION_ROOT` - Root directory for command execution
- `LOG_LEVEL` - Override logging level (DEBUG, INFO, WARNING, ERROR)

### Ports (in `config.toml`)

- `green_agent.port` - Green agent server port (default: 9999)
- `white_agent.port` - White agent server port (default: 8001)

### Evaluation (in `config.toml`)

- `evaluation.task_ids` - List of task IDs to run (e.g., ["hello-world", "csv-to-parquet"])
- `evaluation.n_attempts` - Number of attempts per task
- `evaluation.timeout_multiplier` - Timeout multiplier
- `evaluation.output_path` - Where to save results

### Dataset (in `config.toml`)

- `dataset.path` - Path to local terminal-bench tasks (e.g., "../terminal-bench/tasks")

## Security Best Practices

1. **Never commit `.env`** - It's already in `.gitignore`
2. **Use `.env.example`** - Keep it updated with required variables
3. **Rotate API keys** - Regularly rotate sensitive credentials
4. **Keep secrets in `.env`** - Non-sensitive config goes in `config.toml`

## Example Configuration

**config.toml:**

```toml
[green_agent]
port = 9999
host = "0.0.0.0"

[evaluation]
task_ids = ["hello-world", "csv-to-parquet"]
n_attempts = 3
timeout_multiplier = 1.5

[dataset]
path = "../terminal-bench/tasks"
```

**.env:**

```bash
OPENAI_API_KEY="sk-your-key-here"
WHITE_AGENT_URL="http://localhost:8001"
LOG_LEVEL="DEBUG"
```

## Troubleshooting

**Settings not loading?**

- Check that `config.toml` is in the project root
- Verify `.env` file exists and is in the project root
- Check for syntax errors in TOML or .env files

**Environment variable not working?**

- Use UPPERCASE with underscores: `GREEN_AGENT_PORT` not `green_agent.port`
- For nested keys: `EVALUATION_N_ATTEMPTS` for `evaluation.n_attempts`
- For lists: Use comma-separated strings: `EVALUATION_TASK_IDS="hello-world,csv-to-parquet"`

**API key not found?**

- Make sure `.env` exists (copy from `.env.example`)
- Check the key name matches exactly (case-sensitive)
- Verify no extra quotes or spaces in `.env` file
