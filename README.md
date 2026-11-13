# Event-Driven Media Transcoding Pipeline

Production-ready media processing platform with autoscaling workers, HLS streaming output, and full DevOps observability.

## Overview

This project demonstrates advanced DevOps patterns:
- **Event-driven architecture** with Redis queues
- **Autoscaling workers** using KEDA on Kubernetes
- **Multi-region storage** for distributed media serving
- **Observability** with Prometheus, Grafana, and OpenTelemetry
- **Zero-downtime deployments** with proper database migrations

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web Frontend  │────▶│  API Gateway   │────▶│   Redis Queue   │
│  (Next.js/TS)   │     │   (FastAPI)    │     │   (Celery/RQ)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                    │  ▲  │  ▲
                                                    ▼  │  ▼  │
                                         ┌─────────────────────────────────┐
                                         │        Worker Pool              │
                                         │   (FFmpeg + HLS Transcoder)     │
                                         │  Scale-to-zero via KEDA         │
                                         └─────────────────────────────────┘
                                                    │  ▲  │  ▲
                                                    ▼  │  ▼  │
                                         ┌─────────────────────────────────┐
                                         │        Object Storage           │
                                         │  (MinIO/Local or S3/GCS)      │
                                         └─────────────────────────────────┘
```

## Local Development

### Prerequisites
- Docker Compose v2+
- Python 3.11+
- FFmpeg (for local worker testing)

### Quick Start
```bash
# Clone and enter directory
cd transcode-pipeline

# Start the complete stack
docker compose up -d --build

# Access services
# API:      http://localhost:8000
# Frontend: http://localhost:3000
# Redis:    localhost:6379
```

### Development Commands
```bash
# Start API service in watch mode
poetry run python -m app.main --reload

# Start worker
poetry run celery -A app.worker worker --loglevel=info

# Run tests
poetry run pytest

# Run linting
poetry run ruff check app/

# Build and push images
docker buildx build -t my-registry/transcode-api:latest -f docker/api.Dockerfile .
docker buildx build -t my-registry/transcode-worker:latest -f docker/worker.Dockerfile .
```

## Kubernetes Deployment

### Prerequisites
- kubectl configured for your cluster
- Helm v3+
- KEDA operator installed

### Deployment
```bash
helm upgrade --install transcode-pipeline ./helm/ \
  --set storage.backend=s3 \
  --set storage.s3.bucket=my-media-bucket \
  --set image.pullSecrets[0]=my-registry-secret
```

### Verification
```bash
kubectl get pods -n transcode-pipeline
kubectl get svc -n transcode-pipeline
kubectl get hpa -n transcode-pipeline
```

## Monitoring & Alerting

### Prometheus Metrics
- `http_requests_total` - API request counts
- `transcoding_jobs_total` - Jobs processed
- `worker_queue_length` - Jobs pending
- `ffmpeg_transcode_duration_seconds` - Transcoding time histogram

### Grafana Dashboards
Import the bundled JSON dashboard for out-of-the-box observability.

## License

MIT - This is a demonstration project for DevOps engineers.