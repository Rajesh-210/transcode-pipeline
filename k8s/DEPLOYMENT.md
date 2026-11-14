# Kubernetes Deployment Guide

This guide covers deploying the Media Transcoding Pipeline on Kubernetes using either **EKS** (AWS Elastic Kubernetes Service) or **K3s** (lightweight Kubernetes).

## Prerequisites

- `kubectl` configured for your cluster
- `helm` v3+ installed
- KEDA operator installed (for worker autoscaling)
- Nginx Ingress Controller installed (for external API access)

---

## Option A: Deploy on EKS (AWS)

### 1. Create EKS Cluster

```bash
# Using eksctl
eksctl create cluster \
  --name transcode-pipeline \
  --region ap-south-1 \
  --nodes 3 \
  --node-type t3.medium \
  --managed

# Or using AWS Console / Terraform
```

### 2. Install KEDA Operator

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda --create-namespace
```

### 3. Install Nginx Ingress Controller

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace
```

### 4. Deploy the Pipeline

#### Using Raw Kubernetes Manifests

```bash
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/secret.yaml      # Edit credentials first!
kubectl apply -f k8s/base/redis-deployment.yaml
kubectl apply -f k8s/base/redis-service.yaml
kubectl apply -f k8s/base/api-deployment.yaml
kubectl apply -f k8s/base/api-service.yaml
kubectl apply -f k8s/base/worker-deployment.yaml
kubectl apply -f k8s/base/keda-scaledobject.yaml
kubectl apply -f k8s/base/ingress.yaml      # If using Ingress
```

#### Using Helm (Recommended)

```bash
helm install transcode-pipeline ./helm/transcode-pipeline \
  --namespace transcode-pipeline \
  --create-namespace \
  --set image.api.tag=<your-build-tag> \
  --set image.worker.tag=<your-build-tag> \
  --set ingress.enabled=true
```

### 5. Get External LoadBalancer IP

```bash
kubectl get ingress -n transcode-pipeline
kubectl get svc -n transcode-pipeline transcode-api
```

Configure your DNS to point to the LoadBalancer IP for external access.

---

## Option B: Deploy on K3s (Lightweight)

K3s is ideal for single-node or small clusters, homelabs, or CI agents.

### 1. Install K3s

```bash
# On your server
curl -sfL https://get.k3s.io | sh -

# Check node status
kubectl get nodes
```

### 2. Install Helm (if not already present)

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### 3. Install KEDA Operator

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda --create-namespace
```

### 4. Install Traefik or Nginx Ingress (K3s includes Traefik by default)

K3s comes with Traefik pre-installed. To use Nginx instead:

```bash
# Disable Traefik (if desired)
# Then install Nginx Ingress
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace
```

### 5. Deploy the Pipeline

```bash
helm install transcode-pipeline ./helm/transcode-pipeline \
  --namespace transcode-pipeline \
  --create-namespace
```

### 6. Access the API

```bash
# Port-forward for local testing
kubectl port-forward svc/transcode-api 8000:8000 -n transcode-pipeline

# Open in browser
# http://localhost:8000/docs
```

---

## Verification

Check all pods are running:

```bash
kubectl get pods -n transcode-pipeline
kubectl get svc -n transcode-pipeline
kubectl get scaledobject -n transcode-pipeline
```

Test the API:

```bash
curl http://<your-ingress-ip>/healthz
curl http://localhost:8000/docs  # If port-forwarded
```

Upload a video:

```bash
curl -X POST http://<your-ingress-ip>/api/v1/videos/upload \
  -F "file=@sample-video.mp4"
```

---

## Worker Autoscaling with KEDA

KEDA scales the FFmpeg worker from **0 to 10 replicas** based on Redis queue depth:

```bash
# Watch workers scale up/down
watch kubectl get hpa -n transcode-pipeline
watch kubectl get pods -n transcode-pipeline -l app.kubernetes.io/component=worker
```

When the Redis queue `transcode:queue` exceeds 5 items, KEDA spins up more workers. When idle, workers scale to zero.

---

## Using S3 Instead of Local Storage (Production)

For production on EKS, replace local storage with AWS S3:

1. Edit `k8s/base/configmap.yaml`:
   ```yaml
   STORAGE_BACKEND: "s3"
   ```

2. Edit `k8s/base/secret.yaml` with your AWS credentials:
   ```yaml
   stringData:
     AWS_ACCESS_KEY_ID: "AKIA..."
     AWS_SECRET_ACCESS_KEY: "..."
     AWS_DEFAULT_REGION: "ap-south-1"
     S3_BUCKET: "transcode-media-prod"
   ```

3. Alternatively, use **IRSA** (IAM Roles for Service Accounts) to avoid storing credentials in Secrets.

---

## Cleanup

```bash
# Helm uninstall
helm uninstall transcode-pipeline -n transcode-pipeline

# Or delete all raw manifests
kubectl delete -f k8s/base/

# Delete namespace
kubectl delete namespace transcode-pipeline
```

---

## Architecture Summary

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   External User │────▶│   Ingress/NLB   │────▶│  transcode-api  │
│   (Browser/API) │     │   (LoadBalancer)│     │   (2 replicas)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                    │
                                                    ▼
                                          ┌─────────────────┐
                                          │   Redis Queue   │
                                          │  (transcode:)   │
                                          └─────────────────┘
                                                    ▲
                                                    │
                                          ┌─────────────────┐
                                          │   KEDA watches  │
                                          │   queue length  │
                                          └─────────────────┘
                                                    │
                                                    ▼
                                          ┌─────────────────┐
                                          │  transcode-work │
                                          │   (0→10 replicas│
                                          │    via KEDA)    │
                                          └─────────────────┘
                                                    │
                                                    ▼
                                          ┌─────────────────┐
                                          │  Local Storage  │
                                          │   or AWS S3     │
                                          └─────────────────┘
```
