"""Simple in-memory broadcaster for development and MVP.

This allows components to publish events to subscribers within the same process.
For multi-process deployments, swap in a Redis-backed broadcaster later.
"""
import asyncio
from typing import Callable, DefaultDict, Dict, List
from collections import defaultdict

class InMemoryBroadcaster:
    def __init__(self):
        self._subs: DefaultDict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, topic: str, callback: Callable[[dict], None]) -> None:
        self._subs[topic].append(callback)

    async def publish(self, topic: str, event: dict) -> None:
        for cb in self._subs.get(topic, []):
            try:
                cb(event)
            except Exception:
                pass

__all__ = ["InMemoryBroadcaster"]
