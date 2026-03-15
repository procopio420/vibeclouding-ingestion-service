from fastapi import APIRouter, HTTPException
import uuid
from datetime import datetime

from app.api.schemas import ProjectCreate, ProjectInfo
from app.db import init_db, get_session, ProjectModel
from app.discovery.orchestrator import DiscoveryOrchestrator

router = APIRouter()

orchestrator = DiscoveryOrchestrator()


@router.post("/projects", response_model=ProjectInfo)
async def create_project(payload: ProjectCreate):
    init_db()
    session = get_session()
    project_id = str(uuid.uuid4())
    proj = ProjectModel(
        id=project_id, 
        name=payload.project_name, 
        summary=payload.summary,
        status="collecting_initial_context",
        created_at=datetime.utcnow()
    )
    session.add(proj)
    session.commit()
    session.close()
    
    try:
        discovery_result = orchestrator.start_discovery(project_id, payload.project_name or "")
        return ProjectInfo(project_id=project_id, status="collecting_initial_context")
    except Exception as e:
        return ProjectInfo(project_id=project_id, status="created")


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    session = get_session()
    proj = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    session.close()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_id": proj.id,
        "project_name": proj.name,
        "summary": proj.summary,
    }


@router.get("/projects")
async def list_projects():
    """Get all projects with their IDs."""
    session = get_session()
    projects = session.query(ProjectModel).order_by(ProjectModel.created_at.desc()).all()
    session.close()
    return {
        "projects": [
            {
                "project_id": p.id,
                "project_name": p.name,
                "summary": p.summary,
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in projects
        ]
    }


@router.get("/projects/{project_id}/status")
async def get_project_status(project_id: str):
    session = get_session()
    proj = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    session.close()
    if not proj:
        return {"project_id": project_id, "status": "not_found"}
    return {"project_id": project_id, "status": "existing"}
