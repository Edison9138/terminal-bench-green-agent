# Terminal-Bench Green Agent

A green agent that evaluates other agents on [terminal-bench](https://www.tbench.ai/) using the A2A protocol.

## Overview

This project implements a **green agent** (evaluator) that runs terminal-bench to evaluate **white agents** (agents under test). Communication between agents uses the A2A protocol, and white agents execute bash commands via task-scoped MCP servers.

### Key Features

- **Multi-agent evaluation framework** using A2A protocol
- **Task-scoped MCP servers** for isolated bash command execution
- **Docker-based sandboxing** for secure task environments
- **Flexible configuration** via TOML
- **Comprehensive logging** of agent interactions and command execution

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

### Components

#### 1. Kickoff (`src/kickoff.py`)

- Entry point that initiates evaluation
- Sends evaluation configuration to green agent via A2A
- Validates both agents are running before starting

#### 2. Green Agent (`src/green_agent/`)

- **`green_agent.py`**: Evaluator that orchestrates terminal-bench harness
- **`task_mcp_server.py`**: Creates and manages task-scoped MCP servers
- Receives evaluation requests via A2A
- Manages task lifecycle and collects results

#### 3. A2A Adapter (`src/adapters/a2a_adapter.py`)

- Bridge between terminal-bench harness and white agent
- Implements terminal-bench's agent interface
- Translates terminal-bench calls to A2A messages
- Creates unique MCP server for each task

#### 4. White Agent (`white_agent/`)

- **`white_agent.py`**: Example agent implementation with A2A interface
- **`white_agent_helpers.py`**: MCP connection utilities and LLM integration
- Receives tasks via A2A
- Connects to task-specific MCP server
- Uses LLM to solve tasks by executing bash commands

### Evaluation Flow

1. **Initialization**

   - Kickoff validates both agents are accessible
   - Configuration loaded from `config.toml`

2. **Task Assignment**

   - Kickoff sends evaluation request to green agent
   - Green agent starts terminal-bench harness
   - For each task, harness creates Docker container

3. **Task Execution**

   - A2A adapter creates unique MCP server for the task
   - Adapter sends task instruction + MCP URL to white agent via A2A
   - White agent connects to MCP server
   - White agent iteratively executes bash commands via MCP
   - MCP server forwards commands to Docker container

4. **Validation**

   - Terminal-bench validates task completion
   - Results collected and scored

5. **Reporting**
   - Results saved to `eval_results/` with timestamps
   - Includes logs, scores, and terminal recordings

## Quick Start

### Local Development

**See [SETUP.md](SETUP.md) for detailed installation, configuration, and implementation guide with code examples.**

```bash
# Terminal 1: Start white agent
python -m white_agent

# Terminal 2: Start green agent
python -m src.green_agent

# Terminal 3: Run evaluation
python -m src.kickoff
```

### Building Your Own White Agent

Your white agent must:

1. **Implement A2A interface** - Handle evaluation requests
2. **Connect to MCP server** - Parse MCP URL from task instruction
3. **Execute bash commands** - Use `execute_bash_command` tool
4. **Return results** - Send completion status via A2A

## AgentBeats Platform Deployment

This project is integrated with the [AgentBeats platform](http://v2.agentbeats.org) for cloud deployment on Google Cloud Run. The same codebase can deploy both green and white agents as separate services.

### What Changed for AgentBeats Integration

- **`Dockerfile`**: Container definition with git installed and dataset pre-downloaded
- **`main.py`**: New unified entry point that handles both green and white agents via `ROLE` environment variable
- **`run.sh`**: Script called by AgentBeats controller to start the agent
- **`Procfile`**: Entry point for Cloud Run (used with buildpacks)
- **Environment Variables**: Agents now read `ROLE`, `HOST`, `AGENT_PORT`, and `AGENT_URL` from environment

### Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker (for local testing)
- Python 3.13+ (for Cloud Run deployment)

### Step-by-Step Deployment

#### 1. Enable Required Google Cloud APIs

```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable run.googleapis.com
```

#### 2. Build Container Image

```bash
# Navigate to project directory
cd terminal-bench-green-agent

# Build image (includes git and pre-downloads dataset)
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/terminal-bench-agent
```

Replace `YOUR_PROJECT_ID` with your Google Cloud project ID.

#### 3. Deploy Green Agent

```bash
# Deploy green agent service
gcloud run deploy terminal-bench-green-agent \
  --image gcr.io/YOUR_PROJECT_ID/terminal-bench-agent \
  --platform managed \
  --region us-west1 \
  --allow-unauthenticated \
  --set-env-vars ROLE=green \
  --set-env-vars CLOUDRUN_HOST=terminal-bench-green-agent-123456.us-west1.run.app \
  --set-env-vars HTTPS_ENABLED=true \
  --set-env-vars OPENAI_API_KEY=your-key-here \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600
```

**Important**: After deployment, get the actual service URL and update `CLOUDRUN_HOST`:

```bash
# Get actual service URL
GREEN_URL=$(gcloud run services describe terminal-bench-green-agent \
  --region us-west1 \
  --format 'value(status.url)')

# Extract hostname (remove https://)
GREEN_HOST=$(echo $GREEN_URL | sed 's|https://||')

# Update CLOUDRUN_HOST
gcloud run services update terminal-bench-green-agent \
  --region us-west1 \
  --update-env-vars CLOUDRUN_HOST=$GREEN_HOST
```

#### 4. Deploy White Agent

```bash
# Deploy white agent service (uses same image)
gcloud run deploy terminal-bench-white-agent \
  --image gcr.io/YOUR_PROJECT_ID/terminal-bench-agent \
  --platform managed \
  --region us-west1 \
  --allow-unauthenticated \
  --set-env-vars ROLE=white \
  --set-env-vars CLOUDRUN_HOST=terminal-bench-white-agent-123456.us-west1.run.app \
  --set-env-vars HTTPS_ENABLED=true \
  --set-env-vars OPENAI_API_KEY=your-key-here \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600
```

Similarly, update the white agent's `CLOUDRUN_HOST`:

```bash
# Get actual service URL
WHITE_URL=$(gcloud run services describe terminal-bench-white-agent \
  --region us-west1 \
  --format 'value(status.url)')

# Extract hostname
WHITE_HOST=$(echo $WHITE_URL | sed 's|https://||')

# Update CLOUDRUN_HOST
gcloud run services update terminal-bench-white-agent \
  --region us-west1 \
  --update-env-vars CLOUDRUN_HOST=$WHITE_HOST
```

#### 5. Verify Deployment

Check that both services are running:

```bash
# Check green agent
curl https://$GREEN_HOST/info

# Check green agent card
curl https://$GREEN_HOST/.well-known/agent-card.json

# Check white agent
curl https://$WHITE_HOST/info

# Check white agent card
curl https://$WHITE_HOST/.well-known/agent-card.json
```

The agent card should show the correct public URL (not `0.0.0.0:8080`).

### How It Works

1. **AgentBeats Controller** sets environment variables (`ROLE`, `HOST`, `AGENT_PORT`, `AGENT_URL`)
2. **Controller** calls `./run.sh` which executes `python main.py run`
3. **main.py** reads `ROLE` environment variable and starts the appropriate agent:
   - `ROLE=green` → starts green agent (evaluator)
   - `ROLE=white` → starts white agent (solver)
4. **Agent** uses `AGENT_URL` from environment for its agent card URL

### Key Features

- ✅ **Single codebase** for both green and white agents
- ✅ **Dataset pre-downloaded** during Docker build (faster cold starts)
- ✅ **Automatic URL configuration** via AgentBeats controller
- ✅ **Local testing still works** with `python -m src.green_agent` or `python -m white_agent`
- ✅ **Git included** in Docker image for dataset download fallback

### Troubleshooting

**Issue**: Agent card shows `0.0.0.0:8080` instead of public URL
- **Solution**: Ensure `CLOUDRUN_HOST` is set correctly (use actual hostname from `gcloud run services describe`)

**Issue**: Dataset download fails during build
- **Solution**: Check that git is installed (it should be in Dockerfile). The dataset will retry at runtime via `run.sh`.

**Issue**: Container fails to start
- **Solution**: Check logs with `gcloud run services logs read terminal-bench-green-agent --region us-west1`

For more details, see [AGENTBEATS_INTEGRATION.md](AGENTBEATS_INTEGRATION.md).


## Project Structure

```
terminal-bench-green-agent/
├── src/
│   ├── green_agent/
│   │   ├── green_agent.py      # Evaluator (runs terminal-bench)
│   │   ├── task_mcp_server.py  # Task-scoped MCP servers
│   │   └── card.toml            # Green agent A2A card
│   ├── adapters/
│   │   └── a2a_adapter.py      # Terminal-bench ↔ A2A bridge
│   ├── config/
│   │   └── settings.py         # Configuration loader
│   ├── utils/
│   │   └── a2a_client.py       # A2A client utilities
│   └── kickoff.py              # Evaluation initiator
├── white_agent/
│   ├── white_agent.py          # Example white agent
│   └── white_agent_helpers.py  # MCP & LLM helpers
├── scripts/
│   ├── setup.sh                # Installation script
│   └── setup_dataset.py        # Dataset downloader
├── config.toml                 # Configuration file
├── requirements.txt            # Python dependencies
└── eval_results/               # Evaluation results (generated)
```

## Results Structure

Results are saved to `eval_results/green_agent_eval_TIMESTAMP/`:

```
green_agent_eval_20251030_120000/
├── results.json              # Overall evaluation metrics
├── run_metadata.json         # Configuration snapshot
├── run.log                   # Detailed harness logs
└── task-id/                  # Per-task directory
    ├── task-id.N-of-M.*/     # Individual trial
    │   ├── results.json      # Task-specific scores
    │   ├── sessions/         # Terminal recordings (asciinema)
    │   └── agent_interaction.log  # A2A/MCP messages
    └── ...
```

### Key Metrics

- **Overall Score**: Weighted score based on task difficulty
- **Success rate**: Percentage of tasks completed successfully
- **Test case pass rate**: Percentage of individual test cases passed per task
- **Command efficiency**: Number of commands executed per task
- **Time taken**: Total duration per task
- **Error analysis**: Common failure patterns

**Note:** Scoring weights are configurable in `config.toml` under the `[scoring]` section. See [SETUP.md](SETUP.md) for details.

## License

MIT License - see [LICENSE](LICENSE)
