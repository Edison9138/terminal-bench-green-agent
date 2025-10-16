#!/bin/bash
# Start the White Agent (LLM-powered)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Default values (can be overridden via environment variables)
export WHITE_AGENT_PORT=${WHITE_AGENT_PORT:-${1:-8001}}
export WHITE_AGENT_HOST=${WHITE_AGENT_HOST:-${2:-0.0.0.0}}

echo "Starting White Agent..."
echo "Host: $WHITE_AGENT_HOST"
echo "Port: $WHITE_AGENT_PORT"
echo ""

# Kill any existing process on the port
echo "Checking for existing processes on port $WHITE_AGENT_PORT..."
EXISTING_PID=$(lsof -ti :$WHITE_AGENT_PORT 2>/dev/null || true)
if [ ! -z "$EXISTING_PID" ]; then
    echo "Found process $EXISTING_PID using port $WHITE_AGENT_PORT. Killing it..."
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 1
    echo "Process killed."
else
    echo "Port $WHITE_AGENT_PORT is free."
fi
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the LLM-powered white agent
echo "Using LLM-powered agent"
python -m white_agent
