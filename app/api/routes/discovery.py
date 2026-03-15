"""Discovery API routes - DEPRECATED in favor of WebSocket.

All discovery functionality is now available via WebSocket:
    /ws/discovery/{project_id}

WebSocket events:
- session.start: Start a discovery session
- message.create: Send a chat message
- checklist.update: Update a checklist item
- question.answer: Answer a clarification question
- connection.ready: Full state on connect (session, messages, checklist, readiness, questions)

This file also exposes GET /projects/{id}/discovery/panel for the right-side repo/architecture panel.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.db import get_session, DiscoverySessionModel, ProjectModel
from app.services.context_aggregator import get_repo_url_for_panel
from app.repositories.architecture_result_repo import ArchitectureResultRepository

logger = logging.getLogger(__name__)

router = APIRouter()
_arch_repo = ArchitectureResultRepository()


def _verify_project_exists(project_id: str) -> None:
    """Verify project exists."""
    session = get_session()
    project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    session.close()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.get("/projects/{project_id}/discovery/panel")
async def get_discovery_panel(project_id: str) -> Dict[str, Any]:
    """Return repo panel and architecture panel state for the right-side UI.

    Single source of truth: repo_panel (has_repo_url, repo_url, repo_status) and
    architecture_panel (can_start_architecture, architecture_status, etc.).
    """
    _verify_project_exists(project_id)

    repo_url, has_repo_url = get_repo_url_for_panel(project_id)
    repo_panel = {
        "has_repo_url": has_repo_url,
        "repo_url": repo_url,
        "repo_status": "linked" if has_repo_url else "missing",
    }

    session = get_session()
    try:
        discovery_session = session.query(DiscoverySessionModel).filter(
            DiscoverySessionModel.project_id == project_id
        ).first()
    finally:
        session.close()

    architecture_triggered = False
    readiness_status = "not_ready"
    if discovery_session:
        architecture_triggered = bool(discovery_session.architecture_triggered)
        readiness_status = discovery_session.readiness_status or "not_ready"

    arch_result = _arch_repo.get_latest(project_id)
    architecture_result_available = arch_result is not None

    if architecture_result_available:
        architecture_status = "result_available"
    elif architecture_triggered:
        architecture_status = "triggered"
    else:
        architecture_status = "not_started"

    can_start_architecture = (
        readiness_status in ("maybe_ready", "ready_for_architecture")
        and has_repo_url
        and not architecture_triggered
        and not architecture_result_available
    )

    architecture_panel = {
        "can_start_architecture": can_start_architecture,
        "architecture_status": architecture_status,
        "architecture_triggered": architecture_triggered,
        "architecture_result_available": architecture_result_available,
    }

    return {
        "repo_panel": repo_panel,
        "architecture_panel": architecture_panel,
        "can_start_architecture": can_start_architecture,
    }


__all__ = ["router"]
