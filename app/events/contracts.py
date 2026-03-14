from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event identifier")
    event_type: str = Field(..., description="Event type name (e.g., 'DomainUpdated', 'UserCreated')")
    version: int = Field(1, description="Event contract version")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing across services")
    causation_id: Optional[str] = Field(None, description="Causation ID linking to the initiating event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event emission timestamp")


class DomainEvent(Event):
    domain: Optional[str] = Field(None, description="Optional domain identifier/classification")


class IntegrationEvent(Event):
    integration_metadata: Optional[Dict[str, Any]] = Field(None, description="Optional integration metadata for transport")


def build_domain_event(
    event_type: str,
    payload: Dict[str, Any],
    domain: Optional[str] = None,
    correlation_id: Optional[str] = None,
    causation_id: Optional[str] = None,
) -> DomainEvent:
    """Construct a domain event from high-level inputs without mutation side-effects."""
    return DomainEvent(
        event_type=event_type,
        payload=payload,
        domain=domain,
        correlation_id=correlation_id,
        causation_id=causation_id,
        version=1,
    )


def to_integration_event(
    domain_event: DomainEvent,
    integration_metadata: Optional[Dict[str, Any]] = None,
) -> IntegrationEvent:
    """Convert a domain event to an integration event payload for transport."""
    return IntegrationEvent(
        event_type=domain_event.event_type,
        payload=domain_event.payload,
        correlation_id=domain_event.correlation_id,
        causation_id=domain_event.causation_id,
        integration_metadata=integration_metadata,
        version=1,
    )
