# Kubernetes Deployment Guide

## Prerequisites

- kubectl configured for your target cluster
- KEDA operator installed:
  ```bash
  helm repo add kedacore https://kedacore.github.io/charts
  helm install keda kedacore/keda --namespace keda --create-namespace
  ```
- Redis accessible (you can deploy via Helm chart or use managed Redis)

## Deployment Steps

### 1. Apply Core Manifests

```bash
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/secret.yaml   # Edit secrets first!
kubectl apply -f k8s/base/api-deployment.yaml
kubectl apply -f k8s/base/api-service.yaml
kubectl apply -f k8s/base/worker-deployment.yaml
kubectl apply -f k8s/base/keda-scaledobject.yaml
```

### 2. Verify Deployment

```bash
kubectl get pods -n transcode-pipeline
kubectl get svc -n transcode-pipeline
kubectl get scaledobject -n transcode-pipeline
```

### 3. Expose API (Ingress)

Add an Ingress resource or use your cloud load balancer to expose `transcode-api` service.

## Architecture Overview

- **API**: 2 replicas, ClusterIP service, health probes configured
- **Worker**: Starts at 1 replica, autoscaled by KEDA between 0-10 replicas based on Redis queue length
- **KEDA**: Scales worker based on `transcode:queue` list length; scale-to-zero when idle
- **Secrets**: Managed via Kubernetes Secret with `stringData`

## Prometheus Metrics

- API exposes `/metrics` on port 8000
- Worker exposes metrics on port 9090
- Configure Prometheus ServiceMonitor or scrape annotations accordingly
