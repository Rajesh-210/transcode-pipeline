"""API router for the transcoding pipeline."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
import redis.asyncio as redis_async

from app.core.config import get_settings
from app.core.redis import get_redis
from app.services.upload import handle_video_upload
from app.services.transcode import get_job_status
from app.services.storage import get_storage
from app.schemas import VideoUploadResponse, TranscodeStatusResponse

router = APIRouter()


@router.post(
    "/videos/upload",
    response_model=VideoUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["videos"],
)
async def upload_video(
    file: UploadFile = File(...),
    redis_client: redis_async.Redis = Depends(get_redis),
):
    """Upload a raw video file to trigger asynchronous transcoding."""
    settings = get_settings()

    if file.content_type and file.content_type not in settings.allowed_video_mime_types:
        # If client doesn't specify exact mime or sends generic stream, check filename
        valid_exts = (".mp4", ".mov", ".avi", ".webm", ".mkv")
        if not file.filename.lower().endswith(valid_exts):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported video type: {file.content_type}. Allowed extensions: {valid_exts}",
            )

    video_id = await handle_video_upload(file=file, redis_client=redis_client)

    return VideoUploadResponse(
        video_id=video_id,
        filename=file.filename or "unknown.mp4",
        size=file.size or 0,
        mime_type=file.content_type or "video/mp4",
        status="queued",
    )


@router.get(
    "/videos/{video_id}/status",
    response_model=TranscodeStatusResponse,
    tags=["videos"],
)
async def get_video_status(
    video_id: str,
    redis_client: redis_async.Redis = Depends(get_redis),
):
    """Get the current transcoding status, progress, and HLS manifest URL."""
    job = await get_job_status(video_id=video_id, redis_client=redis_client)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video job '{video_id}' not found",
        )

    return TranscodeStatusResponse(
        video_id=job.get("video_id", video_id),
        status=job.get("status", "unknown"),
        progress=job.get("progress", 0),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
        hls_url=job.get("hls_url"),
        resolutions=job.get("resolutions", []),
        thumbnail_url=job.get("thumbnail_url"),
        error=job.get("error"),
    )


@router.get(
    "/videos/{video_id}/stream-url",
    tags=["videos"],
)
async def get_video_stream_url(video_id: str, redis_client: redis_async.Redis = Depends(get_redis)):
    """Generate a presigned streaming URL for the master HLS playlist."""
    job = await get_job_status(video_id=video_id, redis_client=redis_client)
    if not job:
        raise HTTPException(status_code=404, detail="Video not found")
    if job.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Video is not ready for streaming (current status: {job.get('status')})",
        )

    master_playlist_object = f"hls/{video_id}/master.m3u8"
    storage = get_storage()
    try:
        url = storage.get_presigned_url(master_playlist_object)
        return {"video_id": video_id, "stream_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate streaming URL: {e}")
