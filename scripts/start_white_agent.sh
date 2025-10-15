#!/bin/bash
# Start the White Agent (LLM-powered by default)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Default values
PORT=${1:-8001}
HOST=${2:-0.0.0.0}
MODE=${3:-llm}  # 'llm' or 'simple'

echo "Starting White Agent..."
echo "Host: $HOST"
echo "Port: $PORT"
echo "Mode: $MODE"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the white agent
if [ "$MODE" = "simple" ]; then
    echo "Using simple (heuristic-based) agent"
    python -m white_agent --simple --host "$HOST" --port "$PORT"
else
    echo "Using LLM-powered agent (GPT-4o-mini)"
    python -m white_agent --host "$HOST" --port "$PORT"
fi
