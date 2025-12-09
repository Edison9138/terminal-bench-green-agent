FROM python:3.13-slim

# Install git and Docker CLI (required for terminal-bench)
RUN apt-get update && \
    apt-get install -y git ca-certificates curl gnupg && \
    # Install Docker CLI
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce-cli docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

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

