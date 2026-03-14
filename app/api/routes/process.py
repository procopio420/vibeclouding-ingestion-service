from fastapi import APIRouter
import uuid
from typing import Dict, Any

router = APIRouter()


@router.post("/projects/{project_id}/process")
async def start_processing(project_id: str) -> Dict[str, Any]:
    # Placeholder processing start; in real life we'd enqueue a Celery task
    process_id = str(uuid.uuid4())
    return {"process_id": process_id, "project_id": project_id, "status": "started"}


@router.post("/projects/{project_id}/reprocess")
async def reprocess(project_id: str) -> Dict[str, Any]:
    process_id = str(uuid.uuid4())
    return {"process_id": process_id, "project_id": project_id, "status": "restarted"}
