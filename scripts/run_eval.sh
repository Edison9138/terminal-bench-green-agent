#!/bin/bash
# Run a terminal-bench evaluation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "Starting agents..."

# Start green agent
if [ -f "$SCRIPT_DIR/start_green_agent.sh" ]; then
    echo "Starting green agent..."
    bash "$SCRIPT_DIR/start_green_agent.sh"
else
    echo "Warning: start_green_agent.sh not found"
fi

# Start white agent
if [ -f "$SCRIPT_DIR/start_white_agent.sh" ]; then
    echo "Starting white agent..."
    bash "$SCRIPT_DIR/start_white_agent.sh"
else
    echo "Warning: start_white_agent.sh not found"
fi

echo "Running Terminal-Bench Evaluation..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the kickoff script
python -m src.kickoff
