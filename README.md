# Event-Driven Media Transcoding Pipeline

Production-ready media processing platform with autoscaling workers, HLS streaming output, and full DevOps observability.

## Overview

This project demonstrates advanced DevOps patterns with a complete media transcoding pipeline:

- **FastAPI** backend for video upload, status polling, and HLS stream URLs
- **FFmpeg** background worker for multi-resolution HLS transcoding (360p, 720p, 1080p)
- **Redis** queue for event-driven job dispatch
- **KEDA** for event-driven worker autoscaling (0 → 10 replicas based on queue depth)
- **AWS S3** for shared object storage across EKS nodes
- **Jenkins** CI/CD pipeline with Docker Hub image publishing
- **Kubernetes (EKS)** for container orchestration
- **Helm** for reproducible deployments

---

## Architecture

```
┌─────────────────┐
│   User / Browser│
│  (Swagger UI)   │
└─────────┬───────┘
          │ POST /api/v1/videos/upload
          ▼
┌─────────────────┐     ┌─────────────────┐
│   FastAPI API   │────▶│   Redis Queue   │
│   (API Pod)     │     │  (transcode:)   │
└─────────┬───────┘     └─────────┬───────┘
          │                      │
          │ KEDA scales workers │
          ▼                      │
┌─────────────────┐              │
│   FFmpeg Worker │──────────────┘
│   (Worker Pod)  │
└─────────┬───────┘
          │ AWS S3
          ▼
┌─────────────────┐
│   S3 Bucket     │
│  (transcode-    │
│  media-prod)    │
└─────────────────┘
          │
          ▼
    HLS Master Playlist
    (.m3u8 + .ts segments)
    → Stream via VLC/ffplay
```

**Data flow:**
1. User uploads MP4 via FastAPI `/api/v1/videos/upload`
2. API stores raw video in S3 and pushes job ID to Redis queue
3. KEDA watches Redis queue length → scales worker pods (0 → 10)
4. Worker pops job, downloads raw video from S3
5. Worker runs FFmpeg → generates HLS variants (360p, 720p, 1080p) + thumbnail
6. Worker uploads HLS files back to S3
7. API returns `hls_url` → user opens in VLC/ffplay

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11 |
| API Framework | FastAPI |
| Background Worker | Python + Redis + FFmpeg |
| Container | Docker (multi-stage builds) |
| Orchestration | Kubernetes (AWS EKS) |
| Autoscaling | KEDA (event-driven, Redis list length) |
| Ingress/LoadBalancer | Nginx Ingress + AWS NLB |
| Object Storage | AWS S3 |
| CI/CD | Jenkins (Docker Hub push + Helm deploy) |
| Package Format | Helm Chart |
| Queue | Redis |

---

## Prerequisites

Install on your CI/CD / EC2 machine:

```bash
# kubectl
curl -O https://s3.us-west-2.amazonaws.com/amazon-eks/1.36.2/2026-07-05/bin/linux/amd64/kubectl
chmod +x ./kubectl
mkdir -p $HOME/bin && cp ./kubectl $HOME/bin/kubectl
export PATH=$HOME/bin:$PATH

# AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws configure

# Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# eksctl
curl -sLO "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz"
tar -xzf eksctl_$(uname -s)_amd64.tar.gz -C /tmp && rm eksctl_$(uname -s)_amd64.tar.gz
sudo mv /tmp/eksctl /usr/local/bin

# Verify
kubectl version --client
helm version
eksctl version
aws sts get-caller-identity
```

---

## Project Structure

```
transcode-pipeline/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application factory
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       └── router.py          # Upload, status, stream endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # Pydantic settings (env_prefix=TRANSCODE_)
│   │   ├── database.py
│   │   ├── middleware.py          # Prometheus metrics
│   │   └── redis.py               # Redis client
│   ├── schemas/
│   │   └── __init__.py            # Pydantic models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── storage.py             # MinIO/S3 + local storage abstraction
│   │   ├── upload.py              # Video upload handling
│   │   └── transcode.py           # Transcode status query
│   └── worker.py                  # FFmpeg transcoding worker
├── docker/
│   ├── api.Dockerfile
│   └── worker.Dockerfile
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   └── pages/index.tsx            # Next.js dashboard
├── helm/
│   └── transcode-pipeline/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── Chart.yaml
│           ├── _helpers.tpl
│           ├── api-deployment.yaml
│           ├── api-service.yaml
│           ├── configmap.yaml
│           ├── ingress.yaml
│           ├── keda-scaledobject.yaml
│           ├── namespace.yaml
│           ├── redis-deployment.yaml
│           ├── redis-service.yaml
│           ├── secret.yaml
│           ├── worker-deployment.yaml
│           └── NOTES.txt
├── k8s/
│   ├── base/
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── secret.yaml
│   │   ├── redis-deployment.yaml
│   │   ├── redis-service.yaml
│   │   ├── api-deployment.yaml
│   │   ├── api-service.yaml
│   │   ├── worker-deployment.yaml
│   │   ├── keda-scaledobject.yaml
│   │   ├── ingress.yaml
│   │   └── kustomization.yaml
│   └── DEPLOYMENT.md
├── docker-compose.prod.yml
├── Jenkinsfile
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Problems Encountered & Solutions

| # | Problem | Solution |
|---|---------|----------|
| 1 | Poetry `package mode` error: missing `authors` field | Added `authors` field to `pyproject.toml` |
| 2 | Poetry install slow/fragile in Docker | Replaced Poetry with `requirements.txt` + `pip` |
| 3 | Docker BuildKit missing on EC2 | Disabled BuildKit or installed buildx plugin |
| 4 | MinIO `:latest` tag deprecated | Switched to AWS S3 instead of MinIO |
| 5 | Jenkins couldn't clone Git (proxy, workspace permissions) | Unset proxy env vars; `chown -R ubuntu:ubuntu` on workspace |
| 6 | EC2 disk full (99%) during Docker build | `docker system prune -a --volumes`, `apt-get clean` |
| 7 | MinIO `pull access denied` on Jenkins agent | `docker login` before compose push/pull |
| 8 | KEDA `listLength` must be string | Quoted listLength value in ScaledObject YAML |
| 9 | Pydantic `env_prefix="TRANSCODE_"` mismatch | ConfigMap keys must be prefixed: `TRANSCODE_STORAGE_BACKEND`, `TRANSCODE_S3_BUCKET`, etc. |
| 10 | Worker couldn't find uploaded file | API and Worker on different EKS nodes with `emptyDir` → switched to AWS S3 |
| 11 | Ingress host `chart-example.local` blocked direct IP | Patched Ingress to remove host restriction (catch-all) |
| 12 | Worker missing `s3_bucket` attribute | Added `TRANSCODE_S3_BUCKET` to ConfigMap |

---

## How to Use

### Upload a Video

```bash
INGRESS_IP="a0b41deb6bda8409cb013f76066e9cc2-ce9a863db1bcd7ba.elb.ap-south-1.amazonaws.com"

curl -X POST "http://$INGRESS_IP/api/v1/videos/upload" \
  -F "file=@sample.mp4"
```

Returns:
```json
{
  "video_id": "uuid-here",
  "filename": "sample.mp4",
  "size": 1234567,
  "mime_type": "video/mp4",
  "status": "queued"
}
```

### Check Transcoding Status

```bash
VIDEO_ID="your-video-id"
curl "http://$INGRESS_IP/api/v1/videos/$VIDEO_ID/status"
```

Returns:
```json
{
  "video_id": "...",
  "status": "completed",
  "progress": 100,
  "hls_url": "http://.../hls/uuid/master.m3u8",
  "resolutions": ["360p", "720p", "1080p"],
  "thumbnail_url": "http://.../thumbnail.jpg",
  "error": null
}
```

### Stream the Video

```bash
curl "http://$INGRESS_IP/api/v1/videos/$VIDEO_ID/stream-url"
```

Returns:
```json
{
  "video_id": "...",
  "stream_url": "http://.../hls/uuid/master.m3u8"
}
```

Play with VLC or ffplay:
```bash
ffplay "http://$INGRESS_IP/hls/uuid/master.m3u8"
```

---

## Deploy to EKS

### Prerequisites
- AWS CLI configured
- kubectl, helm, eksctl installed
- EKS cluster running

### Deploy KEDA
```bash
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda --create-namespace
```

### Deploy Nginx Ingress
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer
```

### Deploy Pipeline
```bash
helm install transcode-pipeline ./helm/transcode-pipeline \
  --namespace transcode-pipeline \
  --create-namespace \
  --set image.api.tag=latest \
  --set image.worker.tag=latest \
  --set ingress.enabled=true \
  --set storage.backend=s3
```

### Verify
```bash
kubectl get pods -n transcode-pipeline
kubectl get svc -n transcode-pipeline
kubectl get ingress -n transcode-pipeline
```

---

## CI/CD (Jenkins)

The `Jenkinsfile` defines a pipeline:

1. **Checkout SCM** - Git checkout from GitHub
2. **Code Lint & Test** - Python syntax check
3. **Build Docker Images** - Build API + Worker images
4. **Push to Docker Hub** - Push tagged images
5. **Deploy to EC2** - Docker Compose deploy (or Helm to EKS)
6. **Smoke Test / Health Check** - Verify `/healthz` endpoint

---

## Cleanup / Tear Down

```bash
# Uninstall Helm release
helm uninstall transcode-pipeline -n transcode-pipeline

# Delete namespace
kubectl delete namespace transcode-pipeline

# Uninstall KEDA
helm uninstall keda -n keda
kubectl delete namespace keda

# Uninstall Ingress
helm uninstall ingress-nginx -n ingress-nginx
kubectl delete namespace ingress-nginx

# Delete EKS cluster
eksctl delete cluster --name transcode-pipeline --region ap-south-1

# Delete S3 bucket
aws s3 rm s3://transcode-media-prod --recursive
aws s3 rb s3://transcode-media-prod --region ap-south-1
```

---

## License

MIT - This is a demonstration project for DevOps engineers.