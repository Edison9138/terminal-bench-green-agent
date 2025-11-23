# Setup Guide

Guide for installing, configuring, and building white agents for terminal-bench evaluation.

## Table of Contents

- [Quick Setup](#quick-setup)
- [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [Running Evaluations](#running-evaluations)
- [Building Your White Agent](#building-your-white-agent)
- [AgentBeats Platform Deployment](#agentbeats-platform-deployment)

## Prerequisites

- **Python 3.10+** - `python --version`
- **Docker** - `docker ps` should work without errors
- **OpenAI API Key** - For example white agent (optional)

## Quick Setup

The fastest way to get started:

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# OR: venv\Scripts\activate  # Windows

# 2. Run setup script, which install dependencies and download terminal-bench dataset
bash scripts/setup.sh

# 3. Configure API key
echo "OPENAI_API_KEY=your_key_here" > .env
```

## Configuration

Edit `config.toml` to configure evaluation. Key settings:

```toml
[white_agent]
model = "gpt-4o-mini"      # LLM model
max_iterations = 30         # Max commands per task

[evaluation]
task_ids = ["hello-world", "create-bucket"]  # Tasks to run
n_attempts = 1              # Attempts per task
n_concurrent_trials = 2     # Parallel trials
timeout_multiplier = 1.0    # Adjust timeouts

[dataset]
name = "terminal-bench-core"
version = "0.1.1"

[scoring]
# Weights for computing overall weighted score
[scoring.difficulty_weights]
easy = 1
medium = 2
hard = 3
unknown = 1
# ... (see config.toml for complete list)
```

**Available tasks:** Check `~/.cache/terminal-bench/terminal-bench-core/tasks/` for all task IDs.

**Scoring Configuration:** The evaluation system computes a weighted overall score based on task difficulty. Each task gets a score from 0.0 to 1.0 (50% from test case pass rate, 50% from is_resolved status). The overall score is weighted by difficulty (easy=1, medium=2, hard=3). You can customize these weights in `config.toml` under the `[scoring]` section.

See `config.toml` for all configuration options (ports, logging, A2A settings, etc).

## Building Your White Agent

Your white agent needs three components:

1. **A2A Server** - Receives evaluation requests
2. **MCP Client** - Connects to task-scoped MCP servers
3. **Solver Logic** - Executes bash commands to solve tasks

### Task Instruction Format

Each task includes an MCP server URL. Below is an example instruction for the "hello-world" task.

```
You are being evaluated on Terminal-Bench.

TASK: Create a file called hello.txt with "Hello, World!"

MCP Server URL: http://localhost:10000

ENVIRONMENT:
- Tool: execute_bash_command (parameter: command)
- Working directory: /app (Docker container)
- Each command runs in fresh shell (no state between commands)
```

### A2A Server

```python
from a2a.server.apps import A2AStarletteApplication
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, TextPart
import uvicorn

class WhiteAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        instruction = context.get_user_input()

        # Extract MCP URL and solve task
        mcp_url = extract_mcp_url(instruction)
        result = await solve_task(instruction, mcp_url)

        # Return result
        await updater.add_artifact([Part(root=TextPart(text=result))], name="response")
        await updater.complete()
```

### MCP Client

```python
from mcp.client.sse import sse_client
from mcp import ClientSession
import json

async def execute_command(mcp_url: str, command: str):
    async with sse_client(f"{mcp_url}/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "execute_bash_command",
                arguments={"command": command}
            )

            # Returns: {command, returncode, stdout, stderr}
            return json.loads(result.content[0].text)
```

### LLM Solver

```python
from openai import AsyncOpenAI

async def solve_with_llm(instruction: str, mcp_url: str, max_iterations: int = 30):
    client = AsyncOpenAI()
    messages = [{"role": "user", "content": instruction}]

    async with sse_client(f"{mcp_url}/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            for _ in range(max_iterations):
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=[{
                        "type": "function",
                        "function": {
                            "name": "execute_bash_command",
                            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}
                        }
                    }]
                )

                if response.choices[0].message.tool_calls:
                    # Execute command via MCP
                    # Add result to messages
                    # Continue loop
                elif "TASK_COMPLETE" in response.choices[0].message.content:
                    return "Task completed"
```

### Reference Implementation

See complete working example:

- `white_agent/white_agent.py` - A2A server
- `white_agent/white_agent_helpers.py` - MCP client + LLM integration

## Running Evaluations

Start three terminals with the virtual environment activated:

**Terminal 1 - White Agent:**

```bash
python -m white_agent
```

**Terminal 2 - Green Agent:**

```bash
python -m src.green_agent
```

**Terminal 3 - Kickoff:**

```bash
python -m src.kickoff
```

The kickoff script validates both agents are running, then starts evaluation. Results are saved to `eval_results/green_agent_eval_TIMESTAMP/`.

**Stop evaluation:** Press `Ctrl+C` in any terminal.

## AgentBeats Platform Deployment

This project is integrated with the AgentBeats platform for cloud deployment on Google Cloud Run. The same codebase can deploy both green and white agents as separate services.

### Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- Docker (for local testing)
- Python 3.13+ (for Cloud Run deployment, required for `earthshaker==0.2.0`)

### What Changed for AgentBeats

The following files were added/modified to support AgentBeats deployment:

**New Files:**
- `Dockerfile` - Container definition with git installed and dataset pre-downloaded
- `.dockerignore` - Excludes unnecessary files from Docker build
- `main.py` - Unified entry point that handles both green and white agents
- `run.sh` - Script called by AgentBeats controller
- `Procfile` - Entry point for Cloud Run (used with buildpacks)

**Modified Files:**
- `src/green_agent/green_agent.py` - Now accepts `host`/`port` parameters and uses `AGENT_URL` from environment
- `white_agent/white_agent.py` - Now accepts `host`/`port` parameters and uses `AGENT_URL` from environment
- `requirements.txt` - Added `earthshaker==0.2.0`, `pydantic-settings`, and `typer`

### Step-by-Step Deployment Guide

#### Step 1: Enable Google Cloud APIs

```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable run.googleapis.com
```

#### Step 2: Build Container Image

The Dockerfile installs git (required for dataset download) and pre-downloads the terminal-bench dataset:

```bash
cd terminal-bench-green-agent

# Build image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/terminal-bench-agent
```

Replace `YOUR_PROJECT_ID` with your Google Cloud project ID. You can find it with:
```bash
gcloud config get-value project
```

#### Step 3: Deploy Green Agent

```bash
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

**Important**: After deployment, you must update `CLOUDRUN_HOST` with the actual service URL:

```bash
# Get the actual service URL
GREEN_URL=$(gcloud run services describe terminal-bench-green-agent \
  --region us-west1 \
  --format 'value(status.url)')

# Extract hostname (remove https://)
GREEN_HOST=$(echo $GREEN_URL | sed 's|https://||')

# Update the environment variable
gcloud run services update terminal-bench-green-agent \
  --region us-west1 \
  --update-env-vars CLOUDRUN_HOST=$GREEN_HOST
```

#### Step 4: Deploy White Agent

Use the same image, but with `ROLE=white`:

```bash
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

Update the white agent's `CLOUDRUN_HOST` similarly:

```bash
WHITE_URL=$(gcloud run services describe terminal-bench-white-agent \
  --region us-west1 \
  --format 'value(status.url)')

WHITE_HOST=$(echo $WHITE_URL | sed 's|https://||')

gcloud run services update terminal-bench-white-agent \
  --region us-west1 \
  --update-env-vars CLOUDRUN_HOST=$WHITE_HOST
```

#### Step 5: Verify Deployment

Check that both services are accessible:

```bash
# Check green agent controller info
curl https://$GREEN_HOST/info

# Check green agent card (should show correct public URL)
curl https://$GREEN_HOST/.well-known/agent-card.json | jq .url

# Check white agent
curl https://$WHITE_HOST/info

# Check white agent card
curl https://$WHITE_HOST/.well-known/agent-card.json | jq .url
```

The agent card URLs should show the public Cloud Run URLs (not `0.0.0.0:8080`).

### How AgentBeats Integration Works

1. **AgentBeats Controller** starts and sets environment variables:
   - `ROLE` - Either "green" or "white"
   - `HOST` - Host to bind to (typically "0.0.0.0")
   - `AGENT_PORT` - Port to listen on (typically 8080, from Cloud Run's `PORT` env var)
   - `AGENT_URL` - Public URL for the agent card (constructed from `CLOUDRUN_HOST` and `HTTPS_ENABLED`)

2. **Controller** calls `./run.sh`, which:
   - Checks if dataset exists, downloads if missing (fallback)
   - Executes `python main.py run`

3. **main.py** reads `ROLE` and starts the appropriate agent:
   - `ROLE=green` → calls `start_green_agent(host, port)`
   - `ROLE=white` → calls `start_white_agent(host, port)`

4. **Agent** uses `AGENT_URL` from environment for its agent card URL

### Local Testing with AgentBeats Format

You can test the AgentBeats integration locally (without earthshaker):

```bash
# Test green agent
ROLE=green HOST=0.0.0.0 AGENT_PORT=9999 AGENT_URL=http://localhost:9999 python main.py run

# Test white agent
ROLE=white HOST=0.0.0.0 AGENT_PORT=8001 AGENT_URL=http://localhost:8001 python main.py run
```

### Troubleshooting

**Problem**: Agent card shows `0.0.0.0:8080` instead of public URL
- **Solution**: Ensure `CLOUDRUN_HOST` is set to the actual hostname (without `https://`). Get it from `gcloud run services describe`.

**Problem**: Container fails to start with "git not found" error
- **Solution**: This shouldn't happen with the Dockerfile (git is installed). If using buildpacks, you'll need a custom build step or Dockerfile.

**Problem**: Dataset download fails
- **Solution**: The dataset is downloaded during Docker build. If it fails, check build logs. The `run.sh` script will retry at runtime as a fallback.

**Problem**: ModuleNotFoundError for `terminal_bench` or `earthshaker`
- **Solution**: Ensure `requirements.txt` includes all dependencies. For Cloud Run, Python 3.13 is required for `earthshaker==0.2.0`.

**Problem**: Health check timeout
- **Solution**: Increase timeout with `--timeout 3600` flag. Also ensure the agent binds to `0.0.0.0` and listens on the `PORT` environment variable.

### Updating Deployment

To update the deployment after code changes:

```bash
# Rebuild image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/terminal-bench-agent

# Update service (uses new image automatically)
gcloud run services update terminal-bench-green-agent \
  --region us-west1 \
  --image gcr.io/YOUR_PROJECT_ID/terminal-bench-agent
```

### Additional Resources

- See [AGENTBEATS_INTEGRATION.md](AGENTBEATS_INTEGRATION.md) for detailed technical documentation
- See [README.md](README.md) for project overview and architecture
