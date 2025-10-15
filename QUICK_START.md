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
python example_white_agent.py --port 8001
```

### Terminal 2: Start Green Agent

```bash
cd terminal-bench-green-agent
source venv/bin/activate  # Activate venv
python green_agent.py --port 9999
```

### Terminal 3: Run Kickoff

```bash
cd terminal-bench-green-agent
source venv/bin/activate  # Activate venv
python kickoff_terminal_bench.py
```

## Expected Output

### Terminal 1 (White Agent)

```
Starting Example White Agent on 0.0.0.0:8001
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
Tasks to run: ['accelerate-maximal-square', 'acl-permissions-inheritance']

================================================================================
GREEN AGENT RESPONSE:
================================================================================
Received evaluation request. Parsing configuration...
Configuration parsed. Starting evaluation of agent at http://localhost:8001...

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

============================================================
```

**Note:** Tasks fail because the example white agent is just a stub. This is expected! The infrastructure is working correctly.

## File Structure

```
terminal-bench-green-agent/
├── README.md                      # Overview
├── SETUP.md                       # Detailed setup guide
├── UNDERSTANDING.md               # Architecture explanation
├── QUICK_START.md                 # This file
│
├── kickoff_terminal_bench.py      # Start evaluation
├── green_agent.py                 # Evaluator agent
├── green_agent_card.toml          # Green agent config
│
├── a2a_white_agent.py            # Terminal-bench ↔ A2A adapter
│
├── example_white_agent.py         # Simple test agent
├── example_white_agent_card.toml  # Test agent config
│
├── utils/
│   ├── __init__.py
│   └── a2a_client.py             # A2A communication helpers
│
└── requirements.txt               # Dependencies
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

Edit `kickoff_terminal_bench.py`:

```python
task_config = {
    "dataset_path": "../terminal-bench/tasks",  # Use local tasks
    "task_ids": [
        "accelerate-maximal-square",
        "acl-permissions-inheritance",
    ],  # Actual task directory names
    ...
}
```

**Important:** Task IDs are directory names from `terminal-bench/tasks/`, not numbers.

### Change Agent Being Evaluated

Edit `kickoff_terminal_bench.py`:

```python
task_config = {
    "white_agent_url": "http://your-agent:8001",  # Your agent URL
    ...
}
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

Edit `kickoff_terminal_bench.py`:

```python
task_config = {
    "timeout_multiplier": 2.0,  # Double the timeout
}
```

## Next Steps

1. **Build Real White Agent**: Replace example with your actual agent

   - See `SETUP.md` → "Building Your White Agent"
   - Add terminal execution tools
   - Integrate with LLM

2. **Run Full Evaluation**: Test on complete dataset

   ```python
   task_config = {
       "task_ids": None,  # Run all tasks
   }
   ```

3. **Integrate with AgentBeats**: Connect to evaluation platform
   - See `SETUP.md` → "Integration with AgentBeats"

## Architecture at a Glance

```
Kickoff Script ──[A2A]──> Green Agent ──[Harness]──> A2A Adapter ──[A2A]──> White Agent
(port any)               (port 9999)                                         (port 8001)

What each does:
- Kickoff: Sends config
- Green: Runs terminal-bench harness
- Adapter: Translates BaseAgent ↔ A2A
- White: Solves tasks
```

## Key Files to Edit

### For Configuration

- `kickoff_terminal_bench.py` - Change tasks, agent URL, timeouts

### For Implementation

- `example_white_agent.py` - Replace with your agent
- `a2a_white_agent.py` - Customize task formatting (optional)

### For Understanding

- `SETUP.md` - Complete setup guide
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
