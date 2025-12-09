#!/bin/bash
# GKE Deployment Script for Terminal-Bench Agents
# This script automates the deployment process to GKE

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
ZONE="${GKE_ZONE:-us-west1-a}"
CLUSTER_NAME="${GKE_CLUSTER_NAME:-terminal-bench-cluster}"
IMAGE_NAME="terminal-bench-agent"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"

# Functions
error() {
    echo -e "${RED}Error: $1${NC}" >&2
    exit 1
}

info() {
    echo -e "${GREEN}ℹ️  $1${NC}"
}

warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."
    
    command -v gcloud >/dev/null 2>&1 || error "gcloud CLI not found. Please install it."
    command -v kubectl >/dev/null 2>&1 || error "kubectl not found. Please install it."
    
    if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
        if [ -z "$PROJECT_ID" ]; then
            error "PROJECT_ID not set. Set GCP_PROJECT_ID environment variable or run 'gcloud config set project PROJECT_ID'"
        fi
        warn "Using project from gcloud config: $PROJECT_ID"
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        warn "OPENAI_API_KEY not set. You'll need to create the secret manually."
    fi
    
    info "Using project: $PROJECT_ID"
    info "Using zone: $ZONE"
    info "Using cluster name: $CLUSTER_NAME"
}

# Build and push image
build_and_push() {
    info "Building and pushing Docker image..."
    
    IMAGE="gcr.io/$PROJECT_ID/$IMAGE_NAME"
    
    info "Building image: $IMAGE"
    gcloud builds submit --tag "$IMAGE" || error "Failed to build and push image"
    
    info "Image built and pushed successfully"
}

# Enable APIs
enable_apis() {
    info "Enabling required APIs..."
    
    gcloud services enable container.googleapis.com --project="$PROJECT_ID" || warn "API may already be enabled"
    gcloud services enable containerregistry.googleapis.com --project="$PROJECT_ID" || warn "API may already be enabled"
}

# Create or get cluster
setup_cluster() {
    info "Setting up GKE cluster..."
    
    if gcloud container clusters describe "$CLUSTER_NAME" --zone="$ZONE" --project="$PROJECT_ID" >/dev/null 2>&1; then
        info "Cluster $CLUSTER_NAME already exists"
    else
        info "Creating cluster $CLUSTER_NAME..."
        gcloud container clusters create "$CLUSTER_NAME" \
          --zone="$ZONE" \
          --machine-type=e2-standard-4 \
          --enable-autoscaling \
          --min-nodes=1 \
          --max-nodes=3 \
          --num-nodes=1 \
          --enable-autorepair \
          --enable-autoupgrade \
          --project="$PROJECT_ID" || error "Failed to create cluster"
    fi
    
    info "Getting cluster credentials..."
    gcloud container clusters get-credentials "$CLUSTER_NAME" --zone="$ZONE" --project="$PROJECT_ID" || error "Failed to get credentials"
}

# Create secrets
create_secrets() {
    info "Creating secrets..."
    
    if [ -n "$OPENAI_API_KEY" ]; then
        if kubectl get secret openai-secret >/dev/null 2>&1; then
            warn "Secret openai-secret already exists. Updating..."
            kubectl delete secret openai-secret
        fi
        
        kubectl create secret generic openai-secret \
          --from-literal=api-key="$OPENAI_API_KEY" || error "Failed to create secret"
        info "Secret created successfully"
    else
        warn "OPENAI_API_KEY not set. Please create secret manually:"
        warn "  kubectl create secret generic openai-secret --from-literal=api-key='YOUR_KEY'"
    fi
}

# Update YAML files with project ID
update_yaml() {
    info "Updating YAML files with project ID..."
    
    IMAGE="gcr.io/$PROJECT_ID/$IMAGE_NAME:latest"
    
    # Update deployment files
    for file in k8s/deployment-*.yaml; do
        if [ -f "$file" ]; then
            sed -i.bak "s|gcr.io/YOUR_PROJECT_ID/terminal-bench-agent:latest|$IMAGE|g" "$file"
            rm -f "${file}.bak"
        fi
    done
    
    info "YAML files updated"
}

# Deploy agents
deploy_agents() {
    info "Deploying agents..."
    
    info "Deploying green agent..."
    kubectl apply -f k8s/deployment-green.yaml || error "Failed to deploy green agent"
    
    info "Deploying white agent..."
    kubectl apply -f k8s/deployment-white.yaml || error "Failed to deploy white agent"
    
    info "Waiting for deployments to be ready..."
    kubectl rollout status deployment/terminal-bench-green-agent --timeout=5m || warn "Green agent deployment may not be ready"
    kubectl rollout status deployment/terminal-bench-white-agent --timeout=5m || warn "White agent deployment may not be ready"
}

# Get external IPs and update CLOUDRUN_HOST
update_hosts() {
    info "Getting external IPs and updating CLOUDRUN_HOST..."
    
    info "Waiting for LoadBalancer IPs to be assigned (this may take 1-2 minutes)..."
    
    # Wait for services to get external IPs
    for i in {1..30}; do
        GREEN_IP=$(kubectl get service terminal-bench-green-agent -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
        WHITE_IP=$(kubectl get service terminal-bench-white-agent -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
        
        if [ -n "$GREEN_IP" ] && [ -n "$WHITE_IP" ]; then
            break
        fi
        
        if [ $i -eq 30 ]; then
            error "Timeout waiting for LoadBalancer IPs. Check service status manually."
        fi
        
        sleep 2
    done
    
    info "Green Agent External IP: $GREEN_IP"
    info "White Agent External IP: $WHITE_IP"
    
    # Update CLOUDRUN_HOST
    info "Updating CLOUDRUN_HOST for green agent..."
    kubectl set env deployment/terminal-bench-green-agent CLOUDRUN_HOST="$GREEN_IP" || warn "Failed to update CLOUDRUN_HOST"
    
    info "Updating CLOUDRUN_HOST for white agent..."
    kubectl set env deployment/terminal-bench-white-agent CLOUDRUN_HOST="$WHITE_IP" || warn "Failed to update CLOUDRUN_HOST"
    
    # Update MCP_HOST for green agent (bypasses Cloudflare port restrictions for MCP connections)
    info "Updating MCP_HOST for green agent..."
    kubectl set env deployment/terminal-bench-green-agent MCP_HOST="$GREEN_IP" || warn "Failed to update MCP_HOST"
    
    # Restart to apply changes
    info "Restarting deployments to apply new environment variables..."
    kubectl rollout restart deployment/terminal-bench-green-agent
    kubectl rollout restart deployment/terminal-bench-white-agent
    
    info "Deployment URLs:"
    info "  Green Agent: http://$GREEN_IP"
    info "  White Agent: http://$WHITE_IP"
}

# Main execution
main() {
    info "Starting GKE deployment for Terminal-Bench Agents"
    echo ""
    
    check_prerequisites
    echo ""
    
    read -p "Do you want to build and push the Docker image? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        build_and_push
        echo ""
    fi
    
    enable_apis
    echo ""
    
    setup_cluster
    echo ""
    
    create_secrets
    echo ""
    
    update_yaml
    echo ""
    
    deploy_agents
    echo ""
    
    update_hosts
    echo ""
    
    info "✅ Deployment complete!"
    info ""
    info "Next steps:"
    info "  1. Check pod status: kubectl get pods"
    info "  2. View logs: kubectl logs -f deployment/terminal-bench-green-agent"
    info "  3. Test endpoints: curl http://<EXTERNAL_IP>/info"
}

# Run main function
main

