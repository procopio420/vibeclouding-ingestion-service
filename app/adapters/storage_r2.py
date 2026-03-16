"""Cloudflare R2 / S3-compatible storage adapter."""
import logging
from typing import Any, List

import boto3
from botocore.config import Config

from app.adapters.storage_base import StorageAdapter

logger = logging.getLogger(__name__)


class R2StorageAdapter(StorageAdapter):
    """Storage adapter for Cloudflare R2 (S3-compatible API).
    
    Environment variables:
    - R2_BUCKET: Bucket name
    - R2_ACCESS_KEY: Access key
    - R2_SECRET_KEY: Secret key
    - R2_ENDPOINT: R2 endpoint URL (e.g., https://account.r2.cloudflarestorage.com)
    - R2_REGION: Region (default: auto)
    """
    
    def __init__(self, bucket: str, access_key: str, secret_key: str, 
                 endpoint: str, region: str = "auto"):
        self.bucket = bucket
        self.client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version='s3v4')
        )
        logger.info(f"R2StorageAdapter initialized with bucket: {bucket}")
    
    def store(self, path: str, data: Any) -> str:
        """Store data in R2.
        
        Args:
            path: Relative path (e.g., "project_id/output/markdown/01-overview.md")
            data: Content to store (str or bytes)
            
        Returns:
            The full R2 URI (e.g., "r2://bucket/project_id/output/markdown/01-overview.md")
        """
        # Encode string to bytes if needed
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        self.client.put_object(
            Bucket=self.bucket,
            Key=path,
            Body=data
        )
        
        uri = f"r2://{self.bucket}/{path}"
        logger.info(f"Stored data at: {uri}")
        return uri
    
    def retrieve(self, path: str) -> bytes:
        """Retrieve data from R2.
        
        Args:
            path: Relative path to retrieve
            
        Returns:
            Binary content from R2
        """
        response = self.client.get_object(
            Bucket=self.bucket,
            Key=path
        )
        return response['Body'].read()
    
    def list(self, prefix: str) -> List[str]:
        """List files in R2 with given prefix.

        Args:
            prefix: Path prefix to search

        Returns:
            List of relative paths
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            if 'Contents' not in response:
                return []
            return [obj['Key'] for obj in response['Contents']]
        except Exception as e:
            logger.warning(f"Error listing objects with prefix {prefix}: {e}")
            return []

    def get_presigned_get_url(self, path: str, expires_in: int = 3600) -> str:
        """Return a presigned GET URL so the object can be fetched via HTTP without credentials.

        Args:
            path: Relative path (storage key) of the object.
            expires_in: URL validity in seconds (default 1 hour).

        Returns:
            Presigned HTTP URL string.
        """
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": path},
            ExpiresIn=expires_in,
        )
        return url
