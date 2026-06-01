"""
Storage Service — production-hardened cloud storage abstraction (GCP / AWS only).

Design notes
────────────
• Cloud-only: GCP and AWS are the only supported providers.  Any other value
  raises ValueError at startup so misconfiguration is caught before traffic.

• Non-blocking I/O: every SDK call that touches the network runs inside
  asyncio.to_thread() so the FastAPI event loop is never blocked.

• AWS credential resolution: explicit keys are used when both
  CLOUD_STORAGE_ACCOUNTNAME and CLOUD_STORAGE_SECRET are non-empty; otherwise
  boto3 falls through to its standard credential chain (IAM role, env vars,
  ~/.aws/credentials, EC2 instance metadata).

• GCP credential resolution: CLOUD_STORAGE_SECRET must contain the full
  service-account JSON (preferred) or the private key alone.  The credentials
  are scoped to cloud-platform so V4 signed URLs work without any additional
  IAM permission (signing is done locally using the private key).

• Signed URLs: Content-Type is intentionally NOT bound when generating upload
  signed URLs.  Browsers and runtimes emit varying Content-Type suffixes
  (e.g. "text/csv" vs "text/csv; charset=utf-8"), which would cause 403s on
  PUT if the URL signature includes the type.  Validation happens at API layer.

• Error types:
    StorageUploadError      — put/upload failed
    StorageDownloadError    — get/download failed (NOT "not found")
    StoragePermissionError  — credential / IAM / ACL denied
  All inherit from StorageError so callers can catch the base type if needed.
  Object-not-found is always expressed as None return value, never an exception.

• Temp files: each get_file_path() call writes to a UUID-prefixed path so
  concurrent requests for the same object cannot race on the same file.

• Bootstrap probe: run_deep_validation() writes a tiny probe object, verifies
  it via metadata fetch and signed URL generation, then deletes it.  This runs
  once at startup and catches permission / credential problems before any real
  traffic arrives.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import timedelta
from pathlib import Path, PurePosixPath
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from core.config import settings

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_ALLOWED_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_PROVIDER_ALIASES: dict[str, str] = {"gcp": "gcp", "aws": "aws"}

# Prefix for all bootstrap probe objects — easy to identify in bucket listings
_PROBE_PREFIX = "__evidence_bootstrap_probe__"

# boto3 client config applied to every AWS client instance
_BOTO_CONFIG = BotoConfig(
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=10,
    read_timeout=60,
)

# GCP OAuth2 scope covering all Storage operations
_GCP_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


# ── Custom exceptions ────────────────────────────────────────────────────────

class StorageError(Exception):
    """Base exception for all storage errors."""


class StorageUploadError(StorageError):
    """Raised when an upload operation fails."""


class StorageDownloadError(StorageError):
    """Raised when a download/metadata operation fails (not for 404)."""


class StoragePermissionError(StorageError):
    """Raised when a cloud operation fails due to insufficient permissions."""


# ── StorageService ───────────────────────────────────────────────────────────

class StorageService:
    """Provider-agnostic async cloud storage service.

    Supports GCP Cloud Storage and AWS S3.  All public methods are async
    and non-blocking.  Safe to instantiate per-request or share as a
    module-level singleton.
    """

    # ── Initialisation ───────────────────────────────────────────────────────

    def __init__(self) -> None:
        self.storage_provider: str = self._resolve_storage_provider()
        self.bucket_name: str = (settings.CLOUD_STORAGE_BUCKETNAME or "").strip()

        if self.storage_provider == "gcp":
            self._init_gcp_client()
            logger.info(
                "StorageService initialised  provider=GCP  bucket=%s",
                self.bucket_name,
            )
        else:  # aws
            self._init_aws_client()
            logger.info(
                "StorageService initialised  provider=AWS  bucket=%s  region=%s",
                self.bucket_name,
                (settings.CLOUD_STORAGE_REGION or "").strip() or "(default)",
            )

    @staticmethod
    def _resolve_storage_provider() -> str:
        provider = (settings.CLOUD_STORAGE_PROVIDER or "").strip().lower()
        if not provider:
            provider = (settings.CLOUD_STORAGE or "").strip().lower()
        normalized = _PROVIDER_ALIASES.get(provider, "")
        if not normalized:
            raise ValueError(
                f"Unsupported CLOUD_STORAGE_PROVIDER value '{provider}'. "
                "Supported values: gcp, aws. "
                "Check the CLOUD_STORAGE_PROVIDER environment variable."
            )
        return normalized

    # ── AWS client ───────────────────────────────────────────────────────────

    def _init_aws_client(self) -> None:
        if not self.bucket_name:
            raise ValueError(
                "CLOUD_STORAGE_BUCKETNAME is required for AWS storage."
            )

        client_kwargs: dict = {"config": _BOTO_CONFIG}

        access_key = (settings.CLOUD_STORAGE_ACCOUNTNAME or "").strip()
        secret_key = (settings.CLOUD_STORAGE_SECRET or "").strip()

        if access_key and secret_key:
            # Explicit static credentials take precedence over the default chain
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key
            logger.debug("AWS: using explicit access-key credentials")
        elif access_key or secret_key:
            # Only one of the pair provided — ignore both and fall back to chain
            logger.warning(
                "AWS: only one of CLOUD_STORAGE_ACCOUNTNAME / CLOUD_STORAGE_SECRET "
                "is set.  Ignoring partial credentials and falling back to IAM role / "
                "environment credential chain."
            )
        else:
            logger.info(
                "AWS: no explicit credentials provided — "
                "using IAM role / environment credential chain."
            )

        region = (settings.CLOUD_STORAGE_REGION or "").strip()
        if region:
            client_kwargs["region_name"] = region

        endpoint = (settings.CLOUD_ENDPOINT or "").strip()
        if endpoint:
            client_kwargs["endpoint_url"] = endpoint

        self.s3_client = boto3.client("s3", **client_kwargs)

    # ── GCP client ───────────────────────────────────────────────────────────

    def _build_gcp_credentials_info(self) -> dict:
        secret_value = (settings.CLOUD_STORAGE_SECRET or "").strip()
        if not secret_value:
            raise ValueError(
                "CLOUD_STORAGE_SECRET is required for GCP storage. "
                "Provide the full service-account JSON or the private key."
            )

        if secret_value.startswith("{"):
            # Full service-account JSON (preferred path)
            try:
                info = json.loads(secret_value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "CLOUD_STORAGE_SECRET looks like JSON but failed to parse. "
                    f"Detail: {exc}"
                ) from exc
            if "private_key" in info:
                # Normalise escaped newlines introduced by env-var serialisation
                info["private_key"] = str(info["private_key"]).replace("\\n", "\n")
            return info

        # Backward-compatible: private key only
        client_email = (settings.CLOUD_STORAGE_ACCOUNTNAME or "").strip()
        if not client_email:
            raise ValueError(
                "When CLOUD_STORAGE_SECRET contains only a private key, "
                "CLOUD_STORAGE_ACCOUNTNAME must be the service-account email."
            )
        return {
            "type": "service_account",
            "private_key": secret_value.replace("\\n", "\n"),
            "client_email": client_email,
            "token_uri": (
                (settings.CLOUD_ENDPOINT or "").strip()
                or "https://oauth2.googleapis.com/token"
            ),
            "project_id": (settings.CLOUD_STORAGE_REGION or "").strip() or None,
        }

    def _init_gcp_client(self) -> None:
        if not self.bucket_name:
            raise ValueError(
                "CLOUD_STORAGE_BUCKETNAME is required for GCP storage."
            )

        from google.cloud import storage as gcs
        from google.oauth2 import service_account

        info = self._build_gcp_credentials_info()

        # Scoped credentials are required for V4 signed URL generation when
        # signing is performed locally with the service account private key.
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=[_GCP_SCOPE],
        )

        project_id = (
            info.get("project_id")
            or (settings.CLOUD_STORAGE_REGION or "").strip()
            or None
        )

        self.gcs_client = gcs.Client(credentials=credentials, project=project_id)
        self.bucket = self.gcs_client.bucket(self.bucket_name)

    # ── Startup validation ───────────────────────────────────────────────────

    async def run_deep_validation(self) -> None:
        """Write a probe object, verify read access and signed URL generation,
        then delete it.  Raises RuntimeError with actionable guidance on failure.

        Run once during bootstrap — not in the hot request path.
        """
        probe_path = f"/{_PROBE_PREFIX}/{uuid.uuid4().hex}.txt"
        probe_content = b"evidence-analysis-bootstrap-probe"
        provider = self.storage_provider.upper()

        logger.info("[%s] Starting deep storage validation (bucket=%s)", provider, self.bucket_name)

        try:
            # 1 — Write
            logger.info("  [%s] testing write access...", provider)
            try:
                await self.upload_file(probe_content, probe_path, "text/plain")
            except StoragePermissionError as exc:
                raise RuntimeError(
                    f"[{provider}] Write permission DENIED on bucket '{self.bucket_name}'.\n"
                    f"  GCP → grant 'roles/storage.objectCreator' or 'storage.objects.create'.\n"
                    f"  AWS → add 's3:PutObject' to the IAM policy.\n"
                    f"  Detail: {exc}"
                ) from exc
            except StorageError as exc:
                raise RuntimeError(
                    f"[{provider}] Write check FAILED on bucket '{self.bucket_name}'.\n"
                    f"  Detail: {exc}"
                ) from exc

            # 2 — Read metadata
            logger.info("  [%s] testing read/metadata access...", provider)
            try:
                meta = await self.get_file_metadata(probe_path)
                if meta is None:
                    raise RuntimeError(
                        "Probe object not found immediately after upload — "
                        "possible eventual-consistency race or permissions issue."
                    )
            except StoragePermissionError as exc:
                raise RuntimeError(
                    f"[{provider}] Read permission DENIED on bucket '{self.bucket_name}'.\n"
                    f"  GCP → grant 'storage.objects.get' to the service account.\n"
                    f"  AWS → add 's3:GetObject' and 's3:HeadObject' to the IAM policy.\n"
                    f"  Detail: {exc}"
                ) from exc
            except StorageError as exc:
                raise RuntimeError(
                    f"[{provider}] Read check FAILED on bucket '{self.bucket_name}'.\n"
                    f"  Detail: {exc}"
                ) from exc

            # 3 — Signed URL generation
            logger.info("  [%s] testing signed URL generation...", provider)
            try:
                signed = await self.generate_download_url(probe_path, expiration=60)
                if not (signed or {}).get("url"):
                    raise RuntimeError("generate_download_url returned an empty URL.")
            except StorageError as exc:
                raise RuntimeError(
                    f"[{provider}] Signed URL generation FAILED for bucket '{self.bucket_name}'.\n"
                    f"  GCP → the service account needs 'iam.serviceAccounts.signBlob'.\n"
                    f"        V4 signing with a key file works without this if credentials\n"
                    f"        are service_account.Credentials with scopes set.\n"
                    f"  AWS → verify IAM allows 's3:GetObject' for presigned URLs.\n"
                    f"  Detail: {exc}"
                ) from exc

            logger.info("  [%s] deep storage validation passed ✓", provider)

        finally:
            # Best-effort cleanup — probe objects are tiny and have a distinct prefix
            try:
                await self.delete_file(probe_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "  [%s] probe cleanup failed (non-fatal, key=%s): %s",
                    provider, probe_path, exc,
                )

    # ── Path utilities ───────────────────────────────────────────────────────

    @staticmethod
    def sanitize_filename(file_name: str) -> str:
        """Return a filesystem/object-key-safe filename, preserving the extension."""
        raw = Path(file_name or "").name.strip()
        if not raw:
            return "file"
        sanitized = _ALLOWED_FILENAME_CHARS.sub("_", raw)
        return sanitized[:255] or "file"

    @staticmethod
    def _sanitize_path_segment(segment: str) -> str:
        sanitized = _ALLOWED_FILENAME_CHARS.sub("_", (segment or "").strip())
        return sanitized or "unknown"

    def build_execution_file_path(
        self, user_id: str, execution_id: str, file_name: str
    ) -> str:
        """Build an absolute provider-agnostic path: /{userId}/{executionId}/{fileName}."""
        return (
            f"/{self._sanitize_path_segment(user_id)}"
            f"/{self._sanitize_path_segment(str(execution_id))}"
            f"/{self.sanitize_filename(file_name)}"
        )

    def _normalize_absolute_file_path(self, file_path: str) -> str:
        """Normalise any path representation to /key/format.

        Accepts:
          - gs://bucket/key/...   (legacy GCS URL)
          - s3://bucket/key/...   (legacy S3 URL)
          - /absolute/key
          - relative/key

        Raises ValueError on empty input, path-traversal attempts, or
        paths that resolve to the root.
        """
        candidate = (file_path or "").strip()
        if not candidate:
            raise ValueError("file_path must not be empty.")

        if candidate.startswith("gs://"):
            idx = candidate.find("/", len("gs://"))
            candidate = candidate[idx:] if idx != -1 else "/"
        elif candidate.startswith("s3://"):
            idx = candidate.find("/", len("s3://"))
            candidate = candidate[idx:] if idx != -1 else "/"

        if not candidate.startswith("/"):
            candidate = f"/{candidate}"

        parts = [p for p in PurePosixPath(candidate).parts if p not in {"", "/"}]

        if any(p == ".." for p in parts):
            raise ValueError(
                f"Path traversal detected in file_path: {file_path!r}"
            )
        if not parts:
            raise ValueError(
                f"file_path resolves to root or is empty: {file_path!r}"
            )

        return "/" + "/".join(parts)

    def _object_key(self, file_path: str) -> str:
        """Return the bare object key (no leading slash) for SDK calls."""
        return self._normalize_absolute_file_path(file_path).lstrip("/")

    # ── Core I/O ─────────────────────────────────────────────────────────────

    async def upload_file(
        self,
        file_content: bytes,
        file_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload *file_content* and return the stored absolute path."""
        absolute_path = self._normalize_absolute_file_path(file_path)
        if self.storage_provider == "gcp":
            return await self._upload_to_gcp(file_content, absolute_path, content_type)
        return await self._upload_to_aws(file_content, absolute_path, content_type)

    async def _upload_to_gcp(
        self, file_content: bytes, absolute_path: str, content_type: str
    ) -> str:
        key = self._object_key(absolute_path)

        def _do() -> None:
            blob = self.bucket.blob(key)
            blob.upload_from_string(file_content, content_type=content_type)

        try:
            await asyncio.to_thread(_do)
        except Exception as exc:
            logger.error("GCP upload FAILED  key=%s  bytes=%d  error=%s", key, len(file_content), exc)
            raise StorageUploadError(
                f"GCP upload failed for key '{key}': {exc}"
            ) from exc

        logger.debug("GCP upload OK  key=%s  bytes=%d", key, len(file_content))
        return absolute_path

    async def _upload_to_aws(
        self, file_content: bytes, absolute_path: str, content_type: str
    ) -> str:
        key = self._object_key(absolute_path)

        def _do() -> None:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_content,
                ContentType=content_type,
            )

        try:
            await asyncio.to_thread(_do)
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise StoragePermissionError(
                "AWS credentials not found or incomplete. "
                "Set CLOUD_STORAGE_ACCOUNTNAME + CLOUD_STORAGE_SECRET "
                "or configure an IAM role. "
                f"Detail: {exc}"
            ) from exc
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"AccessDenied", "403"}:
                raise StoragePermissionError(
                    f"AWS write denied on bucket '{self.bucket_name}' key '{key}'. "
                    "Add 's3:PutObject' to the IAM policy."
                ) from exc
            logger.error("AWS upload FAILED  key=%s  code=%s  error=%s", key, code, exc)
            raise StorageUploadError(f"AWS upload failed for key '{key}': {exc}") from exc

        logger.debug("AWS upload OK  key=%s  bytes=%d", key, len(file_content))
        return absolute_path

    # ─ Download ──────────────────────────────────────────────────────────────

    async def download_file(self, file_path: str) -> Optional[bytes]:
        """Return file bytes or *None* if the object does not exist.

        Raises StorageDownloadError / StoragePermissionError on non-404 errors.
        """
        if self.storage_provider == "gcp":
            return await self._download_from_gcp(file_path)
        return await self._download_from_aws(file_path)

    async def _download_from_gcp(self, file_path: str) -> Optional[bytes]:
        key = self._object_key(file_path)

        def _do() -> Optional[bytes]:
            blob = self.bucket.blob(key)
            if not blob.exists():
                return None
            return blob.download_as_bytes()

        try:
            return await asyncio.to_thread(_do)
        except Exception as exc:
            # google.api_core.exceptions.NotFound → treat as missing
            exc_name = type(exc).__name__
            if "NotFound" in exc_name or (hasattr(exc, "code") and exc.code == 404):
                return None
            logger.error("GCP download FAILED  key=%s  error=%s", key, exc)
            raise StorageDownloadError(
                f"GCP download failed for key '{key}': {exc}"
            ) from exc

    async def _download_from_aws(self, file_path: str) -> Optional[bytes]:
        key = self._object_key(file_path)

        def _do() -> bytes:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()

        try:
            return await asyncio.to_thread(_do)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "NoSuchBucket", "404"}:
                return None
            if code in {"AccessDenied", "403"}:
                raise StoragePermissionError(
                    f"AWS read denied on bucket '{self.bucket_name}' key '{key}'. "
                    "Add 's3:GetObject' to the IAM policy."
                ) from exc
            logger.error("AWS download FAILED  key=%s  code=%s  error=%s", key, code, exc)
            raise StorageDownloadError(
                f"AWS download failed for key '{key}': {exc}"
            ) from exc

    # ─ Delete ────────────────────────────────────────────────────────────────

    async def delete_file(self, file_path: str) -> None:
        """Delete *file_path*.  Silently succeeds if the object does not exist."""
        absolute_path = self._normalize_absolute_file_path(file_path)
        key = self._object_key(absolute_path)

        if self.storage_provider == "gcp":
            def _do() -> None:
                self.bucket.blob(key).delete()

            try:
                await asyncio.to_thread(_do)
            except Exception as exc:
                exc_name = type(exc).__name__
                if "NotFound" in exc_name or (hasattr(exc, "code") and exc.code == 404):
                    return
                logger.warning("GCP delete FAILED  key=%s  error=%s", key, exc)
                raise StorageError(f"GCP delete failed for key '{key}': {exc}") from exc

        else:  # aws — delete_object is idempotent; no error for missing keys
            def _do() -> None:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)

            try:
                await asyncio.to_thread(_do)
            except ClientError as exc:
                logger.warning("AWS delete FAILED  key=%s  error=%s", key, exc)
                raise StorageError(f"AWS delete failed for key '{key}': {exc}") from exc

    # ─ Get local path ────────────────────────────────────────────────────────

    async def get_file_path(self, file_path: str) -> str:
        """Download *file_path* to a unique local temp file; return its path.

        The caller is responsible for deleting the temp file when done.
        Uses a UUID prefix so concurrent calls for the same object are safe.
        """
        absolute_path = self._normalize_absolute_file_path(file_path)
        content = await self.download_file(absolute_path)
        if content is None:
            raise FileNotFoundError(
                f"Object not found in {self.storage_provider.upper()} storage: "
                f"{absolute_path}"
            )

        suffix = Path(absolute_path).suffix or ".tmp"
        tmp_dir = Path(__import__("tempfile").gettempdir()) / "evidence_analysis"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"{uuid.uuid4().hex}{suffix}"
        tmp_path.write_bytes(content)

        logger.debug(
            "Downloaded to temp  key=%s  tmp=%s  bytes=%d",
            self._object_key(absolute_path), tmp_path.name, len(content),
        )
        return str(tmp_path)

    # ─ Metadata ──────────────────────────────────────────────────────────────

    async def get_file_metadata(self, file_path: str) -> Optional[dict]:
        """Return ``{size_bytes, content_type}`` or *None* if the object is absent."""
        absolute_path = self._normalize_absolute_file_path(file_path)

        if self.storage_provider == "gcp":
            key = self._object_key(absolute_path)

            def _do() -> Optional[dict]:
                blob = self.bucket.blob(key)
                if not blob.exists():
                    return None
                blob.reload()
                return {
                    "size_bytes": int(blob.size or 0),
                    "content_type": blob.content_type,
                }

            try:
                return await asyncio.to_thread(_do)
            except Exception as exc:
                exc_name = type(exc).__name__
                if "NotFound" in exc_name or (hasattr(exc, "code") and exc.code == 404):
                    return None
                logger.error("GCP metadata FAILED  key=%s  error=%s", key, exc)
                raise StorageDownloadError(
                    f"GCP metadata fetch failed for key '{key}': {exc}"
                ) from exc

        # AWS
        key = self._object_key(absolute_path)

        def _do() -> dict:
            return self.s3_client.head_object(Bucket=self.bucket_name, Key=key)

        try:
            response = await asyncio.to_thread(_do)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            if code in {"403", "AccessDenied"}:
                raise StoragePermissionError(
                    f"AWS metadata denied on bucket '{self.bucket_name}' key '{key}'. "
                    "Add 's3:HeadObject' to the IAM policy."
                ) from exc
            logger.error("AWS metadata FAILED  key=%s  code=%s  error=%s", key, code, exc)
            raise StorageDownloadError(
                f"AWS metadata fetch failed for key '{key}': {exc}"
            ) from exc

        return {
            "size_bytes": int(response.get("ContentLength", 0)),
            "content_type": response.get("ContentType"),
        }

    # ── Signed URLs ───────────────────────────────────────────────────────────

    async def generate_upload_url(
        self,
        file_path: str,
        content_type: str,
        expiration: int = 900,
    ) -> dict:
        """Return a short-lived signed PUT URL for direct client upload.

        Content-Type is intentionally NOT included in the URL signature.
        See module docstring for the rationale.
        """
        absolute_path = self._normalize_absolute_file_path(file_path)
        key = self._object_key(absolute_path)

        if self.storage_provider == "gcp":
            def _do() -> str:
                blob = self.bucket.blob(key)
                return blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=expiration),
                    method="PUT",
                )

            try:
                signed_url = await asyncio.to_thread(_do)
            except Exception as exc:
                logger.error("GCP signed upload URL FAILED  key=%s  error=%s", key, exc)
                raise StorageError(
                    f"GCP signed upload URL generation failed for key '{key}'. "
                    "Ensure the service account has its private key in credentials "
                    "(full service-account JSON in CLOUD_STORAGE_SECRET). "
                    f"Detail: {exc}"
                ) from exc

            logger.debug("GCP signed upload URL OK  key=%s  exp=%ds", key, expiration)
            return {
                "url": signed_url,
                "method": "PUT",
                "headers": {},
                "expires_in_seconds": expiration,
            }

        # AWS
        def _do() -> str:
            return self.s3_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiration,
                HttpMethod="PUT",
            )

        try:
            signed_url = await asyncio.to_thread(_do)
        except Exception as exc:
            logger.error("AWS presigned upload URL FAILED  key=%s  error=%s", key, exc)
            raise StorageError(
                f"AWS presigned upload URL generation failed for key '{key}': {exc}"
            ) from exc

        logger.debug("AWS presigned upload URL OK  key=%s  exp=%ds", key, expiration)
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
        """Return a short-lived signed GET URL for direct client download."""
        absolute_path = self._normalize_absolute_file_path(file_path)
        key = self._object_key(absolute_path)

        if self.storage_provider == "gcp":
            safe_filename = (
                self.sanitize_filename(response_filename) if response_filename else None
            )

            def _do() -> str:
                blob = self.bucket.blob(key)
                kwargs: dict = {
                    "version": "v4",
                    "expiration": timedelta(seconds=expiration),
                    "method": "GET",
                }
                if safe_filename:
                    kwargs["response_disposition"] = (
                        f'attachment; filename="{safe_filename}"'
                    )
                return blob.generate_signed_url(**kwargs)

            try:
                signed_url = await asyncio.to_thread(_do)
            except Exception as exc:
                logger.error("GCP signed download URL FAILED  key=%s  error=%s", key, exc)
                raise StorageError(
                    f"GCP signed download URL generation failed for key '{key}'. "
                    "Ensure the service account has its private key in credentials. "
                    f"Detail: {exc}"
                ) from exc

            logger.debug("GCP signed download URL OK  key=%s  exp=%ds", key, expiration)
            return {
                "url": signed_url,
                "method": "GET",
                "headers": {},
                "expires_in_seconds": expiration,
            }

        # AWS
        params: dict = {"Bucket": self.bucket_name, "Key": key}
        if response_filename:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{self.sanitize_filename(response_filename)}"'
            )

        def _do() -> str:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expiration,
                HttpMethod="GET",
            )

        try:
            signed_url = await asyncio.to_thread(_do)
        except Exception as exc:
            logger.error("AWS presigned download URL FAILED  key=%s  error=%s", key, exc)
            raise StorageError(
                f"AWS presigned download URL generation failed for key '{key}': {exc}"
            ) from exc

        logger.debug("AWS presigned download URL OK  key=%s  exp=%ds", key, expiration)
        return {
            "url": signed_url,
            "method": "GET",
            "headers": {},
            "expires_in_seconds": expiration,
        }

    async def generate_presigned_url(self, file_path: str, expiration: int = 3600) -> str:
        """Backward-compatible wrapper — returns only the URL string."""
        signed = await self.generate_download_url(
            file_path=file_path, expiration=expiration
        )
        return signed["url"]
