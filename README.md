# Terminal-Bench Green Agent

A green agent (evaluator) that runs [terminal-bench](https://www.tbench.ai/) to evaluate white agents (agents under test) using the A2A protocol.

## Quick Start

1. **Create virtual environment and install dependencies:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **(Optional) Customize evaluation settings:**

   Edit [config.toml](config.toml) if you want to change:

   - Task IDs to evaluate (`evaluation.task_ids`)
   - White agent model (`white_agent.model`) - need to be OpenAI
   - Concurrent trials (`evaluation.n_concurrent_trials`)
   - Dataset version (`dataset.version`)

   _Skip this step to use default settings._

4. **Start the agents:**

   In separate terminals:

   ```bash
   # Terminal 1: Start green agent (evaluator)
   python -m src.green_agent

   # Terminal 2: Start white agent (solver)
   python -m white_agent
   ```

5. **Run evaluation:**

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
