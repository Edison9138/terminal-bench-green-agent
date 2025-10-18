# Setup Guide

Complete guide for setting up, configuring, and building agents for terminal-bench evaluation.

## Prerequisites

- Python 3.10+
- Docker (required for terminal-bench task environments)
- OpenAI API key (for LLM-powered white agent)

## Installation

```bash
# Setup environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Download terminal-bench dataset
terminal-bench datasets download --dataset terminal-bench-core

# Configure API key
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY="sk-your-key"
```

Verify installation:
```bash
terminal-bench --help
docker ps  # Check Docker is running
```

## Configuration

### Configuration Files

- **`config.toml`** - All settings (ports, paths, eval params). Safe to commit.
- **`.env`** - API keys and secrets. Already gitignored, never commit.
- **`.env.example`** - Template for `.env`

### Configuration Hierarchy

1. Environment variables (highest priority)
2. `config.toml` settings

**ALL fields in config.toml are REQUIRED.** The app will fail with helpful error messages if any are missing.

### Complete config.toml Example

```toml
[green_agent]
host = "0.0.0.0"
port = 9999
card_path = "src/green_agent/card.toml"

[white_agent]
host = "0.0.0.0"
port = 8001
card_path = "white_agent/white_agent_card.toml"
model = "gpt-4o-mini"
max_iterations = 10
blocked_commands = []  # e.g., ["rm", "sudo"]

[evaluation]
task_ids = ["hello-world", "create-bucket"]  # Directory names from terminal-bench/tasks/
n_attempts = 1
n_concurrent_trials = 1
timeout_multiplier = 1.0
output_path = "./eval_results"
cleanup = true

[dataset]
name = "terminal-bench-core"
version = "head"

[logging]
level = "INFO"  # DEBUG, INFO, WARNING, ERROR
format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

[a2a]
message_timeout = 300.0
health_check_timeout = 5.0
```

### Agent Card Format

Both agent cards must follow this format:

```toml
name = "AgentName"
description = "What the agent does"
url = "http://localhost:PORT/"
version = "1.0.0"
defaultInputModes = ["text"]
defaultOutputModes = ["text"]

[capabilities]
streaming = true  # REQUIRED

[[skills]]  # Double brackets!
id = "skill_id"
name = "Skill Name"
description = "What this skill does"
```

**Common mistakes:** `[description]` section (wrong), `[skills]` (wrong), `streaming = false` (wrong).

## Building Your White Agent

Your agent must expose an A2A interface and execute terminal commands.

### 1. Implement A2A Interface

```python
from a2a.server.apps import A2AStarletteApplication
from a2a.server.agent_execution import AgentExecutor
from a2a.types import Part, TextPart, TaskState
from a2a.server.tasks import TaskUpdater
import uvicorn

class YourAgentExecutor(AgentExecutor):
    async def execute(self, context, event_queue):
        task = context.current_task
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # Get task instruction
        user_input = context.get_user_input()

        # Solve task (use your LLM + tools here)
        solution = await your_solve_function(user_input)

        # Return result
        await updater.add_artifact([Part(root=TextPart(text=solution))], name="response")
        await updater.complete()

# Create and run
app = A2AStarletteApplication(
    agent_card=AgentCard(**agent_card_data),
    http_handler=DefaultRequestHandler(
        agent_executor=YourAgentExecutor(),
        task_store=InMemoryTaskStore()
    )
).build()

uvicorn.run(app, host="0.0.0.0", port=8001)
```

### 2. Add Terminal Execution

Options:
- **MCP Server** - Connect to MCP server with terminal tools
- **Direct Implementation** - Execute commands via subprocess/docker exec
- **Hybrid** - Mix of both

Example with function calling:
```python
def execute_bash_command(command: str, container_name: str) -> dict:
    """Execute command in Docker container."""
    result = subprocess.run(
        ["docker", "exec", "-w", "/app", container_name, "bash", "-c", command],
        capture_output=True, text=True
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }
```

### 3. Handle Task Instructions

Terminal-bench sends instructions like:
```
You are being evaluated on Terminal-Bench.

TASK:
Create a file called hello.txt with "Hello, World!"

The container name is: terminal_bench_abc123
```

Your agent should:
1. Extract container name from instruction
2. Parse the task
3. Generate and execute commands
4. Verify success
5. Return completion status

## Configuration Reference

### All Settings

#### Green Agent
- `green_agent.host` - Host to bind (default: "0.0.0.0")
- `green_agent.port` - Server port (default: 9999)
- `green_agent.card_path` - Path to agent card

#### White Agent
- `white_agent.host` - Host to bind
- `white_agent.port` - Server port (default: 8001)
- `white_agent.card_path` - Path to agent card
- `white_agent.model` - LLM model 
- `white_agent.max_iterations` - Max iterations per task
- `white_agent.blocked_commands` - Commands to block for safety

#### Evaluation
- `evaluation.task_ids` - **REQUIRED** List of task directory names
- `evaluation.n_attempts` - Attempts per task
- `evaluation.n_concurrent_trials` - Concurrent trials
- `evaluation.timeout_multiplier` - Timeout multiplier
- `evaluation.output_path` - Results directory
- `evaluation.cleanup` - Cleanup Docker after eval

#### Dataset
- `dataset.name` - Dataset name (terminal-bench manages automatically)
- `dataset.version` - Dataset version

#### Logging
- `logging.level` - Log level
- `logging.format` - Log format string

#### A2A
- `a2a.message_timeout` - Message timeout (seconds)
- `a2a.health_check_timeout` - Health check timeout (seconds)

### Security

1. Never commit `.env` (already gitignored)
2. Rotate API keys regularly
3. Use `blocked_commands` to prevent dangerous operations

## Troubleshooting

### Configuration Issues

**Settings not loading?**
- Check `config.toml` is in project root
- Verify `.env` exists
- Check for syntax errors

**API key not found?**
- Ensure `.env` exists (copy from `.env.example`)
- Check exact key name (case-sensitive)
- Remove extra quotes/spaces

### Wrong A2A Package (Most Common!)

```bash
# If you see: ModuleNotFoundError: No module named 'a2a.server'
pip uninstall -y a2a
pip install a2a-sdk openai-agents

# Verify
python -c "from a2a.server.apps import A2AStarletteApplication; print('OK')"
```

**Note:** `a2a` (0.44) is a web scraper. You need `a2a-sdk` (0.3.x) for Agent-to-Agent protocol!

### Agent Card Validation

Check your `*.toml` files have:
```toml
description = "..."  # NOT [description] section
url = "http://localhost:PORT/"
streaming = true  # NOT false
[[skills]]  # Double brackets NOT [skills]
```

### Green Agent Issues

**Can't import terminal_bench**
```bash
pip install terminal-bench
terminal-bench datasets download --dataset terminal-bench-core
```

**Docker errors**
```bash
docker ps  # Ensure Docker is running
docker images | grep terminal-bench
```

### White Agent Issues

**Can't connect to white agent**
```bash
curl http://localhost:8001/agent/card  # Should return agent card
```

**Agent receives tasks but fails**
- Check agent logs for errors
- Verify agent has terminal execution tools
- Test manually with simple A2A messages

### Communication Issues

- Check both agents use compatible A2A versions
- Verify message structure matches A2A spec
- Check logs for detailed error messages

## Advanced Usage

### Custom Datasets

For custom terminal-bench datasets, modify the harness initialization in `src/green_agent/agent.py`. Standard datasets are managed automatically via `dataset.name` and `dataset.version`.

### Integration with AgentBeats

1. Wrap green agent with `AgentBeatsExecutor`
2. Add battle logging/tracking
3. Register as scenario in AgentBeats format

## Results

Results saved to `./eval_results/green_agent_eval_TIMESTAMP/`:
- `results.json` - Overall results
- `run_metadata.json` - Run configuration
- `task_id/` - Per-task results
  - `results.json` - Task results
  - `sessions/` - Terminal recordings
  - `agent_interaction.log` - Communication logs

## Next Steps

1. **Implement Real Agent** - Replace example with your agent
2. **Add Tools** - Implement terminal execution
3. **Test Full Dataset** - Run on complete terminal-bench
4. **Add Metrics** - Track custom metrics and logging
