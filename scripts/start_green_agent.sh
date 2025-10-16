#!/bin/bash
# Start the Terminal-Bench Green Agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Default values (can be overridden via environment variables)
export GREEN_AGENT_PORT=${GREEN_AGENT_PORT:-${1:-9999}}
export GREEN_AGENT_HOST=${GREEN_AGENT_HOST:-${2:-0.0.0.0}}

echo "Starting Terminal-Bench Green Agent..."
echo "Host: $GREEN_AGENT_HOST"
echo "Port: $GREEN_AGENT_PORT"
echo ""

# Kill any existing process on the port
echo "Checking for existing processes on port $GREEN_AGENT_PORT..."
EXISTING_PID=$(lsof -ti :$GREEN_AGENT_PORT 2>/dev/null || true)
if [ ! -z "$EXISTING_PID" ]; then
    echo "Found process $EXISTING_PID using port $GREEN_AGENT_PORT. Killing it..."
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 1
    echo "Process killed."
else
    echo "Port $GREEN_AGENT_PORT is free."
fi
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the green agent
python -m src.green_agent
