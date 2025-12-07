# AgentBeats Integration - Complete

This document summarizes the changes made to integrate terminal-bench-green-agent with the AgentBeats platform.

## Changes Made

### 1. Created Required Files

- **`Dockerfile`**: Container definition with git installed and dataset pre-downloaded
- **`.dockerignore`**: Excludes unnecessary files from Docker build
- **`Procfile`**: Entry point for Cloud Run (used with buildpacks, not Dockerfile)
- **`run.sh`**: Script called by controller (`python main.py run`) - made executable
- **`main.py`**: New entry point that handles both green and white agents
- **`runtime.txt`**: Python version specification for Cloud Buildpacks (used with buildpacks)

### 2. Modified Files

#### `src/green_agent/green_agent.py`
- Added `import os` for environment variable access
- Added `create_green_agent_app_from_dict()` helper function
- Modified `main()` to accept optional `host` and `port` parameters
- Added logic to use `AGENT_URL` from environment when available

#### `white_agent/white_agent.py`
- Added `import os` for environment variable access
- Modified `main()` to accept optional `host` and `port` parameters
- Added logic to use `AGENT_URL` from environment when available

#### `requirements.txt`
- Added `earthshaker==0.2.0` (provides `agentbeats` command)
- Added `pydantic-settings>=2.0.0` (for environment variable reading)
- Added `typer>=0.9.0` (for CLI commands)

## How It Works

### Local Testing (Unchanged)
```bash
# Start green agent
python -m src.green_agent
# or
python main.py green

# Start white agent
python -m white_agent
# or
python main.py white

# Run evaluation
python -m src.kickoff
```

### AgentBeats Deployment

The controller will:
1. Set environment variables: `ROLE`, `HOST`, `AGENT_PORT`, `AGENT_URL`
2. Call `./run.sh`
3. Which calls `python main.py run`
4. Which reads `ROLE` and starts the appropriate agent

## Python Version Requirements

- **Local Development**: Python 3.12+ (earthshaker not required)
- **Cloud Run Deployment**: Python 3.13+ (required for earthshaker==0.2.0)

For local testing, use `requirements.txt` (earthshaker commented out).
For Cloud Run, the Dockerfile uses Python 3.13 and installs all dependencies including earthshaker.

## Deployment Commands

### Build Container Image

**Using Dockerfile (Recommended - includes git for dataset download):**
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/terminal-bench-agent
```

**Alternative: Using Buildpacks (requires git to be installed separately):**
```bash
gcloud builds submit --pack image=gcr.io/YOUR_PROJECT_ID/terminal-bench-agent
```

### Deploy Green Agent

```bash
# Deploy
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
  --cpu 2
```

### Deploy White Agent

```bash
# Use the same image built above (no need to rebuild)

# Deploy
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
  --cpu 1
```

**Note**: You can use the same image for both services, just set different `ROLE` and `CLOUDRUN_HOST` values.

## After Deployment

1. **Get actual service URLs**:
   ```bash
   gcloud run services describe terminal-bench-green-agent \
     --region us-west1 \
     --format 'value(status.url)'
   ```

2. **Update CLOUDRUN_HOST if different**:
   ```bash
   gcloud run services update terminal-bench-green-agent \
     --region us-west1 \
     --update-env-vars CLOUDRUN_HOST=actual-hostname-from-above
   ```

3. **Verify**:
   - Check controller info: `https://YOUR_SERVICE_URL/info`
   - Check agent card: `https://YOUR_SERVICE_URL/.well-known/agent-card.json`
   - Verify URL is public (not `0.0.0.0:8080`)

## Dataset Download

The dataset is downloaded in two places:

1. **During Docker build** (Dockerfile): Dataset is downloaded and baked into the image
   - ✅ Faster cold starts (dataset already in image)
   - ✅ No network dependency at runtime
   - ✅ Works even if git is not available at runtime

2. **At container startup** (run.sh): Fallback if dataset not found
   - Only runs if dataset is missing (shouldn't happen if build succeeded)
   - Requires git to be available (which is installed in Dockerfile)

**Note**: With the Dockerfile approach, the dataset is baked into the image, so `run.sh` should rarely need to download it. The download in `run.sh` is just a safety fallback.

## Key Points

- ✅ Both agents can be deployed from the same codebase
- ✅ Use `ROLE=green` or `ROLE=white` to determine which agent to start
- ✅ Local testing still works with `python -m src.green_agent` or `python -m white_agent`
- ✅ Agent card URLs are automatically set by controller via `AGENT_URL`
- ✅ Dataset is automatically downloaded on first container start
- ✅ All existing functionality is preserved

## Testing Locally with AgentBeats Format

You can test the AgentBeats integration locally (earthshaker not required):

```bash
# Test green agent
ROLE=green HOST=0.0.0.0 AGENT_PORT=9999 AGENT_URL=http://localhost:9999 python main.py run

# Test white agent
ROLE=white HOST=0.0.0.0 AGENT_PORT=8001 AGENT_URL=http://localhost:8001 python main.py run
```

**Note**: For Cloud Run builds, the Dockerfile uses Python 3.13 and installs all dependencies including `earthshaker==0.2.0` from `requirements.txt`. The dataset is pre-downloaded during the Docker build for faster cold starts.

