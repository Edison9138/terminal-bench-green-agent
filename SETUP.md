# Setup Guide for Terminal-Bench Green Agent

This guide will help you set up and run the terminal-bench green agent evaluation system.

## Overview

The system has three components:

1. **Green Agent** (Evaluator) - Runs terminal-bench harness and evaluates white agents
2. **White Agent** (Subject) - The agent being evaluated
3. **Kickoff Script** - Sends evaluation requests to the green agent

## Prerequisites

- Python 3.10+
- Docker (required by terminal-bench for task environments)
- Terminal-bench installed

## Installation

### Step 1: Install Dependencies

```bash
cd terminal-bench-green-agent

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install terminal-bench (from parent directory)
cd ../terminal-bench
pip install -e .
cd ../terminal-bench-green-agent
```

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY="sk-your-actual-key-here"
```

Optionally customize `config.toml` for ports, paths, and other settings.

### Step 3: Verify Terminal-Bench Installation

```bash
# Test that terminal-bench is available
terminal-bench --help
```

## Quick Start

### Option A: Test with LLM-Powered White Agent

This uses the included LLM-powered white agent (GPT-4o-mini) for realistic testing.

```bash
# Terminal 1: Start the LLM white agent
./scripts/start_white_agent.sh
# Or directly:
python -m white_agent --port 8001

# Terminal 2: Start the green agent
./scripts/start_green_agent.sh
# Or directly:
python -m src.green_agent --port 9999

# Terminal 3: Run the kickoff script
./scripts/run_eval.sh
# Or directly:
python -m src.kickoff
```

**Note:** Requires `OPENAI_API_KEY` in `.env` file.

### Option B: Test with Your Own White Agent

If you have your own A2A-compatible agent:

```bash
# Terminal 1: Start your white agent
python your_white_agent.py --port 8001

# Terminal 2: Start the green agent
./scripts/start_green_agent.sh

# Terminal 3: Configure evaluation in config.toml
# Edit config.toml:
#   - Set task_ids to the tasks you want to run
#   - Set white_agent URL/port if needed
#   - Adjust other parameters as needed

./scripts/run_eval.sh
```

## Configuration

### Task Configuration

Edit `config.toml` to configure the evaluation:

```toml
# Terminal-Bench Evaluation Settings
[evaluation]
# Task IDs are actual directory names from terminal-bench/tasks/
task_ids = [                             # REQUIRED - List of tasks to evaluate
    "hello-world",                       # Simple file creation
    "create-bucket",                     # AWS S3 bucket creation
    "csv-to-parquet",                    # Data format conversion
]
n_attempts = 1                           # Optional: default 1 - Attempts per task
n_concurrent_trials = 1                  # Optional: default 1 - Parallel execution
timeout_multiplier = 1.0                 # Optional: default 1.0 - Timeout adjustment

# Dataset Settings
[dataset]
path = "../terminal-bench/tasks"        # REQUIRED - Path to local dataset

# White Agent Settings
[white_agent]
port = 8001                              # Optional: default 8001 - Port where agent is running
card_path = "white_agent/white_agent_card.toml"  # REQUIRED
execution_root = "."                     # REQUIRED - Command execution directory
model = "gpt-4o-mini"                    # REQUIRED - LLM model to use
```

**Important Notes:**

- **REQUIRED fields**: Must be explicitly set - the app will fail with helpful errors if missing
- **Task IDs**: Use actual directory names from `terminal-bench/tasks/`, not numbers
- **Dataset**: Must specify `dataset.path` for local tasks
- You can override any setting with environment variables (see CONFIG.md)

### Environment Configuration

See [CONFIG.md](CONFIG.md) for full details. Key settings:

**`.env` file** (copy from `.env.example`):

```bash
OPENAI_API_KEY="sk-your-key-here"  # Required for LLM agent
WHITE_AGENT_URL="http://localhost:8001"  # Optional override
LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
```

**`config.toml` file**:

```toml
[green_agent]
port = 9999
host = "0.0.0.0"

[white_agent]
port = 8001                                      # Optional: default 8001
host = "0.0.0.0"                                 # Optional: default 0.0.0.0
card_path = "white_agent/white_agent_card.toml" # REQUIRED
execution_root = "."                             # REQUIRED
model = "gpt-4o-mini"                            # REQUIRED

[evaluation]
task_ids = ["hello-world"]         # REQUIRED - Tasks to run
n_attempts = 1                      # Optional: default 1
timeout_multiplier = 1.0            # Optional: default 1.0
output_path = "eval_results"        # Optional: default ./eval_results

[dataset]
path = "../terminal-bench/tasks"   # REQUIRED - Local dataset path
```

### Agent Configuration

#### Agent Card Format (CRITICAL!)

Both green and white agent cards MUST follow this format:

```toml
name = "YourAgentName"
description = """
Your agent description here...
"""
url = "http://localhost:PORT/"  # Required!
version = "1.0.0"

defaultInputModes = ["text"]    # Required!
defaultOutputModes = ["text"]   # Required!

[capabilities]
streaming = true  # MUST be true for A2A streaming to work!

[[skills]]  # Double brackets! Not [skills]
id = "skill_id"
name = "Skill Name"
description = "What this skill does"
tags = ["tag1", "tag2"]
```

**Common Mistakes:**

- ❌ `[description]` section with `short` and `long` → ✅ Use top-level `description = "..."`
- ❌ `[skills]` → ✅ Use `[[skills]]` (double brackets, array of tables)
- ❌ `streaming = false` → ✅ Use `streaming = true`
- ❌ Missing `url`, `defaultInputModes`, `defaultOutputModes` → ✅ Add them!

#### Green Agent (`green_agent_card.toml`)

- Evaluator agent configuration
- Runs on port 9999 by default
- Has evaluation and reporting skills

#### White Agent (`example_white_agent_card.toml` or your own)

- Agent being evaluated configuration
- Runs on port 8001 by default
- Should have task-solving skills

## Architecture Details

### How It Works

```
┌──────────────────┐
│ Kickoff Script   │
│                  │ 1. Sends task config
└────────┬─────────┘
         │ HTTP POST (A2A message)
         │ to http://localhost:9999
         ▼
┌──────────────────┐
│  Green Agent     │
│  (Evaluator)     │ 2. Receives config
│                  │ 3. Initializes terminal-bench harness
│                  │ 4. Loads tasks from dataset
└────────┬─────────┘
         │ For each task:
         │   a. Create Docker environment
         │   b. Send task to white agent
         │   c. Collect response
         │   d. Run tests
         │   e. Score results
         │
         │ HTTP POST (A2A message)
         │ to http://localhost:8001
         ▼
┌──────────────────┐
│  White Agent     │
│  (Subject)       │ 5. Receives task instruction
│                  │ 6. Solves task (executes commands)
│                  │ 7. Returns solution
└──────────────────┘
```

### Components

#### 1. Green Agent (`green_agent.py`)

The green agent is a special evaluator agent that:

- Exposes an A2A interface (can receive messages from kickoff script)
- Internally runs the terminal-bench harness
- Uses `A2AWhiteAgent` adapter to communicate with the white agent
- Collects and reports results

**Key Classes:**

- `TerminalBenchGreenAgentExecutor`: Main executor that runs evaluations
- Methods:
  - `parse_task_config()`: Extracts config from incoming message
  - `run_terminal_bench_evaluation()`: Runs the harness
  - `format_results_message()`: Formats results for output

#### 2. A2A White Agent Adapter (`a2a_white_agent.py`)

This is the bridge between terminal-bench and A2A agents:

- Implements terminal-bench's `BaseAgent` interface
- Communicates with white agent via A2A protocol
- Translates terminal-bench task instructions to A2A messages
- Handles responses and reports results back to harness

**Key Class:**

- `A2AWhiteAgent`: Adapter class
- Methods:
  - `perform_task()`: Main entry point called by terminal-bench
  - `_send_to_agent_async()`: Sends A2A message to white agent
  - `_format_task_instruction()`: Formats task for white agent

#### 3. A2A Client (`utils/a2a_client.py`)

Helper utilities for A2A communication:

- `send_message_to_agent()`: Send message to A2A agent
- `check_agent_health()`: Check if agent is responding
- `get_agent_card()`: Retrieve agent card

#### 4. Kickoff Script (`kickoff_terminal_bench.py`)

Initiates the evaluation:

- Defines task configuration
- Sends evaluation request to green agent
- Displays results

## Building Your White Agent

To create a white agent that can be evaluated:

### 1. Implement A2A Interface

Your white agent must expose an A2A interface. You can use:

- **OpenAI Agents SDK** (as shown in your screenshot)
- **AgentBeats SDK**
- **Custom A2A implementation**

Example structure:

```python
from a2a.server.apps import A2AStarletteApplication
from a2a.server.agent_execution import AgentExecutor

class YourAgentExecutor(AgentExecutor):
    async def execute(self, context, event_queue):
        # 1. Get task instruction
        task_instruction = context.get_user_input()

        # 2. Use your LLM/framework to solve it
        solution = await your_agent_solve(task_instruction)

        # 3. Return result
        await updater.add_artifact([Part(root=TextPart(text=solution))], name="response")
        await updater.complete()

# Create A2A app and run
app = A2AStarletteApplication(...)
uvicorn.run(app, host="0.0.0.0", port=8001)
```

### 2. Add Terminal Execution Capability

Your agent needs to execute terminal commands. Options:

**Option A: Use MCP (Model Context Protocol)**

- Connect to an MCP server that provides terminal tools
- Agent calls tools via function calling

**Option B: Custom Tools**

- Implement terminal execution tools directly
- Register with your agent framework

**Option C: Hybrid**

- Mix of MCP and custom tools

Example with OpenAI Agents SDK (from your screenshot):

```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# Define terminal tool
def execute_terminal_command(command: str) -> dict:
    """Execute a terminal command and return output."""
    # Your implementation here
    return {"terminal_output": output, "asciinema_url": url}

# Create agent with tool
root_agent = Agent(
    name="terminal_agent",
    model=LiteLlm(model="openai/gpt-4o"),
    instructions="You are a helpful assistant that can execute terminal commands.",
    tools=[execute_terminal_command],
)

# Make it A2A compatible
from google.adk.a2a.utils.agent_to_a2a import to_a2a
a2a_app = to_a2a(root_agent, port=8001)
```

### 3. Handle Task Instructions

Terminal-bench sends task instructions like:

```
You are being evaluated on the Terminal-Bench benchmark.

TASK:
Create a file called hello.txt with the content "Hello, World!"

You have access to a terminal session where you can execute commands...
```

Your agent should:

1. Parse the task
2. Determine required commands
3. Execute them
4. Verify success
5. Return completion status

## Troubleshooting

### Critical: Wrong A2A Package (Most Common Error!)

**Problem:** `ModuleNotFoundError: No module named 'a2a.server'`

This means you have the WRONG `a2a` package installed! There are two packages:

- ❌ `a2a` (0.44) - A web scraping library (WRONG!)
- ✅ `a2a-sdk` (0.3.x) - Agent-to-Agent protocol (CORRECT!)

**Solution:**

```bash
# Check what you have
pip list | grep a2a

# If you see "a2a 0.44", uninstall and install correct one:
pip uninstall -y a2a
pip install a2a-sdk openai-agents

# Verify
python -c "from a2a.server.apps import A2AStarletteApplication; print('✓ OK')"
```

### Agent Card Validation Errors

**Problem:** `ValidationError` when loading agent card

**Solution:** Check your `*.toml` files have the correct format:

```toml
name = "AgentName"
description = "Description here"  # NOT [description] section!
url = "http://localhost:PORT/"
version = "1.0.0"
defaultInputModes = ["text"]
defaultOutputModes = ["text"]

[capabilities]
streaming = true  # MUST be true!

[[skills]]  # Double brackets!
id = "skill1"
...
```

### Green Agent Issues

**Problem:** Green agent can't import terminal_bench

```bash
# Solution: Make sure terminal-bench is installed
cd ../terminal-bench
pip install -e .
```

**Problem:** Docker errors when running tasks

```bash
# Solution: Make sure Docker is running
docker ps

# Check terminal-bench Docker images
docker images | grep terminal-bench
```

### White Agent Issues

**Problem:** Green agent can't connect to white agent

```bash
# Solution: Check white agent is running and accessible
curl http://localhost:8001/agent/card

# Check firewall/port settings
```

**Problem:** White agent receives tasks but fails

- Check agent logs for errors
- Verify agent has necessary tools/capabilities
- Test agent manually first with simple A2A messages

### Communication Issues

**Problem:** A2A message format errors

- Check that both agents are using compatible A2A versions
- Verify message structure matches A2A spec
- Check logs for detailed error messages

## Advanced Usage

### Custom Datasets

To evaluate on custom terminal-bench datasets, edit `config.toml`:

```toml
[dataset]
path = "/path/to/custom/dataset"  # REQUIRED - Custom dataset location

[evaluation]
task_ids = ["task1", "task2"]  # Custom task IDs
```

Or use environment variables:

```bash
export DATASET_PATH="/path/to/custom/dataset"
export EVALUATION_TASK_IDS="task1,task2"
```

### Multiple Evaluation Runs

To run multiple evaluations with different configurations:

```bash
# Run 1: First set of tasks
export EVALUATION_TASK_IDS="hello-world,csv-to-parquet"
python -m src.kickoff

# Run 2: Different set of tasks
export EVALUATION_TASK_IDS="create-bucket,other-task"
python -m src.kickoff
```

Or modify `config.toml` between runs and re-run the kickoff script.

### Integration with AgentBeats

To integrate with the AgentBeats platform:

1. Wrap green agent with `AgentBeatsExecutor`
2. Add battle logging
3. Register as a scenario in AgentBeats

See `agentbeats/scenarios/` for examples.

## Results

Results are saved to `./eval_results/green_agent_eval_TIMESTAMP/`:

- `results.json` - Overall results
- `run_metadata.json` - Run configuration and metadata
- `task_id/` - Per-task results
  - `results.json` - Task results
  - `sessions/` - Terminal session recordings
  - `agent_interaction.log` - Agent communication logs

## Next Steps

1. **Implement a Real White Agent**: Replace the example with your actual agent
2. **Add Tools**: Implement terminal execution tools
3. **Test on Full Dataset**: Run on complete terminal-bench
4. **Integrate with AgentBeats**: Connect to the evaluation platform
5. **Add Metrics**: Track custom metrics and logging

## Support

For questions or issues:

- Check terminal-bench documentation
- Review A2A protocol specifications
- See example implementations in `agentbeats/scenarios/`
