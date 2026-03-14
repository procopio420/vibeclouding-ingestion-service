"""API routes for architecture results."""
import json
import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import ArchitectureResultResponse
from app.db import get_session, ProjectModel
from app.repositories.architecture_result_repo import (
    ArchitectureResultRepository,
    parse_architecture_result,
)

logger = logging.getLogger(__name__)

router = APIRouter()
repo = ArchitectureResultRepository()


@router.post("/projects/{project_id}/architecture-result", response_model=ArchitectureResultResponse)
async def create_architecture_result(project_id: str, payload: dict):
    """Save an architecture result for a project.
    
    This endpoint:
    1. Validates the project exists
    2. Validates the payload is valid JSON
    3. Uploads raw JSON to object storage
    4. Saves structured data to database
    5. Updates project status to 'architecture_ready'
    """
    session = get_session()
    project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    session.close()
    
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    if isinstance(payload, dict):
        payload_dict = payload
    elif hasattr(payload, 'dict'):
        payload_dict = payload.dict()
    else:
        raise HTTPException(
            status_code=422,
            detail="Request body must be a JSON object"
        )
    
    logger.info(f"=== ARCHITECTURE RESULT RECEIVED ===")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Payload type: {type(payload_dict)}")
    logger.info(f"Payload keys: {list(payload_dict.keys()) if hasattr(payload_dict, 'keys') else 'N/A'}")
    logger.info(f"analise_entrada type: {type(payload_dict.get('analise_entrada'))}")
    logger.info(f"analise_entrada value: {str(payload_dict.get('analise_entrada'))[:200] if payload_dict.get('analise_entrada') else 'None'}")
    logger.info(f"vibe_economica type: {type(payload_dict.get('vibe_economica'))}")
    logger.info(f"vibe_performance type: {type(payload_dict.get('vibe_performance'))}")
    logger.info(f"=== END ARCHITECTURE RESULT ===")
    
    try:
        model = repo.save(project_id, payload_dict)
        return parse_architecture_result(model)
    except Exception as e:
        logger.error(f"Failed to save architecture result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save architecture result: {str(e)}")


@router.get("/projects/{project_id}/architecture-result", response_model=ArchitectureResultResponse)
async def get_architecture_result(project_id: str):
    """Get the latest architecture result for a project."""
    session = get_session()
    project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    session.close()
    
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    model = repo.get_latest(project_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"No architecture result found for project {project_id}")
    
    return parse_architecture_result(model)


__all__ = ["router"]
