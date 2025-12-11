# Terminal-Bench Green Agent

A green agent (evaluator) that runs [terminal-bench](https://www.tbench.ai/) to evaluate white agents (agents under test) using the A2A protocol.

## Prerequisites

- **Docker**: Must be installed and running (terminal-bench uses Docker for isolated task environments)
  ```bash
  docker ps  # Verify Docker is running
  ```

## Quick Start

1. **Create virtual environment and install dependencies:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Download dataset:**

   The dataset will be downloaded automatically to `~/.cache/terminal-bench/terminal-bench-core`. To verify or manually download:

   ```bash
   terminal-bench datasets download --dataset terminal-bench-core
   ```

3. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

4. **(Optional) Customize evaluation settings:**

   Edit [config.toml](config.toml) if you want to change:

   - Task IDs to evaluate (`evaluation.task_ids`)
   - White agent model (`white_agent.model`) - must be OpenAI
   - Concurrent trials (`evaluation.n_concurrent_trials`)
   - Dataset version (`dataset.version`)

   _Skip this step to use default settings._

5. **Verify configuration:**

   Ensure ports are available (9999 for green agent, 8001 for white agent, 10000+ for MCP servers):

   ```bash
   # Check if ports are in use
   lsof -i :9999 -i :8001 -i :10000
   ```

6. **Start the agents:**

   In separate terminals:

   ```bash
   # Terminal 1: Start green agent (evaluator)
   python -m src.green_agent

   # Terminal 2: Start white agent (solver)
   python -m white_agent
   ```

7. **Run evaluation:**

   In a third terminal:

   ```bash
   python -m src.kickoff
   ```

## View Results

Results are saved to `eval_results/green_agent_eval_<timestamp>/`

**Print formatted results:**
Formatted results will be displayed in terminal upon completion, but you can also view them using

```bash
python -m scripts.print_eval_results eval_results/green_agent_eval_<timestamp>
```

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐         ┌─────────────┐
│   Kickoff   │  A2A    │ Green Agent  │  A2A    │ A2A Adapter │   MCP   │ White Agent │
│  (kickoff)  ├────────►│ (evaluator)  ├────────►│  (bridge)   ├────────►│  (solver)   │
└─────────────┘         └──────────────┘         └─────────────┘         └─────────────┘
                              │                          │
                              │                          │
                              ▼                          ▼
                        Terminal-Bench            Task MCP Server
                          Harness                 (bash execution)
```

**Components:**

- **Green Agent**: Terminal-bench evaluator that orchestrates task execution
- **White Agent**: LLM-powered agent that solves terminal tasks
- **A2A Adapter**: Bridges A2A protocol to MCP for bash execution
- **MCP Server**: Task-scoped bash environment for each test

## License

MIT License - see [LICENSE](LICENSE)
