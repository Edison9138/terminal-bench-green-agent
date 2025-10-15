#!/bin/bash
# Start the Example White Agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Default values
PORT=${1:-8001}
HOST=${2:-0.0.0.0}

echo "Starting Example White Agent..."
echo "Host: $HOST"
echo "Port: $PORT"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the white agent
python -m white_agent --host "$HOST" --port "$PORT"
