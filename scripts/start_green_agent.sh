#!/bin/bash
# Start the Terminal-Bench Green Agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Default values
PORT=${1:-9999}
HOST=${2:-0.0.0.0}

echo "Starting Terminal-Bench Green Agent..."
echo "Host: $HOST"
echo "Port: $PORT"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the green agent
python -m src.green_agent.agent --host "$HOST" --port "$PORT"
