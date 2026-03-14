"""Tiny event-publish test route (tiny in-memory stub)."""

from fastapi import APIRouter
from typing import Dict, Any

from app.events.publisher import publish_domain_event
from app.events.contracts import DomainEvent

router = APIRouter()


@router.post("/projects/{project_id}/events/stub")
async def publish_stub_event(project_id: str) -> Dict[str, Any]:
    # Create a small domain event and publish via the tiny in-memory bus
    domain_event = DomainEvent(
        event_type="TinyTestEvent",
        payload={"project_id": project_id, "note": "tiny event stub"},
        domain="ingestor",
    )
    event_id = publish_domain_event(domain_event)
    return {"published_event_id": event_id, "project_id": project_id}
