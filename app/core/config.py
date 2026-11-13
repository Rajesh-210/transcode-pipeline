"""Configuration module for the transcoding pipeline."""

import os
from functools import lru_cache
from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TRANSCODE_",
        extra="allow",
    )

    # Application
    api_title: str = Field(default="Transcoding Pipeline API", description="API title")
    api_version: str = Field(default="0.1.0", description="API version")
    log_level: str = Field(default="INFO", description="Logging level")

    # Storage configuration
    storage_backend: str = Field(
        default="minio", description="Storage backend: minio, s3, or gcs"
    )
    minio_endpoint: str = Field(
        default="http://minio:9000", description="MinIO endpoint URL"
    )
    minio_access_key: str = Field(
        default="minioadmin", description="MinIO access key"
    )
    minio_secret_key: str = Field(
        default="minioadmin123", description="MinIO secret key"
    )
    minio_bucket: str = Field(default="transcoded-media", description="Default bucket name")

    # S3/GCS fallback
    aws_access_key_id: str | None = Field(default=None, description="AWS access key")
    aws_secret_access_key: str | None = Field(default=None, description="AWS secret key")
    aws_default_region: str | None = Field(
        default=None, description="AWS default region"
    )
    gcs_project_id: str | None = Field(
        default=None, description="GCS project ID"
    )

    # Redis
    redis_url: str = Field(
        default="redis://redis:6379/0", description="Redis connection URL"
    )

    # API limits
    max_upload_size_mb: int = Field(
        default=500, description="Max upload size in MB"
    )
    allowed_video_mime_types: list[str] = Field(
        default=[
            "video/mp4",
            "video/quicktime",
            "video/x-msvideo",
            "video/webm",
        ],
        description="Allowed video MIME types",
    )

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # Feature flags
    keda_enabled: bool = Field(default=True, description="Enable KEDA autoscaling")
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()