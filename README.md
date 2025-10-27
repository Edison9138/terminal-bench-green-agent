# Terminal-Bench Green Agent

A green agent that evaluates other agents' capabilities on the terminal-bench benchmark using the A2A protocol.

## Architecture

```
Kickoff Script ──[A2A]──> Green Agent ──[terminal-bench]──> A2A Adapter ──[A2A]──> White Agent
(src/kickoff.py)          (port 9999)                       (translates)          (port 8001)
```

**Flow:**
1. Kickoff sends task config to green agent via A2A
2. Green agent runs terminal-bench harness
3. Harness uses A2A adapter to communicate with white agent
4. White agent solves tasks and returns results
5. Green agent collects results and reports back

## Quick Start

### 1. Install

```bash
# Setup environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install terminal-bench
pip install terminal-bench

# Download dataset
terminal-bench datasets download --dataset terminal-bench-core

# Configure API key
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY="sk-your-key"
```

### 2. Run Evaluation

Start three terminals:

```bash
# Terminal 1: Start white agent
./scripts/start_white_agent.sh

# Terminal 2: Start green agent
./scripts/start_green_agent.sh

# Terminal 3: Run evaluation
./scripts/run_eval.sh
```

### 3. Verify Setup

- [ ] Both agents start without errors
- [ ] `curl http://localhost:8001/agent/card` returns agent card
- [ ] Evaluation completes and shows results
- [ ] `ls eval_results/` shows results directory

## Configuration

Edit `config.toml` for your evaluation:

```toml
[white_agent]
model = "gpt-4o-mini"
max_iterations = 10
blocked_commands = []

[evaluation]
task_ids = ["hello-world", "create-bucket"]  # Directory names, not numbers
n_attempts = 1
timeout_multiplier = 1.0
cleanup = true

[dataset]
name = "terminal-bench-core"
version = "head"
```

**All fields in config.toml are REQUIRED.**

See [SETUP.md](SETUP.md) for complete configuration reference.

## Project Structure

```
terminal-bench-green-agent/
├── src/
│   ├── green_agent/agent.py       # Evaluator that runs terminal-bench
│   ├── adapters/a2a_white_agent.py  # Bridges terminal-bench ↔ A2A
│   ├── kickoff.py                  # Sends eval requests
│   └── config/settings.py          # Config loader
├── white_agent/
│   └── llm_white_agent.py          # Example LLM-powered agent
├── scripts/                         # Helper scripts
├── config.toml                      # Configuration
└── eval_results/                    # Results (generated)
```

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
- `[[skills]]` with double brackets

### Missing Dataset
```bash
terminal-bench datasets download --dataset terminal-bench-core
```

See [SETUP.md](SETUP.md) for detailed troubleshooting.

## Development

```bash
# Start agents
python -m src.green_agent
python -m white_agent
python -m src.kickoff

# Import in code
from src.green_agent.agent import TerminalBenchGreenAgentExecutor
from src.adapters.a2a_white_agent import A2AWhiteAgent
from src.config import settings
```

## Next Steps

1. **Customize White Agent** - See [SETUP.md](SETUP.md) → "Building Your White Agent"
2. **Run More Tasks** - Add task IDs to `config.toml`
3. **Integrate with AgentBeats** - Wrap with AgentBeats executor

## Documentation

- **SETUP.md** - Detailed setup, configuration reference, building agents, troubleshooting
- **ARCHITECTURE.txt** - Detailed architecture diagram
