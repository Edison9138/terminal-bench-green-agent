# Terminal-Bench Green Agent

This is a "green agent" that evaluates other agents' capabilities on the terminal-bench benchmark.

## Architecture

```
┌─────────────────────┐
│  Kickoff Script     │  Sends terminal-bench config to green agent
│                     │
└──────────┬──────────┘
           │ HTTP POST to green agent (port 9999)
           │ Message: task config (env, model, task_ids, etc.)
           ▼
┌─────────────────────┐
│  Green Agent        │  Runs terminal-bench harness
│  (Evaluator)        │  - Loads tasks from terminal-bench
│                     │  - Spins up Docker environments
│                     │  - Executes white agent via A2A adapter
│                     │  - Runs tests & collects results
└──────────┬──────────┘
           │ A2A protocol (port 8001)
           │ Sends task instructions
           ▼
┌─────────────────────┐
│  White Agent        │  Agent being tested
│  (Subject)          │  - Receives task instructions via A2A
│                     │  - Executes terminal commands
│                     │  - Returns completion status
└─────────────────────┘
```

## Components

### 1. Kickoff Script (`kickoff_terminal_bench.py`)

- Sends terminal-bench configuration to green agent
- Config includes: dataset, task_ids, white agent URL, model settings

### 2. Green Agent (`green_agent.py`)

- Receives eval request via A2A
- Runs terminal-bench harness internally
- Uses custom A2A-based white agent adapter
- Returns evaluation results

### 3. White Agent (separate process)

- Can be any A2A-compatible agent
- Implements agent logic using any framework (ADK, LangChain, custom, etc.)
- Exposes A2A interface on specified port

### 4. A2A White Agent Adapter (`a2a_white_agent.py`)

- Bridges terminal-bench's BaseAgent interface to A2A protocol
- Translates terminal-bench instructions to A2A messages
- Handles terminal session coordination

## Quick Start

### Installation

```bash
cd terminal-bench-green-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies (includes a2a-sdk, NOT a2a!)
pip install -r requirements.txt

# Install terminal-bench
cd ../terminal-bench && pip install -e . && cd ../terminal-bench-green-agent
```

### Run Evaluation

#### Terminal 1: Start White Agent

```bash
cd terminal-bench-green-agent
source venv/bin/activate

# Option 1: Using helper script (LLM-powered agent)
./scripts/start_white_agent.sh

# Option 2: Using simple heuristic agent
./scripts/start_white_agent.sh 8001 0.0.0.0 simple

# Option 3: Direct Python execution
python -m white_agent --port 8001  # LLM-powered (default)
python -m white_agent --simple --port 8001  # Simple agent
```

#### Terminal 2: Start Green Agent

```bash
cd terminal-bench-green-agent
source venv/bin/activate
# Option 1: Using helper script
./scripts/start_green_agent.sh

# Option 2: Direct Python execution
python -m src.green_agent --port 9999
```

#### Terminal 3: Run Kickoff Script

```bash
cd terminal-bench-green-agent
source venv/bin/activate

# Option 1: Using helper script
./scripts/run_eval.sh

# Option 2: Direct Python execution
python -m src.kickoff
# or simply
python -m src
```

### Expected Output

```
Terminal-Bench Evaluation Results
=====================================
Agent Under Test: http://localhost:8001
Dataset: terminal-bench
Tasks Evaluated: 3

Overall Performance:
- Accuracy: 33.33%
- Resolved: 1/3
- Unresolved: 2/3

Task Results:
------------------------------------------------------------
✓ PASS - hello-world
      Tokens: 197 in, 63 out
✗ FAIL - create-bucket
      Failure Mode: unset
      Tokens: 202 in, 200 out
✗ FAIL - csv-to-parquet
      Failure Mode: unset
      Tokens: 213 in, 21 out
```

**Note:** The LLM-powered white agent can solve simple tasks but may fail on complex ones due to iteration limits or error recovery issues. This is expected behavior for the example implementation!

## File Structure

```
terminal-bench-green-agent/
├── README.md                       # This file
├── QUICK_START.md                  # Quick start guide
├── SETUP.md                        # Detailed setup instructions
├── CONFIG.md                       # Configuration guide
├── ARCHITECTURE.txt                # Architecture diagram
│
├── requirements.txt                # Python dependencies
├── config.toml                     # Configuration settings
├── .env.example                    # Environment variable template
│
├── src/                           # Source code
│   ├── __init__.py
│   ├── __main__.py                # Module entry point (runs kickoff)
│   ├── kickoff.py                 # Kickoff script logic
│   │
│   ├── config/                   # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py           # Settings loader (TOML + env)
│   │
│   ├── green_agent/              # Green agent (evaluator)
│   │   ├── __init__.py
│   │   ├── __main__.py           # Green agent entry point
│   │   ├── agent.py              # Main green agent code
│   │   └── card.toml             # Green agent A2A card
│   │
│   ├── adapters/                 # Protocol adapters
│   │   ├── __init__.py
│   │   └── a2a_white_agent.py    # A2A adapter for terminal-bench
│   │
│   └── utils/                    # Shared utilities
│       ├── __init__.py
│       └── a2a_client.py         # A2A client utilities
│
├── white_agent/                  # White agent implementations
│   ├── __init__.py
│   ├── __main__.py               # White agent entry point
│   ├── white_agent.py            # Simple heuristic-based agent
│   ├── llm_white_agent.py        # LLM-powered agent (GPT-4o-mini)
│   └── white_agent_card.toml     # White agent A2A card
│
├── scripts/                      # Helper scripts
│   ├── start_green_agent.sh      # Start green agent
│   ├── start_white_agent.sh      # Start white agent (LLM or simple)
│   ├── run_eval.sh               # Run evaluation
│   └── check_docker.sh           # Docker environment checker
│
├── tests/                        # Unit tests
│   └── __init__.py
│
└── eval_results/                 # Evaluation results (generated)
    └── green_agent_eval_*/       # Timestamped evaluation runs
        ├── results.json          # Overall results
        ├── run_metadata.json     # Run metadata
        ├── run.log               # Execution log
        └── task_id/              # Per-task results
            └── trial_name/
                ├── results.json
                ├── agent-logs/
                └── sessions/
```

## Configuration

### Quick Config (`src/kickoff.py`)

Edit the task configuration to customize evaluation:

```python
task_config = {
    "dataset_path": "../terminal-bench/tasks",  # Local tasks
    "task_ids": [
        "hello-world",        # Simple file creation
        "create-bucket",      # AWS S3 bucket creation
        "csv-to-parquet",     # Data format conversion
    ],
    "white_agent_url": "http://localhost:8001",
    "n_attempts": 1,
    "n_concurrent_trials": 1,
    "timeout_multiplier": 1.0,
}
```

**Important:** Task IDs are directory names from `terminal-bench/tasks/`, not numbers!

### Full Config (`config.toml` and `.env`)

See [CONFIG.md](CONFIG.md) for details on:
- Environment variables (API keys, URLs)
- Agent ports and hosts
- Evaluation settings
- Logging configuration

## Common Issues

### Wrong A2A Package

```bash
# If you see: ModuleNotFoundError: No module named 'a2a.server'
pip uninstall -y a2a
pip install a2a-sdk openai-agents
```

### Agent Card Errors

Agent cards must have:

- `streaming = true` in `[capabilities]`
- `url = "http://localhost:PORT/"`
- `defaultInputModes = ["text"]` and `defaultOutputModes = ["text"]`
- `[[skills]]` (double brackets!) not `[skills]`

See `SETUP.md` for detailed troubleshooting.

## Next Steps

1. **Build Real White Agent** - Replace `white_agent/white_agent.py` with actual agent
2. **Add Terminal Tools** - Implement command execution capabilities
3. **Run Full Evaluation** - Test on complete terminal-bench dataset
4. **Integrate with AgentBeats** - Connect to evaluation platform

## Development Commands

```bash
# Start green agent
python -m src.green_agent --port 9999
# Or use helper script
./scripts/start_green_agent.sh

# Start white agent (LLM-powered)
python -m white_agent --port 8001
# Or use helper script
./scripts/start_white_agent.sh

# Start white agent (simple heuristic-based)
python -m white_agent --simple --port 8001
# Or use helper script with mode argument
./scripts/start_white_agent.sh 8001 0.0.0.0 simple

# Run evaluation
python -m src.kickoff
# Or use helper script
./scripts/run_eval.sh

# Check Docker environment
./scripts/check_docker.sh

# Run tests (when available)
pytest tests/

# Import modules in your code
from src.green_agent.agent import TerminalBenchGreenAgentExecutor
from src.adapters.a2a_white_agent import A2AWhiteAgent
from src.utils.a2a_client import send_message_to_agent
from src.config import settings
```

## Documentation

- **QUICK_START.md** - Get running in 5 minutes
- **SETUP.md** - Complete setup and configuration guide
- **CONFIG.md** - Configuration management (TOML + env variables)
- **ARCHITECTURE.txt** - Visual architecture diagram
- **TROUBLESHOOTING.md** - Common issues and solutions (see eval_results for debugging)

## Key Differences from AgentBeats Integration

This green agent is standalone and uses terminal-bench directly.
For AgentBeats integration, you would:

1. Wrap this green agent with AgentBeats executor
2. Add battle logging/tracking
3. Register scenarios in AgentBeats format
