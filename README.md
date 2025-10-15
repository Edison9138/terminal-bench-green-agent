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
# Option 1: Using helper script
./scripts/start_white_agent.sh

# Option 2: Direct Python execution
python -m white_agent --port 8001
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
python -m src
```

### Expected Output

```
Terminal-Bench Evaluation Results
=====================================
Agent Under Test: http://localhost:8001
Dataset: terminal-bench
Tasks Evaluated: 2

Overall Performance:
- Accuracy: 0.00%
- Resolved: 0/2
- Unresolved: 2/2

Task Results:
------------------------------------------------------------
✗ FAIL - accelerate-maximal-square
      Failure Mode: unknown_agent_error
✗ FAIL - acl-permissions-inheritance
      Failure Mode: unknown_agent_error
```

**Note:** Tasks fail because the example white agent is just a stub. The infrastructure works correctly!

## File Structure

```
terminal-bench-green-agent/
├── README.md                       # This file
├── QUICK_START.md                  # Quick start guide
├── SETUP.md                        # Detailed setup instructions
├── ARCHITECTURE.txt                # Architecture diagram
│
├── requirements.txt                # Python dependencies
│
├── src/                           # Source code
│   ├── __init__.py
│   ├── __main__.py                # Kickoff entry point
│   ├── kickoff.py                 # Kickoff script logic
│   │
│   ├── green_agent/              # Green agent (evaluator)
│   │   ├── __init__.py
│   │   ├── __main__.py
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
├── white_agent/                  # Example white agent
│   ├── __init__.py
│   ├── __main__.py
│   ├── white_agent.py            # Example white agent (for testing)
│   └── white_agent_card.toml     # Example agent card
│
├── scripts/                      # Helper scripts
│   ├── start_green_agent.sh      # Start green agent
│   ├── start_white_agent.sh      # Start white agent
│   └── run_eval.sh               # Run evaluation
│
├── tests/                        # Unit tests
│   └── __init__.py
│
└── eval_results/                 # Evaluation results (generated)
```

## Configuration

Edit `src/kickoff.py` to customize evaluation:

```python
task_config = {
    "dataset_path": "../terminal-bench/tasks",  # Local tasks
    "task_ids": [
        "accelerate-maximal-square",  # Actual directory names
        "acl-permissions-inheritance",
    ],
    "white_agent_url": "http://localhost:8001",
    "n_attempts": 1,
    "n_concurrent_trials": 1,
    "timeout_multiplier": 1.0,
}
```

**Important:** Task IDs are directory names from `terminal-bench/tasks/`, not numbers!

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

# Start white agent
python -m white_agent --port 8001
# Or use helper script
./scripts/start_white_agent.sh

# Run evaluation
python -m src
# Or use helper script
./scripts/run_eval.sh

# Run tests (when available)
pytest tests/

# Import modules in your code
from src.green_agent import TerminalBenchGreenAgentExecutor
from src.adapters import A2AWhiteAgent
from src.utils import send_message_to_agent
```

## Documentation

- **QUICK_START.md** - Get running in 5 minutes
- **SETUP.md** - Complete setup and configuration guide
- **ARCHITECTURE.txt** - Visual architecture diagram

## Key Differences from AgentBeats Integration

This green agent is standalone and uses terminal-bench directly.
For AgentBeats integration, you would:

1. Wrap this green agent with AgentBeats executor
2. Add battle logging/tracking
3. Register scenarios in AgentBeats format
