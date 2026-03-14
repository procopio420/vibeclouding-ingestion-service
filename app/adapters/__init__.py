"""Storage adapter factory and exports."""
import logging
import os

from app.adapters.storage_base import StorageAdapter

logger = logging.getLogger(__name__)

# Cache the storage adapter instance
_storage_adapter = None


def get_storage_adapter() -> StorageAdapter:
    """Get the configured storage adapter.
    
    Environment variables:
    - STORAGE_BACKEND: "local", "r2", or "minio" (default: "local")
    
    For R2:
    - R2_BUCKET: Bucket name
    - R2_ACCESS_KEY: Access key
    - R2_SECRET_KEY: Secret key  
    - R2_ENDPOINT: R2 endpoint URL
    - R2_REGION: Region (default: "auto")
    
    For MinIO (S3-compatible):
    - MINIO_ENDPOINT: http://minio:9000
    - MINIO_ACCESS_KEY: Access key
    - MINIO_SECRET_KEY: Secret key
    - MINIO_BUCKET: Bucket name
    
    For Local:
    - LOCAL_STORAGE_PATH: Base path (default: "./artifacts")
    
    Returns:
        Configured StorageAdapter instance
    """
    global _storage_adapter
    
    if _storage_adapter is not None:
        return _storage_adapter
    
    backend = os.environ.get("STORAGE_BACKEND", "local").lower()
    logger.info(f"Initializing storage adapter with backend: {backend}")
    
    if backend == "r2":
        from app.adapters.storage_r2 import R2StorageAdapter
        
        _storage_adapter = R2StorageAdapter(
            bucket=os.environ["R2_BUCKET"],
            access_key=os.environ["R2_ACCESS_KEY"],
            secret_key=os.environ["R2_SECRET_KEY"],
            endpoint=os.environ["R2_ENDPOINT"],
            region=os.environ.get("R2_REGION", "auto"),
        )
        logger.info("Using R2 storage adapter")
        
    elif backend == "minio":
        from app.adapters.storage_r2 import R2StorageAdapter
        
        _storage_adapter = R2StorageAdapter(
            bucket=os.environ.get("MINIO_BUCKET", "artifacts"),
            access_key=os.environ["MINIO_ACCESS_KEY"],
            secret_key=os.environ["MINIO_SECRET_KEY"],
            endpoint=os.environ["MINIO_ENDPOINT"],
            region=os.environ.get("MINIO_REGION", "us-east-1"),
        )
        logger.info("Using MinIO storage adapter")
        
    else:
        from app.adapters.storage_local import LocalStorageAdapter
        
        base_path = os.environ.get("LOCAL_STORAGE_PATH", "./artifacts")
        _storage_adapter = LocalStorageAdapter(base_path=base_path)
        logger.info(f"Using local storage adapter at: {base_path}")
    
    return _storage_adapter


def reset_storage_adapter():
    """Reset the cached storage adapter (useful for testing)."""
    global _storage_adapter
    _storage_adapter = None


__all__ = ["StorageAdapter", "get_storage_adapter", "reset_storage_adapter"]
