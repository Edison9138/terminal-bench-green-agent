# GKE Deployment Guide

This directory contains Kubernetes manifests for deploying terminal-bench agents to Google Kubernetes Engine (GKE).

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **kubectl** installed
4. **Docker image** built and pushed to Google Container Registry (GCR)

## Step-by-Step Deployment

### 1. Set Your Project ID

Replace `YOUR_PROJECT_ID` in the YAML files with your actual GCP project ID:

```bash
export PROJECT_ID="your-gcp-project-id"
sed -i '' "s/YOUR_PROJECT_ID/$PROJECT_ID/g" k8s/*.yaml
```

### 2. Build and Push Docker Image

```bash
# Build and push the image
gcloud builds submit --tag gcr.io/$PROJECT_ID/terminal-bench-agent

# Or if you prefer to build locally first:
docker build -t gcr.io/$PROJECT_ID/terminal-bench-agent .
docker push gcr.io/$PROJECT_ID/terminal-bench-agent
```

### 3. Enable Required APIs

```bash
gcloud services enable container.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 4. Create GKE Cluster

```bash
# Create cluster with auto-scaling
gcloud container clusters create terminal-bench-cluster \
  --zone us-west1-a \
  --machine-type e2-standard-4 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 3 \
  --num-nodes 1 \
  --enable-autorepair \
  --enable-autoupgrade

# Get credentials
gcloud container clusters get-credentials terminal-bench-cluster --zone us-west1-a
```

**Note**: Adjust `--zone` and `--machine-type` based on your needs. For production, consider:
- Larger machine types for better performance
- Multiple zones for high availability
- Node pools with different machine types

### 5. Create Secret for API Keys

```bash
# Create secret with your OpenAI API key
kubectl create secret generic openai-secret \
  --from-literal=api-key="your-openai-api-key-here"
```

**Security Note**: Never commit secrets to git. Use `kubectl create secret` or a secret management system.

### 6. Deploy Green Agent

```bash
# Deploy green agent
kubectl apply -f k8s/deployment-green.yaml

# Wait for deployment to be ready
kubectl rollout status deployment/terminal-bench-green-agent
```

### 7. Deploy White Agent

```bash
# Deploy white agent
kubectl apply -f k8s/deployment-white.yaml

# Wait for deployment to be ready
kubectl rollout status deployment/terminal-bench-white-agent
```

### 8. Get External IPs

```bash
# Wait for LoadBalancer to assign external IPs (can take 1-2 minutes)
kubectl get services

# Get green agent external IP
GREEN_IP=$(kubectl get service terminal-bench-green-agent -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Green Agent External IP: $GREEN_IP"

# Get white agent external IP
WHITE_IP=$(kubectl get service terminal-bench-white-agent -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "White Agent External IP: $WHITE_IP"
```

### 9. Configure MCP Ports (Important!)

The green agent creates MCP servers on ports starting from 10000 (configurable via `mcp.base_port` in `config.toml`). These ports need to be exposed through the LoadBalancer Service so the white agent can connect to them.

**Current Configuration**: The `deployment-green.yaml` exposes ports 10000-10004 by default, allowing up to 5 concurrent tasks.

**To support more concurrent tasks**, add more ports to the Service in `deployment-green.yaml`:

```yaml
# In k8s/deployment-green.yaml, add more ports:
- port: 10005
  targetPort: 10005
  protocol: TCP
  name: mcp-10005
# ... add up to your max concurrent tasks
```

**Note**: Kubernetes Services don't support port ranges, so you need to add each port individually. For production with many concurrent tasks, consider:
- Using a NodePort service with a wider port range
- Using an Ingress controller with path-based routing
- Limiting concurrent tasks to match exposed ports

### 10. Update CLOUDRUN_HOST Environment Variables

After getting the external IPs, update the `CLOUDRUN_HOST` environment variable:

```bash
# Update green agent
kubectl set env deployment/terminal-bench-green-agent \
  CLOUDRUN_HOST="$GREEN_IP"

# Update white agent
kubectl set env deployment/terminal-bench-white-agent \
  CLOUDRUN_HOST="$WHITE_IP"

# Restart deployments to pick up new environment variable
kubectl rollout restart deployment/terminal-bench-green-agent
kubectl rollout restart deployment/terminal-bench-white-agent
```

**Alternative**: If you have a domain name, use that instead:

```bash
kubectl set env deployment/terminal-bench-green-agent \
  CLOUDRUN_HOST="green-agent.yourdomain.com"
```

### 11. Verify Deployment

```bash
# Check pod status
kubectl get pods

# Check services
kubectl get services

# View logs
kubectl logs -f deployment/terminal-bench-green-agent
kubectl logs -f deployment/terminal-bench-white-agent

# Test endpoints
curl http://$GREEN_IP/info
curl http://$WHITE_IP/info
```

## Updating the Deployment

### Update Image

```bash
# After building a new image
gcloud builds submit --tag gcr.io/$PROJECT_ID/terminal-bench-agent

# Update deployment
kubectl set image deployment/terminal-bench-green-agent \
  agent=gcr.io/$PROJECT_ID/terminal-bench-agent:latest
kubectl rollout status deployment/terminal-bench-green-agent
```

### Update Environment Variables

```bash
# Update any environment variable
kubectl set env deployment/terminal-bench-green-agent \
  HTTPS_ENABLED="false"  # Example: switch to HTTP

# Restart to apply changes
kubectl rollout restart deployment/terminal-bench-green-agent
```

### Scale Deployment

```bash
# Scale green agent to 2 replicas
kubectl scale deployment terminal-bench-green-agent --replicas=2
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods

# Describe pod for details
kubectl describe pod <pod-name>

# View logs
kubectl logs <pod-name>
```

### Service Not Getting External IP

```bash
# Check service status
kubectl describe service terminal-bench-green-agent

# Check if LoadBalancer is provisioning (can take a few minutes)
kubectl get service terminal-bench-green-agent -w
```

### Docker-in-Docker Issues

If you see Docker-related errors, ensure:
1. `securityContext.privileged: true` is set in the deployment
2. The cluster has the necessary permissions
3. Check pod logs for specific error messages

### Permission Denied Errors

```bash
# Ensure you have the right permissions
gcloud projects get-iam-policy $PROJECT_ID

# Grant yourself necessary roles if needed
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/container.admin"
```

## Cleanup

To delete all resources:

```bash
# Delete deployments and services
kubectl delete -f k8s/deployment-green.yaml
kubectl delete -f k8s/deployment-white.yaml

# Delete secret
kubectl delete secret openai-secret

# Delete cluster (WARNING: This deletes everything)
gcloud container clusters delete terminal-bench-cluster --zone us-west1-a
```

## Cost Considerations

- **Cluster**: GKE clusters have a base cost even when idle (~$70/month for a small cluster)
- **Nodes**: Pay for compute resources (e2-standard-4: ~$0.134/hour)
- **LoadBalancer**: External IP costs (~$0.025/hour)
- **Storage**: Persistent volumes if used

**Tip**: Delete the cluster when not in use to avoid charges, or use preemptible nodes for cost savings.

## MCP Networking in GKE

When both agents are deployed to GKE, the green agent creates MCP servers that the white agent needs to connect to. The solution implemented:

1. **MCP URL Construction**: The `A2AAdapter` in `src/adapters/a2a_adapter.py` now extracts the green agent's public IP/hostname from the `AGENT_URL` environment variable and constructs MCP URLs using that hostname instead of `localhost`.

2. **Port Exposure**: The green agent's Service exposes MCP ports (10000+) through the LoadBalancer, making them accessible to the white agent.

3. **Dynamic Port Allocation**: Each task gets a unique port starting from `mcp.base_port` (default: 10000), allowing concurrent tasks.

**Troubleshooting MCP Connections**:
- Ensure the MCP ports are exposed in the Service
- Check firewall rules allow traffic to MCP ports
- Verify `AGENT_URL` is set correctly in the green agent pod
- Check logs: `kubectl logs -f deployment/terminal-bench-green-agent`

## Differences from Cloud Run

| Feature | Cloud Run | GKE |
|---------|-----------|-----|
| Docker-in-Docker | ❌ Not supported | ✅ Supported (with privileged) |
| Auto-scaling | ✅ Automatic | ✅ Configurable |
| Cost | Pay per request | Pay for cluster + nodes |
| Setup | Simple | More complex |
| URL Management | Automatic | Manual (LoadBalancer) |
| Environment Variables | Command-line flags | YAML manifests |
| MCP Networking | ❌ Not possible (localhost issue) | ✅ Supported (public IP) |

