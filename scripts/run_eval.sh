#!/bin/bash
# Run a terminal-bench evaluation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "Running Terminal-Bench Evaluation..."
echo ""
echo "Prerequisites:"
echo "  1. Green agent running on port 9999"
echo "  2. White agent running on port 8001"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the kickoff script
python -m src.kickoff
