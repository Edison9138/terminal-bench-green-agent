#!/bin/bash
# Check if Docker is ready for terminal-bench

set -e

echo "==================================================================="
echo "Docker Setup Verification for Terminal-Bench"
echo "==================================================================="
echo ""

# Check 1: Docker command exists
echo "✓ Checking if Docker is installed..."
if command -v docker &> /dev/null; then
    echo "  ✅ Docker is installed"
    docker --version
else
    echo "  ❌ Docker is NOT installed"
    echo ""
    echo "Please install Docker Desktop:"
    echo "  macOS: https://www.docker.com/products/docker-desktop"
    echo "  Linux: sudo apt-get install docker.io"
    exit 1
fi

echo ""

# Check 2: Docker daemon is running
echo "✓ Checking if Docker daemon is running..."
if docker ps &> /dev/null; then
    echo "  ✅ Docker daemon is running"
else
    echo "  ❌ Docker daemon is NOT running"
    echo ""
    echo "Please start Docker:"
    echo "  macOS: open -a Docker"
    echo "  Linux: sudo systemctl start docker"
    exit 1
fi

echo ""

# Check 3: Docker socket is accessible
echo "✓ Checking Docker socket..."
if [ -e /var/run/docker.sock ]; then
    echo "  ✅ Docker socket exists"
else
    echo "  ⚠️  Docker socket not found at /var/run/docker.sock"
fi

echo ""

# Check 4: Can we actually run containers?
echo "✓ Testing Docker functionality..."
if docker run --rm hello-world &> /dev/null; then
    echo "  ✅ Can run Docker containers"
else
    echo "  ❌ Cannot run Docker containers"
    echo ""
    echo "This might be a permissions issue. Try:"
    echo "  Linux: sudo usermod -aG docker $USER"
    echo "  Then log out and back in"
    exit 1
fi

echo ""

# Check 5: Python can access Docker
echo "✓ Checking Python Docker integration..."
if python -c "import docker; docker.from_env()" &> /dev/null; then
    echo "  ✅ Python can access Docker"
else
    echo "  ❌ Python cannot access Docker"
    echo ""
    echo "Make sure docker package is installed:"
    echo "  pip install docker"
    exit 1
fi

echo ""

# Optional: Show Docker resource usage
echo "==================================================================="
echo "Docker Status"
echo "==================================================================="
docker info 2>/dev/null | grep -E "Server Version|CPUs|Total Memory|Docker Root Dir" || true

echo ""
echo "Running Containers:"
docker ps

echo ""
echo "==================================================================="
echo "✅ ALL CHECKS PASSED - Docker is ready for terminal-bench!"
echo "==================================================================="
echo ""
echo "You can now run:"
echo "  ./scripts/start_white_agent.sh  # Terminal 1"
echo "  ./scripts/start_green_agent.sh  # Terminal 2"
echo "  ./scripts/run_eval.sh           # Terminal 3"
echo ""
