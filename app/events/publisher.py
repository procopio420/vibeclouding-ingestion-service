"""Tiny in-memory event bus stub for Phase 3: Event stub path."""

from typing import List, Optional

from app.events.contracts import DomainEvent, IntegrationEvent


class InMemoryEventBus:
    def __init__(self) -> None:
        self.outbox: List[IntegrationEvent] = []

    def publish(self, event: IntegrationEvent) -> str:
        self.outbox.append(event)
        return event.event_id

    def drain(self) -> List[IntegrationEvent]:
        items = list(self.outbox)
        self.outbox.clear()
        return items

bus = InMemoryEventBus()


def publish_domain_event(domain_event: DomainEvent) -> str:
    """Convert a domain event to an integration event and publish to the in-memory bus."""
    from app.events.contracts import to_integration_event

    integration = to_integration_event(domain_event, integration_metadata={"source": "tiny-stub"})
    return bus.publish(integration)


def get_outbox() -> List[IntegrationEvent]:
    return bus.outbox
