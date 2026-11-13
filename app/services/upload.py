"""Video upload handling and queue dispatch."""

import uuid
from datetime import datetime, timezone
from fastapi import UploadFile
from app.services.storage import get_storage
from app.core.redis import JobRepository
import redis.asyncio as redis_async


async def handle_video_upload(
    file: UploadFile,
    redis_client: redis_async.Redis,
) -> str:
    video_id = str(uuid.uuid4())
    storage = get_storage()

    content = await file.read()
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "mp4"
    object_name = f"raw/{video_id}.{file_extension}"

    storage.upload_file(
        object_name=object_name,
        file_data=content,
        content_type=file.content_type or "video/mp4",
    )

    job_repo = JobRepository(redis_client)
    job_payload = {
        "video_id": video_id,
        "filename": file.filename,
        "object_name": object_name,
        "content_type": file.content_type,
        "size": len(content),
        "status": "queued",
        "progress": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "hls_url": None,
        "thumbnail_url": None,
        "resolutions": [],
        "error": None,
    }

    await job_repo.enqueue_job(job_payload)
    return video_id
