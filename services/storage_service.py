"""
Storage Service
Handles file storage abstraction (GCP, S3, or local filesystem)
"""
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
from typing import Optional
import logging
import json
import tempfile

from core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for file storage operations (GCP, S3, or local)"""
    
    def __init__(self):
        self.storage_type = settings.STORAGE_TYPE
        
        if self.storage_type == "gcp":
            # Initialize GCP Storage Client
            from google.cloud import storage
            from google.oauth2 import service_account
            
            # Parse the service account key from environment
            credentials_dict = {
                "type": "service_account",
                "project_id": settings.CLOUD_STORAGE_PROJECT,
                "private_key": settings.CLOUD_STORAGE_SECRET.replace('\\n', '\n'),
                "client_email": settings.CLOUD_STORAGE_ACCOUNTNAME,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict
            )
            
            self.gcs_client = storage.Client(
                credentials=credentials,
                project=settings.CLOUD_STORAGE_PROJECT
            )
            self.bucket_name = settings.CLOUD_STORAGE_BUCKETNAME
            self.bucket = self.gcs_client.bucket(self.bucket_name)
            logger.info(f"Initialized GCP storage with bucket: {self.bucket_name}")
            
        elif self.storage_type == "s3":
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.bucket_name = settings.S3_BUCKET_NAME
            logger.info(f"Initialized S3 storage with bucket: {self.bucket_name}")
        else:
            self.local_path = Path(settings.LOCAL_STORAGE_PATH)
            self.local_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initialized local storage at: {self.local_path}")
    
    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload file to storage
        Returns: Storage URL/path
        """
        if self.storage_type == "gcp":
            return await self._upload_to_gcp(file_content, filename, content_type)
        elif self.storage_type == "s3":
            return await self._upload_to_s3(file_content, filename, content_type)
        else:
            return await gcp(
        self,
        file_content: bytes,
        filename: str,
        content_type: str
    ) -> str:
        """Upload file to Google Cloud Storage"""
        try:
            blob = self.bucket.blob(filename)
            blob.upload_from_string(
                file_content,
                content_type=content_type
            )
            
            # Return GCS URL
            url = f"gs://{self.bucket_name}/{filename}"
            logger.info(f"Uploaded file to GCS: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {str(e)}")
            raise Exception(f"GCS upload failed: {str(e)}")
    
    async def _upload_to_self._upload_to_local(file_content, filename)
    
    async def _upload_to_s3(
        self,
        file_content: bytes,
        filename: str,
        content_type: str
    ) -> str:
        """Upload file to AWS S3"""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=file_content,
                ContentType=content_type
            )
            gcp":
            return await self._download_from_gcp(file_url)
        elif self.storage_type == "
            # Return S3 URL
            url = f"s3://{self.bucket_name}/{filename}"
            logger.info(f"Uplgcp(self, gcs_url: str) -> Optional[bytes]:
        """Download file from Google Cloud Storage"""
        try:
            # Parse GCS URL
            key = gcs_url.replace(f"gs://{self.bucket_name}/", "")
            
            blob = self.bucket.blob(key)
            content = blob.download_as_bytes()
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to download from GCS: {str(e)}")
            return None
    
    async def _download_from_oaded file to S3: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload to S3: {str(e)}")
            raise Exception(f"S3 upload failed: {str(e)}")
    
    async def _upload_to_local(self, file_content: bytes, filename: str) -> str:
        """Upload file to local filesystem"""
        file_path = self.local_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        logger.info(f"Uploaded file to local: {file_path}")
        return str(file_path)
    
    async def download_file(self, file_url: str) -> Optional[bytes]:
        """Download file from storage"""
        if self.storage_type == "s3":
            return await self._download_from_s3(file_url)
        else:
            return await self._download_from_local(file_url)
    
    async def _download_from_s3(self, s3_url: str) -> Optional[bytes]:
        """Download file from AWS S3"""
        try:
            # Parse S3 URL
            key = s3_url.replace(f"s3://{self.bucket_name}/", "")
            
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            cloud if needed)"""
        if self.storage_type == "local":
            return file_url
        else:
            # For cloud storage (GCP/S3), download to temp location
            content = await self.download_file(file_url)
            if not content:
                raise Exception(f"Failed to download file: {file_url}")
            
            # Save to temp file
            temp_dir = Path(tempfile.gettempdir()) / "evidence_analysis"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / file_url.split("/")[-1]
        except Exception as e:
            logger.error(f"Failed to read local file: {str(e)}")
            return None
    
    async def get_file_path(self, file_url: str) -> str:
        """Get local file path (downloads from S3 if needed)"""
        if self.storage_type == "local":
            return file_url
        else:signed URL for secure file access (cloud storage)"""
        if self.storage_type == "local":
            return file_url
        
        try:
            if self.storage_type == "gcp":
                # Generate GCS signed URL
                key = file_url.replace(f"gs://{self.bucket_name}/", "")
                blob = self.bucket.blob(key)
                
                from datetime import timedelta
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=expiration),
                    method="GET"
                )
                return url
                
            elif self.storage_type == "s3":
                # Generate S3 presigned URL
                key = file_url.replace(f"s3://{self.bucket_name}/", "")
                
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': key},
                    ExpiresIn=expiration
                )
                return url
            
            return file_url
            
        except Exception as e:
            logger.error(f"Failed to generate e access (S3 only)"""
        if self.storage_type != "s3":
            return file_url
        
        try:
            key = file_url.replace(f"s3://{self.bucket_name}/", "")
            
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return file_url
