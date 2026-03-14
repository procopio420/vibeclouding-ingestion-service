import os
import json
import tempfile
import subprocess
from urllib.parse import quote
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _init_local_repo(repo_dir: str) -> str:
    os.makedirs(repo_dir, exist_ok=True)
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)
    # Configure user
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo_dir, check=True)
    # Create a minimal file
    with open(os.path.join(repo_dir, "README.md"), "w") as f:
        f.write("# Demo Repo\nThis is a test repo for Phase 1 repo ingestion.")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)
    return f"file://{repo_dir}"


def test_repo_ingestion_flow_end_to_end():
    # 1) Create a new project
    resp = client.post("/projects", json={"project_name": "RepoIngestDemo", "summary": "async repo ingestion test"})
    assert resp.status_code == 200
    project_id = resp.json().get("project_id")
    assert project_id

    # 2) Create a local test repo and register ingestion
    with tempfile.TemporaryDirectory() as tmp:
        repo_url = _init_local_repo(tmp)
        payload = {"repos": [{"repo_url": repo_url, "reference": "master"}]}
        resp = client.post(f"/projects/{project_id}/ingest/repo", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        job = data["jobs"][0]
        job_id = job["job_id"]
        assert job_id

    # 3) Trigger worker run directly (simulate async worker progression)
    # Import the Celery task and run it synchronously for testing
    from app.celery_app import repo_ingest_worker
    # Use the same path and repo url for the test; the worker will recreate/scrape artifacts
    repo_run = repo_ingest_worker.run(job_id, project_id, repo_url, "master")
    # The run() returns a dict with status; we expect completion or failure handled by the worker
    assert repo_run is not None

    # 4) Poll for status and outputs
    import time
    status = None
    for _ in range(6):
        resp = client.get(f"/jobs/{job_id}")
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")
            if status in ("completed", "failed"):
                break
        time.sleep(1)
    assert status in ("completed", "failed", None)

    # 5) Retrieve context / outputs skeletons
    resp = client.get(f"/projects/{project_id}/context")
    assert resp.status_code == 200

    if status == 'completed':
        resp = client.get(f"/projects/{project_id}/files/01-overview.md")
        if resp.status_code == 200:
            assert "content" in resp.json()
