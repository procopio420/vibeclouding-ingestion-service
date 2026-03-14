"""Local filesystem storage adapter for artifacts (Phase 1 skeleton)."""
import os
from typing import Any


class LocalStorageAdapter:
    def __init__(self, base_path: str = "./artifacts"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _full_path(self, path: str) -> str:
        return os.path.join(self.base_path, path)

    def store(self, path: str, data: Any) -> str:
        full = self._full_path(path)
        dirpath = os.path.dirname(full)
        os.makedirs(dirpath, exist_ok=True)
        mode = 'wb' if isinstance(data, (bytes, bytearray)) else 'w'
        with open(full, mode) as f:
            f.write(data)
        return full

    def retrieve(self, path: str) -> bytes:
        full = self._full_path(path)
        with open(full, 'rb') as f:
            return f.read()

    def list(self, prefix: str) -> list:
        """List files under a given prefix inside the base storage."""
        root = self._full_path(prefix)
        if not os.path.exists(root):
            return []
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), self.base_path)
                files.append(rel)
        return files
