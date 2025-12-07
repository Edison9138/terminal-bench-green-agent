#!/usr/bin/env bash
set -e

# Download dataset if not present (for Cloud Run)
# This ensures the dataset is available even if not baked into the image
# The setup_dataset.py script checks if dataset exists, so it won't re-download unnecessarily
if [ ! -d "$HOME/.cache/terminal-bench/terminal-bench-core" ]; then
    echo "📥 Dataset not found, downloading terminal-bench dataset..."
    # Temporarily disable exit on error for dataset download (non-critical)
    set +e
    python scripts/setup_dataset.py
    download_status=$?
    set -e
    if [ $download_status -ne 0 ]; then
        echo "⚠️  Warning: Dataset download failed (exit code: $download_status)"
        echo "   The agent will still start, but evaluations may fail without the dataset"
    fi
else
    echo "✅ Dataset already present"
fi

# Start the agent
exec python main.py run

