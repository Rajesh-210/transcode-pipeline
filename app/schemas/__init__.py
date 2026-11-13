"""Pydantic schemas for the transcoding pipeline."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class VideoUploadResponse(BaseModel):
    video_id: str = Field(..., description="Unique video identifier")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    status: str = Field(default="queued", description="Initial processing status")


class TranscodeStatusResponse(BaseModel):
    video_id: str
    status: str
    progress: int = Field(default=0, ge=0, le=100)
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    hls_url: Optional[str] = None
    resolutions: List[str] = Field(default_factory=list)
    thumbnail_url: Optional[str] = None
    error: Optional[str] = None


class JobPayload(BaseModel):
    video_id: str
    filename: str
    object_name: str
    bucket: str
    target_resolutions: List[str] = ["360p", "720p", "1080p"]
