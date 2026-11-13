"""Object storage service supporting MinIO and AWS S3."""

import io
from minio import Minio
from minio.error import S3Error
from app.core.config import get_settings


class StorageService:
    def __init__(self):
        settings = get_settings()
        self.endpoint = settings.minio_endpoint.replace("http://", "").replace("https://", "")
        self.access_key = settings.minio_access_key
        self.secret_key = settings.minio_secret_key
        self.bucket = settings.minio_bucket
        self.client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=settings.minio_endpoint.startswith("https"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except Exception as e:
            print(f"Warning: could not ensure bucket exists: {e}")

    def upload_file(self, object_name: str, file_data: bytes, content_type: str) -> str:
        self._ensure_bucket()
        stream = io.BytesIO(file_data)
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_name,
            data=stream,
            length=len(file_data),
            content_type=content_type,
        )
        return object_name

    def download_file(self, object_name: str, target_path: str) -> None:
        self.client.fget_object(self.bucket, object_name, target_path)

    def upload_local_file(self, object_name: str, local_path: str, content_type: str = "application/octet-stream") -> None:
        self._ensure_bucket()
        self.client.fput_object(self.bucket, object_name, local_path, content_type=content_type)

    def get_presigned_url(self, object_name: str, expires_in_seconds: int = 3600) -> str:
        from datetime import timedelta
        return self.client.presigned_get_object(
            self.bucket,
            object_name,
            expires=timedelta(seconds=expires_in_seconds)
        )


_storage_instance = None


def get_storage() -> StorageService:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageService()
    return _storage_instance
