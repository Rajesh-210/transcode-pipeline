# app/services/storage.py
import os
from pathlib import Path
from app.core.config import get_settings


class StorageService:
    def __init__(self):
        settings = get_settings()
        self.backend = settings.storage_backend
        self.local_path = getattr(settings, 'local_storage_path', '/app/local-storage')

        if self.backend == "minio":
            from minio import Minio
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
        else:
            # Local storage - create directory if needed
            Path(self.local_path).mkdir(parents=True, exist_ok=True)
            self.client = None

    def _ensure_bucket(self):
        if self.client:
            try:
                if not self.client.bucket_exists(self.bucket):
                    self.client.make_bucket(self.bucket)
            except Exception as e:
                print(f"Warning: could not ensure bucket exists: {e}")

    def upload_file(self, object_name: str, file_data: bytes, content_type: str) -> str:
        if self.backend == "minio" and self.client:
            from io import BytesIO
            stream = BytesIO(file_data)
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=stream,
                length=len(file_data),
                content_type=content_type,
            )
            return object_name
        else:
            # Local storage
            dest = Path(self.local_path) / object_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(file_data)
            return str(dest)

    def download_file(self, object_name: str, target_path: str) -> None:
        if self.backend == "minio" and self.client:
            self.client.fget_object(self.bucket, object_name, target_path)
        else:
            src = Path(self.local_path) / object_name
            import shutil
            shutil.copy(str(src), target_path)

    def upload_local_file(self, object_name: str, local_path: str, content_type: str = "application/octet-stream") -> None:
        if self.backend == "minio" and self.client:
            self.client.fput_object(self.bucket, object_name, local_path, content_type=content_type)
        else:
            import shutil
            dest = Path(self.local_path) / object_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(local_path, str(dest))

    def get_presigned_url(self, object_name: str, expires_in_seconds: int = 3600) -> str:
        if self.backend == "minio" and self.client:
            from datetime import timedelta
            return self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=timedelta(seconds=expires_in_seconds)
            )
        else:
            # Local storage - return a relative path URL
            return f"/local-storage/{object_name}"


_storage_instance = None


def get_storage() -> StorageService:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageService()
    return _storage_instance
