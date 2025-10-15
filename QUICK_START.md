# Quick Start Guide

Get up and running in 5 minutes!

## Installation

```bash
cd terminal-bench-green-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (including correct a2a-sdk)
pip install -r requirements.txt

# Install terminal-bench
cd ../terminal-bench && pip install -e . && cd ../terminal-bench-green-agent
```

## Run Test Evaluation

### Terminal 1: Start White Agent

```bash
cd terminal-bench-green-agent
source venv/bin/activate  # Activate venv

# Start LLM-powered agent (uses GPT-4o-mini)
./scripts/start_white_agent.sh
# Or directly:
python -m white_agent --port 8001
```

### Terminal 2: Start Green Agent

```bash
cd terminal-bench-green-agent
source venv/bin/activate  # Activate venv

# Using helper script
./scripts/start_green_agent.sh
# Or directly:
python -m src.green_agent --port 9999
```

### Terminal 3: Run Kickoff

```bash
cd terminal-bench-green-agent
source venv/bin/activate  # Activate venv

# Using helper script
./scripts/run_eval.sh
# Or directly:
python -m src.kickoff
```

## Expected Output

### Terminal 1 (White Agent)

```
Starting White Agent...
Host: 0.0.0.0
Port: 8001
Mode: llm

Using LLM-powered agent (GPT-4o-mini)
Starting LLM-Powered White Agent on 0.0.0.0:8001
Using agent card: white_agent/white_agent_card.toml
Model: gpt-4o-mini

INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Terminal 2 (Green Agent)

```
Starting Terminal-Bench Green Agent on 0.0.0.0:9999
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:9999
```

### Terminal 3 (Kickoff)

```
Sending evaluation request to green agent at http://localhost:9999...
White agent being evaluated: http://localhost:8001
Tasks to run: ['hello-world', 'create-bucket', 'csv-to-parquet']

================================================================================
GREEN AGENT RESPONSE:
================================================================================
Received evaluation request. Parsing configuration...
Configuration parsed. Starting evaluation of agent at http://localhost:8001...

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

============================================================
```

**Note:** The LLM-powered agent can solve simple tasks like hello-world but may fail on complex tasks. This is expected! The infrastructure is working correctly.

## File Structure

```
terminal-bench-green-agent/
├── README.md                      # Overview
├── SETUP.md                       # Detailed setup guide
├── CONFIG.md                      # Configuration guide
├── QUICK_START.md                 # This file
│
├── requirements.txt               # Dependencies
├── config.toml                    # Settings
├── .env.example                   # Env template
│
├── src/                          # Source code
│   ├── kickoff.py                # Kickoff script
│   ├── config/                   # Config management
│   ├── green_agent/              # Green agent
│   ├── adapters/                 # A2A adapter
│   └── utils/                    # A2A client
│
├── white_agent/                  # White agent
│   ├── llm_white_agent.py        # LLM agent
│   └── white_agent_card.toml     # Agent card
│
├── scripts/                      # Helper scripts
│   ├── start_green_agent.sh
│   ├── start_white_agent.sh
│   ├── run_eval.sh
│   └── check_docker.sh
│
└── eval_results/                 # Results
```

## Common Commands

### Check Agent Health

```bash
# Check white agent
curl http://localhost:8001/agent/card

# Check green agent
curl http://localhost:9999/agent/card
```

### View Results

```bash
# List evaluation runs
ls eval_results/

# View latest results
cat eval_results/green_agent_eval_*/results.json

# View specific task
cat eval_results/green_agent_eval_*/task_001/*/results.json
```

### Run Specific Tasks

Edit `config.toml`:

```toml
[evaluation]
task_ids = [
    "hello-world",       # Simple file creation
    "create-bucket",     # AWS S3 bucket
    "csv-to-parquet",    # Data conversion
]

[dataset]
path = "../terminal-bench/tasks"  # Use local tasks
```

Or set via environment variable:

```bash
export EVALUATION_TASK_IDS="hello-world,csv-to-parquet,create-bucket"
export DATASET_PATH="../terminal-bench/tasks"
```

**Important:** Task IDs are directory names from `terminal-bench/tasks/`, not numbers.

### Change Agent Being Evaluated

Edit `config.toml`:

```toml
[white_agent]
port = 8001  # Or your agent's port
```

Or set in `.env`:

```bash
WHITE_AGENT_URL="http://your-agent:8001"
```

## Troubleshooting

### Problem: ModuleNotFoundError: No module named 'a2a.server'

```bash
# You have the wrong a2a package! Uninstall and install correct one:
pip uninstall -y a2a
pip install a2a-sdk openai-agents
```

**Note:** Make sure you have `a2a-sdk` (not `a2a`). The `a2a` package is a web scraper, not the Agent-to-Agent protocol!

### Problem: Can't import terminal_bench

```bash
cd ../terminal-bench
pip install -e .
```

### Problem: Agent card validation errors

Make sure your agent card TOML files have:

- `streaming = true` in `[capabilities]`
- `url = "http://localhost:PORT/"` at top level
- `defaultInputModes = ["text"]` and `defaultOutputModes = ["text"]`
- `[[skills]]` sections (double brackets!) not `[skills]`

### Problem: Docker errors

```bash
# Make sure Docker is running
docker ps

# Check Docker images
docker images | grep terminal-bench
```

### Problem: Port already in use

```bash
# Change ports in commands:
python example_white_agent.py --port 8002  # Use 8002 instead
python green_agent.py --port 9998          # Use 9998 instead

# Update kickoff script:
task_config = {
    "white_agent_url": "http://localhost:8002",  # Match new port
}
green_agent_url = "http://localhost:9998"        # Match new port
```

### Problem: Agent times out

Edit `config.toml`:

```toml
[evaluation]
timeout_multiplier = 2.0  # Double the timeout
```

Or set environment variable:

```bash
export EVALUATION_TIMEOUT_MULTIPLIER=2.0
```

### Problem: Missing OpenAI API key

```bash
# Copy .env.example to .env
cp .env.example .env

# Edit .env and add your API key
# OPENAI_API_KEY="sk-your-key-here"
```

## Next Steps

1. **Build Real White Agent**: Replace example with your actual agent

   - See `SETUP.md` → "Building Your White Agent"
   - Add terminal execution tools
   - Integrate with LLM

2. **Run Full Evaluation**: Test on complete dataset

   ```toml
   # In config.toml, comment out or remove task_ids to run all tasks
   [evaluation]
   # task_ids = ["hello-world"]  # Comment this out to run all tasks
   ```

3. **Integrate with AgentBeats**: Connect to evaluation platform
   - See `SETUP.md` → "Integration with AgentBeats"

## Architecture at a Glance

```
Kickoff Script ──[A2A]──> Green Agent ──[Harness]──> A2A Adapter ──[A2A]──> White Agent
(src/kickoff.py)          (port 9999)                                         (port 8001)

What each does:
- Kickoff: Sends evaluation config
- Green: Runs terminal-bench harness
- Adapter: Translates BaseAgent ↔ A2A protocol
- White: Executes bash commands to solve tasks (LLM-powered)
```

## Key Files to Edit

### For Configuration

- `config.toml` - Task IDs, ports, paths, evaluation settings
- `.env` - API keys, secrets, agent URLs (copy from `.env.example`)
- `src/kickoff.py` - Now loads config automatically (no need to edit!)

### For Implementation

- `white_agent/llm_white_agent.py` - LLM-powered agent
- `src/adapters/a2a_white_agent.py` - Task formatting (optional)

### For Understanding

- `SETUP.md` - Complete setup guide
- `CONFIG.md` - Configuration details
- `README.md` - Project overview
- `ARCHITECTURE.txt` - Visual architecture diagram

## Resources

- Terminal-Bench: `/Users/edison/Desktop/dev/green_agent/terminal-bench/`
- AgentBeats Examples: `/Users/edison/Desktop/dev/green_agent/agentbeats/scenarios/`
- A2A Protocol: https://github.com/google/a2a

## Success Checklist

- [ ] Both agents start without errors
- [ ] Can curl agent cards
- [ ] Kickoff script receives response
- [ ] Results directory is created
- [ ] Can view results.json

If all checked, you're ready to build your real agent! 🚀
