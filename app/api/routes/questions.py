"""Questions API routes - DEPRECATED in favor of WebSocket.

All questions functionality is now available via WebSocket:
    /ws/discovery/{project_id}

WebSocket events for questions:
- question.answer: Answer a clarification question
- connection.ready: Contains open questions
- question.asked: When a new question is raised
- question.answered: When a question is answered
"""
from fastapi import APIRouter

router = APIRouter()


__all__ = ["router"]
