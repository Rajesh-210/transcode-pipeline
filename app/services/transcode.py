"""Transcode service helper for query and queue interactions."""

from typing import Optional, Dict, Any
from app.core.redis import JobRepository
import redis.asyncio as redis_async


async def get_job_status(video_id: str, redis_client: redis_async.Redis) -> Optional[Dict[str, Any]]:
    job_repo = JobRepository(redis_client)
    return await job_repo.get_job(video_id)
