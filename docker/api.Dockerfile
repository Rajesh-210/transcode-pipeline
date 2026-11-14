# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install Poetry first!
RUN pip install --no-cache-dir poetry==1.8.2

# Copy dependency manifests
COPY pyproject.toml poetry.lock* ./

# Ensure lockfile exists (recreated if missing)
RUN if [ ! -f poetry.lock ]; then poetry lock --no-update; fi

# Export requirements.txt from poetry (bypasses strict package-mode validation)
RUN poetry export --without-hashes --only=main -f requirements.txt --output requirements.txt

# Install Python dependencies from requirements
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim AS runtime

# Install runtime dependencies: FFmpeg for video processing, libmagic for mime detection, curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash appuser
WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy requirements file (optional, for debugging)
COPY --from=builder /app/requirements.txt /app/requirements.txt

# Copy application code last (leverages Docker layer caching)
COPY app/ ./app/

# Set ownership
RUN chown -R appuser:appuser /app

USER appuser

# Environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
