"""Abstract storage adapter interface."""
from abc import ABC, abstractmethod
from typing import Any, List


class StorageAdapter(ABC):
    """Abstract base class for storage adapters.
    
    Implementations:
    - LocalStorageAdapter: Local filesystem storage
    - R2StorageAdapter: Cloudflare R2 / S3-compatible storage
    """
    
    @abstractmethod
    def store(self, path: str, data: Any) -> str:
        """Store data at the given path.
        
        Args:
            path: Relative path within the storage (e.g., "project_id/output/file.txt")
            data: Content to store (str or bytes)
            
        Returns:
            The full storage path where data was stored
        """
        pass
    
    @abstractmethod
    def retrieve(self, path: str) -> bytes:
        """Retrieve data from the given path.
        
        Args:
            path: Relative path within the storage
            
        Returns:
            The binary content stored at the path
        """
        pass
    
    @abstractmethod
    def list(self, prefix: str) -> List[str]:
        """List files under a given prefix.
        
        Args:
            prefix: Path prefix to search for
            
        Returns:
            List of relative paths matching the prefix
        """
        pass
