#!/bin/bash
# Start the White Agent (LLM-powered)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Default values
PORT=${1:-8001}
HOST=${2:-0.0.0.0}

echo "Starting White Agent..."
echo "Host: $HOST"
echo "Port: $PORT"
echo ""

# Kill any existing process on the port
echo "Checking for existing processes on port $PORT..."
EXISTING_PID=$(lsof -ti :$PORT 2>/dev/null || true)
if [ ! -z "$EXISTING_PID" ]; then
    echo "Found process $EXISTING_PID using port $PORT. Killing it..."
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 1
    echo "Process killed."
else
    echo "Port $PORT is free."
fi
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the LLM-powered white agent
echo "Using LLM-powered agent (GPT-4o-mini)"
python -m white_agent --host "$HOST" --port "$PORT"
