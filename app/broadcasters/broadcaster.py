"""Broadcast interface for cross-instance/event delivery.

This is a protocol-like base to enable future Redis/pubsub wiring.
"""
from typing import Protocol, Any


class Broadcaster(Protocol):
    async def publish(self, topic: str, event: Any) -> None:
        ...
