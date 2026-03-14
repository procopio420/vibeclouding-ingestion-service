"""Discovery API routes - DEPRECATED in favor of WebSocket.

All discovery functionality is now available via WebSocket:
    /ws/discovery/{project_id}

WebSocket events:
- session.start: Start a discovery session
- message.create: Send a chat message
- checklist.update: Update a checklist item
- question.answer: Answer a clarification question
- connection.ready: Full state on connect (session, messages, checklist, readiness, questions)

This file now only contains basic project existence endpoints.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.db import get_session, ProjectModel

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_project_exists(project_id: str) -> None:
    """Verify project exists."""
    session = get_session()
    project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    session.close()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


__all__ = ["router"]
