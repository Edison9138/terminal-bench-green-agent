FROM python:3.13-slim

# Install git (required for terminal-bench dataset download)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Download dataset during build (baked into image for faster startup)
# If this fails, it will be retried at runtime via run.sh
RUN python scripts/setup_dataset.py || echo "⚠️  Dataset download failed during build, will retry at runtime"

# Set entry point (Procfile is not used with Dockerfile, so we set CMD directly)
CMD ["agentbeats", "run_ctrl"]

