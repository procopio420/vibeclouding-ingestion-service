from fastapi import APIRouter, HTTPException
from app.core.instrumentation import get_logger, log_event
logger = get_logger(__name__)
import uuid
import json

from app.api.schemas import (
    IngestImageRequest,
    IngestTextRequest,
    IngestRepoRequest,
    IngestDocumentRequest,
)

from app.celery_app import celery_app
from app.db import init_db, get_session, JobModel
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


@router.post("/projects/{project_id}/ingest/repo", response_model=dict)
async def ingest_repo(project_id: str, payload: IngestRepoRequest):
    init_db()
    session = get_session()
    results = []
    if not getattr(payload, 'repos', None):
        raise HTTPException(status_code=400, detail="repos field is required")
    for r in payload.repos:
        log_event(logger, "repo_ingest_request", {"project_id": project_id, "repo_url": r.repo_url, "reference": r.reference})
        job_id = str(uuid.uuid4())
        payload_json = json.dumps({"repo_url": r.repo_url, "reference": r.reference})
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
        # enqueue worker
        celery_app.send_task("repo_ingest_worker", args=[job_id, project_id, r.repo_url, r.reference], queue="repo_ingest")
        results.append({"job_id": job_id, "project_id": project_id, "job_type": "repo_ingest", "status": "queued"})
    session.close()
    return {"jobs": results}


@router.post("/projects/{project_id}/ingest/document", response_model=dict)
async def ingest_document(project_id: str, payload: IngestDocumentRequest):
    ingest_id = str(uuid.uuid4())
    return {"ingest_id": ingest_id, "status": "queued", "type": "document", "project_id": project_id}
