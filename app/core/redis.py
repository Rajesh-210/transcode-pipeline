"""Redis client integration for task queue and status caching."""

import json
from typing import Optional, Dict, Any
import redis.asyncio as redis_async
from app.core.config import get_settings

_async_redis_client: Optional[redis_async.Redis] = None


async def get_redis() -> redis_async.Redis:
    global _async_redis_client
    if _async_redis_client is None:
        settings = get_settings()
        _async_redis_client = redis_async.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _async_redis_client


async def close_redis() -> None:
    global _async_redis_client
    if _async_redis_client is not None:
        await _async_redis_client.close()
        _async_redis_client = None


class JobRepository:
    """Manages transcoding job states stored in Redis."""

    QUEUE_KEY = "transcode:queue"
    JOB_PREFIX = "transcode:job:"

    def __init__(self, redis_client: redis_async.Redis):
        self.redis = redis_client

    async def enqueue_job(self, job_data: Dict[str, Any]) -> None:
        video_id = job_data["video_id"]
        # Save initial state
        await self.redis.set(
            f"{self.JOB_PREFIX}{video_id}",
            json.dumps(job_data),
        )
        # Push video_id to the FIFO queue list
        await self.redis.rpush(self.QUEUE_KEY, json.dumps(job_data))

    async def get_job(self, video_id: str) -> Optional[Dict[str, Any]]:
        raw = await self.redis.get(f"{self.JOB_PREFIX}{video_id}")
        if not raw:
            return None
        return json.loads(raw)

    async def update_job(self, video_id: str, updates: Dict[str, Any]) -> None:
        current = await self.get_job(video_id)
        if current:
            current.update(updates)
            await self.redis.set(f"{self.JOB_PREFIX}{video_id}", json.dumps(current))
