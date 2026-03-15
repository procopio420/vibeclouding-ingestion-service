from fastapi import APIRouter, HTTPException
from app.core.instrumentation import get_logger, log_event
logger = get_logger(__name__)
import uuid
import json

from app.api.schemas import (
    IngestImageRequest,
    IngestTextRequest,
    IngestDocumentRequest,
)

from app.celery_app import celery_app
from app.db import init_db, get_session, JobModel, ProjectModel
from datetime import datetime

router = APIRouter()


@router.post("/projects/{project_id}/ingest/image", response_model=dict)
async def ingest_image(project_id: str, payload: IngestImageRequest):
    ingest_id = str(uuid.uuid4())
    return {"ingest_id": ingest_id, "status": "queued", "type": "image", "project_id": project_id}


@router.post("/projects/{project_id}/ingest/text", response_model=dict)
async def ingest_text(project_id: str, payload: IngestTextRequest):
    ingest_id = str(uuid.uuid4())
    return {"ingest_id": ingest_id, "status": "queued", "type": "text", "project_id": project_id}


def _normalize_repo_payload(body: dict) -> list:
    """Accept { repo_url } or { repos: [...] }, return list of (repo_url, reference)."""
    if not body:
        return []
    if "repo_url" in body:
        url = body.get("repo_url") or ""
        ref = body.get("reference") or "main"
        return [(str(url).strip(), ref)] if url else []
    if "repos" in body and isinstance(body["repos"], list):
        out = []
        for r in body["repos"]:
            if isinstance(r, dict) and r.get("repo_url"):
                out.append((str(r["repo_url"]).strip(), r.get("reference") or "main"))
            elif hasattr(r, "repo_url"):
                out.append((str(r.repo_url).strip(), getattr(r, "reference", None) or "main"))
        return out
    return []


@router.api_route("/projects/{project_id}/repo", methods=["POST", "PATCH"], response_model=dict)
async def ingest_repo(project_id: str, payload: dict):
    """Accept { "repo_url": "https://github.com/owner/repo" } or { "repos": [ { "repo_url", "reference" } ] }."""
    init_db()
    session = get_session()

    project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        session.close()
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    repos = _normalize_repo_payload(payload)
    if not repos:
        session.close()
        raise HTTPException(status_code=400, detail="repo_url or repos is required")

    results = []
    for repo_url, reference in repos:
        log_event(logger, "repo_ingest_request", {"project_id": project_id, "repo_url": repo_url, "reference": reference})
        job_id = str(uuid.uuid4())
        payload_json = json.dumps({"repo_url": repo_url, "reference": reference})
        job = JobModel(
            id=job_id,
            project_id=project_id,
            job_type="repo_ingest",
            status="queued",
            payload=payload_json,
            created_at=datetime.utcnow(),
        )
        session.add(job)
        session.commit()
        celery_app.send_task("repo_ingest_worker", args=[job_id, project_id, repo_url, reference], queue="repo_ingest")
        results.append({"job_id": job_id, "project_id": project_id, "job_type": "repo_ingest", "status": "queued"})
    session.close()
    return {"jobs": results}


@router.post("/projects/{project_id}/ingest/document", response_model=dict)
async def ingest_document(project_id: str, payload: IngestDocumentRequest):
    ingest_id = str(uuid.uuid4())
    return {"ingest_id": ingest_id, "status": "queued", "type": "document", "project_id": project_id}
