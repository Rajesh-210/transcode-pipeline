"""Event-driven transcoding worker using Redis queue and FFmpeg."""

import os
import sys
import json
import time
import subprocess
import tempfile
import logging
import redis
from prometheus_client import Counter, Histogram, start_http_server

from app.core.config import get_settings
from app.services.storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("transcode-worker")

# Prometheus Metrics
JOBS_PROCESSED = Counter("transcode_jobs_processed_total", "Total transcoding jobs processed", ["status"])
JOB_DURATION = Histogram("transcode_job_duration_seconds", "Time spent transcoding video")


def transcode_video_to_hls(input_path: str, output_dir: str, video_id: str) -> dict:
    """Transcode video to multi-bitrate HLS using FFmpeg."""
    os.makedirs(output_dir, exist_ok=True)

    variants = [
        {"name": "1080p", "width": 1920, "height": 1080, "video_bitrate": "5000k", "audio_bitrate": "192k"},
        {"name": "720p", "width": 1280, "height": 720, "video_bitrate": "2800k", "audio_bitrate": "128k"},
        {"name": "360p", "width": 640, "height": 360, "video_bitrate": "800k", "audio_bitrate": "96k"},
    ]

    master_playlist_lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    generated_resolutions = []

    for var in variants:
        variant_dir = os.path.join(output_dir, var["name"])
        os.makedirs(variant_dir, exist_ok=True)
        playlist_path = os.path.join(variant_dir, "playlist.m3u8")

        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vf", f"scale=w={var['width']}:h={var['height']}:force_original_aspect_ratio=decrease,pad={var['width']}:{var['height']}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-b:v", var["video_bitrate"],
            "-c:a", "aac",
            "-b:a", var["audio_bitrate"],
            "-hls_time", "6",
            "-hls_list_size", "0",
            "-hls_segment_filename", os.path.join(variant_dir, "segment_%03d.ts"),
            playlist_path,
        ]

        logger.info(f"Running FFmpeg for {var['name']}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg failed for {var['name']}: {result.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg transcode failed for {var['name']}")

        bandwidth_map = {"1080p": 5300000, "720p": 3000000, "360p": 900000}
        bw = bandwidth_map.get(var["name"], 1000000)
        master_playlist_lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={bw},RESOLUTION={var['width']}x{var['height']}")
        master_playlist_lines.append(f"{var['name']}/playlist.m3u8")
        generated_resolutions.append(var["name"])

    master_playlist_path = os.path.join(output_dir, "master.m3u8")
    with open(master_playlist_path, "w") as f:
        f.write("\n".join(master_playlist_lines) + "\n")

    # Extract thumbnail at 2 seconds
    thumbnail_path = os.path.join(output_dir, "thumbnail.jpg")
    thumb_cmd = [
        "ffmpeg", "-y", "-ss", "00:00:02", "-i", input_path,
        "-vframes", "1", "-vf", "scale=640:-1", thumbnail_path
    ]
    subprocess.run(thumb_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return {
        "resolutions": generated_resolutions,
        "master_playlist": master_playlist_path,
        "thumbnail": thumbnail_path if os.path.exists(thumbnail_path) else None,
    }


def process_job(job_data: dict, redis_client: redis.Redis) -> None:
    video_id = job_data["video_id"]
    object_name = job_data["object_name"]
    bucket = job_data.get("bucket", "transcoded-media")

    job_key = f"transcode:job:{video_id}"
    storage = get_storage()

    logger.info(f"Starting job {video_id} for file {job_data['filename']}")

    job_data["status"] = "processing"
    job_data["progress"] = 10
    redis_client.set(job_key, json.dumps(job_data))

    start_time = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "input_video")
        output_dir = os.path.join(tmpdir, "output_hls")

        try:
            logger.info(f"Downloading {object_name} from storage...")
            storage.download_file(object_name, input_file)
            job_data["progress"] = 30
            redis_client.set(job_key, json.dumps(job_data))

            logger.info(f"Transcoding video {video_id}...")
            transcode_result = transcode_video_to_hls(input_file, output_dir, video_id)
            job_data["progress"] = 80
            redis_client.set(job_key, json.dumps(job_data))

            logger.info(f"Uploading HLS assets for {video_id}...")
            hls_prefix = f"hls/{video_id}"

            master_path = transcode_result["master_playlist"]
            storage.upload_local_file(f"{hls_prefix}/master.m3u8", master_path, content_type="application/vnd.apple.mpegurl")

            for res in transcode_result["resolutions"]:
                res_dir = os.path.join(output_dir, res)
                for f in os.listdir(res_dir):
                    f_path = os.path.join(res_dir, f)
                    if f.endswith(".ts"):
                        mime = "video/mp2t"
                    elif f.endswith(".m3u8"):
                        mime = "application/vnd.apple.mpegurl"
                    else:
                        mime = "application/octet-stream"
                    storage.upload_local_file(f"{hls_prefix}/{res}/{f}", f_path, content_type=mime)

            thumbnail_url = None
            if transcode_result["thumbnail"]:
                thumb_name = f"{hls_prefix}/thumbnail.jpg"
                storage.upload_local_file(thumb_name, transcode_result["thumbnail"], content_type="image/jpeg")
                thumbnail_url = storage.get_presigned_url(thumb_name)

            master_url = storage.get_presigned_url(f"{hls_prefix}/master.m3u8")

            job_data["status"] = "completed"
            job_data["progress"] = 100
            job_data["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            job_data["hls_url"] = master_url
            job_data["thumbnail_url"] = thumbnail_url
            job_data["resolutions"] = transcode_result["resolutions"]
            redis_client.set(job_key, json.dumps(job_data))

            duration = time.time() - start_time
            JOB_DURATION.observe(duration)
            JOBS_PROCESSED.labels(status="success").inc()
            logger.info(f"Successfully completed job {video_id} in {duration:.2f}s")

        except Exception as e:
            logger.exception(f"Error processing job {video_id}: {e}")
            job_data["status"] = "failed"
            job_data["error"] = str(e)
            redis_client.set(job_key, json.dumps(job_data))
            JOBS_PROCESSED.labels(status="failure").inc()


def main():
    settings = get_settings()

    # Start metrics server on port 9090
    try:
        start_http_server(9090)
        logger.info("Prometheus metrics server started on port 9090")
    except Exception as e:
        logger.warning(f"Could not start metrics server: {e}")

    # Create Redis client with explicit timeouts
    redis_client = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=15,
        retry_on_timeout=True,
        health_check_interval=30,
    )

    queue_key = "transcode:queue"
    logger.info(f"Worker started, listening on Redis queue: {queue_key}")

    while True:
        try:
            item = redis_client.blpop(queue_key, timeout=5)
            if item:
                _, raw_data = item
                job_data = json.loads(raw_data)
                process_job(job_data, redis_client)
        except redis.ConnectionError:
            logger.error("Redis connection lost, reconnecting in 5s...")
            redis_client.connection_pool.disconnect()
            time.sleep(5)
        except Exception as e:
            logger.exception(f"Unexpected error in worker loop: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
