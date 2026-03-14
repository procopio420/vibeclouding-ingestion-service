"""Git adapter (skeleton)."""
import os

def clone_public_repo(repo_url: str, dest: str) -> str:
    # Placeholder: in real world we'd run git, here we just return the destination path
    os.makedirs(dest, exist_ok=True)
    return dest
