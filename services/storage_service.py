"""
Storage Service
Handles file storage abstraction (GCP, S3, or local filesystem)
"""
from pathlib import Path, PurePosixPath
from typing import Optional
import logging
import re
import tempfile

import boto3
from botocore.exceptions import ClientError

from core.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


class StorageService:
    """Service for provider-agnostic file storage operations."""

    def __init__(self):
        self.storage_type = settings.STORAGE_TYPE
        self.local_path = Path(settings.LOCAL_STORAGE_PATH)

        if self.storage_type == "gcp":
            from google.cloud import storage
            from google.oauth2 import service_account

            credentials_dict = {
                "type": "service_account",
                "project_id": settings.CLOUD_STORAGE_PROJECT,
                "private_key": settings.CLOUD_STORAGE_SECRET.replace("\\n", "\n"),
                "client_email": settings.CLOUD_STORAGE_ACCOUNTNAME,
                "token_uri": "https://oauth2.googleapis.com/token",
            }

            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            self.gcs_client = storage.Client(
                credentials=credentials,
                project=settings.CLOUD_STORAGE_PROJECT,
            )
            self.bucket_name = settings.CLOUD_STORAGE_BUCKETNAME
            self.bucket = self.gcs_client.bucket(self.bucket_name)
            logger.info("Initialized cloud storage provider=gcp")

        elif self.storage_type == "s3":
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
            self.bucket_name = settings.S3_BUCKET_NAME
            logger.info("Initialized cloud storage provider=s3")

        else:
            self.local_path.mkdir(parents=True, exist_ok=True)
            logger.info("Initialized local storage")

    @staticmethod
    def sanitize_filename(file_name: str) -> str:
        """Return a safe file name that preserves extension when possible."""
        raw_name = Path(file_name or "").name.strip()
        if not raw_name:
            return "file"

        sanitized = _ALLOWED_FILENAME_CHARS.sub("_", raw_name)
        return sanitized[:255] or "file"

    @staticmethod
    def _sanitize_path_segment(segment: str) -> str:
        sanitized = _ALLOWED_FILENAME_CHARS.sub("_", (segment or "").strip())
        return sanitized or "unknown"

    def build_execution_file_path(self, user_id: str, execution_id: str, file_name: str) -> str:
        """Build provider-agnostic absolute file path: /{userId}/{executionId}/{fileName}."""
        safe_user_id = self._sanitize_path_segment(user_id)
        safe_execution_id = self._sanitize_path_segment(str(execution_id))
        safe_file_name = self.sanitize_filename(file_name)
        return f"/{safe_user_id}/{safe_execution_id}/{safe_file_name}"

    def _normalize_absolute_file_path(self, file_path: str) -> str:
        """Normalize legacy URLs/keys into provider-agnostic absolute file path."""
        candidate = (file_path or "").strip()
        if not candidate:
            raise ValueError("File path is required")

        if candidate.startswith("gs://"):
            # Legacy format: gs://bucket/key
            split_index = candidate.find("/", len("gs://"))
            candidate = candidate[split_index:] if split_index != -1 else "/"
        elif candidate.startswith("s3://"):
            # Legacy format: s3://bucket/key
            split_index = candidate.find("/", len("s3://"))
            candidate = candidate[split_index:] if split_index != -1 else "/"

        if not candidate.startswith("/"):
            candidate = f"/{candidate}"

        normalized = PurePosixPath(candidate)
        parts = [part for part in normalized.parts if part not in {"", "/"}]
        if any(part == ".." for part in parts):
            raise ValueError("Invalid file path")
        if not parts:
            raise ValueError("Invalid file path")

        return "/" + "/".join(parts)

    def _object_key(self, file_path: str) -> str:
        absolute_file_path = self._normalize_absolute_file_path(file_path)
        return absolute_file_path.lstrip("/")

    def _local_file_path(self, file_path: str) -> Path:
        return self.local_path / self._object_key(file_path)

    async def upload_file(
        self,
        file_content: bytes,
        file_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload content to configured storage and return absolute file path."""
        absolute_file_path = self._normalize_absolute_file_path(file_path)

        if self.storage_type == "gcp":
            return await self._upload_to_gcp(file_content, absolute_file_path, content_type)
        if self.storage_type == "s3":
            return await self._upload_to_s3(file_content, absolute_file_path, content_type)
        return await self._upload_to_local(file_content, absolute_file_path)

    async def _upload_to_gcp(self, file_content: bytes, file_path: str, content_type: str) -> str:
        try:
            key = self._object_key(file_path)
            blob = self.bucket.blob(key)
            blob.upload_from_string(file_content, content_type=content_type)
            return self._normalize_absolute_file_path(file_path)
        except Exception as exc:
            logger.error("Failed to upload to GCP: %s", exc)
            raise Exception(f"GCP upload failed: {exc}")

    async def _upload_to_s3(self, file_content: bytes, file_path: str, content_type: str) -> str:
        try:
            key = self._object_key(file_path)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_content,
                ContentType=content_type,
            )
            return self._normalize_absolute_file_path(file_path)
        except ClientError as exc:
            logger.error("Failed to upload to S3: %s", exc)
            raise Exception(f"S3 upload failed: {exc}")

    async def _upload_to_local(self, file_content: bytes, file_path: str) -> str:
        local_file_path = self._local_file_path(file_path)
        local_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_file_path, "wb") as local_file:
            local_file.write(file_content)
        return self._normalize_absolute_file_path(file_path)

    async def download_file(self, file_path: str) -> Optional[bytes]:
        """Download file bytes from configured storage."""
        if self.storage_type == "gcp":
            return await self._download_from_gcp(file_path)
        if self.storage_type == "s3":
            return await self._download_from_s3(file_path)
        return await self._download_from_local(file_path)

    async def _download_from_gcp(self, file_path: str) -> Optional[bytes]:
        try:
            key = self._object_key(file_path)
            blob = self.bucket.blob(key)
            if not blob.exists():
                return None
            return blob.download_as_bytes()
        except Exception as exc:
            logger.error("Failed to download from GCP: %s", exc)
            return None

    async def _download_from_s3(self, file_path: str) -> Optional[bytes]:
        try:
            key = self._object_key(file_path)
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            logger.error("Failed to download from S3: %s", exc)
            return None

    async def _download_from_local(self, file_path: str) -> Optional[bytes]:
        try:
            local_file_path = self._local_file_path(file_path)
            with open(local_file_path, "rb") as local_file:
                return local_file.read()
        except Exception as exc:
            logger.error("Failed to read local file: %s", exc)
            return None

    async def get_file_path(self, file_path: str) -> str:
        """Get local file-system path for processing."""
        absolute_file_path = self._normalize_absolute_file_path(file_path)

        if self.storage_type == "local":
            return str(self._local_file_path(absolute_file_path))

        content = await self.download_file(absolute_file_path)
        if content is None:
            raise Exception(f"Failed to download file: {absolute_file_path}")

        temp_dir = Path(tempfile.gettempdir()) / "evidence_analysis"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_filename = self._object_key(absolute_file_path).replace("/", "_")
        temp_path = temp_dir / temp_filename

        with open(temp_path, "wb") as temp_file:
            temp_file.write(content)

        return str(temp_path)

    async def get_file_metadata(self, file_path: str) -> Optional[dict]:
        """Return object metadata if file exists, otherwise None."""
        absolute_file_path = self._normalize_absolute_file_path(file_path)

        if self.storage_type == "gcp":
            key = self._object_key(absolute_file_path)
            blob = self.bucket.blob(key)
            if not blob.exists():
                return None
            blob.reload()
            return {
                "size_bytes": int(blob.size or 0),
                "content_type": blob.content_type,
            }

        if self.storage_type == "s3":
            key = self._object_key(absolute_file_path)
            try:
                response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchKey", "NotFound"}:
                    return None
                raise

            return {
                "size_bytes": int(response.get("ContentLength", 0)),
                "content_type": response.get("ContentType"),
            }

        local_file_path = self._local_file_path(absolute_file_path)
        if not local_file_path.exists():
            return None

        stat_result = local_file_path.stat()
        return {
            "size_bytes": int(stat_result.st_size),
            "content_type": None,
        }

    async def generate_upload_url(
        self,
        file_path: str,
        content_type: str,
        expiration: int = 900,
    ) -> dict:
        """Generate a short-lived signed upload URL for direct client upload."""
        absolute_file_path = self._normalize_absolute_file_path(file_path)
        key = self._object_key(absolute_file_path)
        # Keep parameter for compatibility but do not hard-bind Content-Type in signed URL.
        # Browser/runtime differences in Content-Type emission can otherwise invalidate signatures.
        _ = content_type or "application/octet-stream"

        if self.storage_type == "local":
            raise Exception("Signed upload URLs require cloud storage (s3 or gcp)")

        if self.storage_type == "gcp":
            from datetime import timedelta

            blob = self.bucket.blob(key)
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expiration),
                method="PUT",
            )
            return {
                "url": signed_url,
                "method": "PUT",
                "headers": {},
                "expires_in_seconds": expiration,
            }

        signed_url = self.s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": key,
            },
            ExpiresIn=expiration,
            HttpMethod="PUT",
        )

        return {
            "url": signed_url,
            "method": "PUT",
            "headers": {},
            "expires_in_seconds": expiration,
        }

    async def generate_download_url(
        self,
        file_path: str,
        expiration: int = 600,
        response_filename: Optional[str] = None,
    ) -> dict:
        """Generate a short-lived signed download URL."""
        absolute_file_path = self._normalize_absolute_file_path(file_path)
        key = self._object_key(absolute_file_path)

        if self.storage_type == "local":
            raise Exception("Signed download URLs require cloud storage (s3 or gcp)")

        if self.storage_type == "gcp":
            from datetime import timedelta

            blob = self.bucket.blob(key)
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expiration),
                method="GET",
                response_disposition=(
                    f'attachment; filename="{self.sanitize_filename(response_filename)}"'
                    if response_filename
                    else None
                ),
            )
            return {
                "url": signed_url,
                "method": "GET",
                "headers": {},
                "expires_in_seconds": expiration,
            }

        params = {
            "Bucket": self.bucket_name,
            "Key": key,
        }
        if response_filename:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{self.sanitize_filename(response_filename)}"'
            )

        signed_url = self.s3_client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expiration,
            HttpMethod="GET",
        )

        return {
            "url": signed_url,
            "method": "GET",
            "headers": {},
            "expires_in_seconds": expiration,
        }

    async def generate_presigned_url(self, file_path: str, expiration: int = 3600) -> str:
        """Backward-compatible wrapper for signed download URL only."""
        signed = await self.generate_download_url(file_path=file_path, expiration=expiration)
        return signed["url"]
