"""Deterministic next-question selector for discovery phase."""
from typing import List, Dict, Optional

from app.discovery.question_intents import QUESTION_INTENTS


class QuestionSelector:
    """Select the next best question deterministically based on checklist state."""

    def select(
        self,
        checklist: List[Dict[str, any]],
        asked_keys: List[str],
        answered_keys: List[str],
        readiness: Dict[str, any],
    ) -> Optional[str]:
        # Build a list of candidate keys that are missing/unaddressed
        missing = [c for c in checklist if c.get("status") in ("missing", "open") or c.get("status") == None]
        candidate_keys = []
        for item in missing:
            key = item.get("key")
            if not key:
                continue
            if key in answered_keys:
                continue
            if key in asked_keys:
                continue
            candidate_keys.append(key)

        # Sort candidates by priority defined in QUESTION_INTENTS
        def priority_of(key: str) -> int:
            for intent, meta in QUESTION_INTENTS.items():
                if meta.get("checklist_key") == key:
                    from enum import Enum
                    pr = meta.get("priority", "low")
                    mapping = {"high": 0, "medium": 1, "low": 2}
                    return mapping.get(pr, 2)
            return 99

        candidate_keys.sort(key=priority_of)
        chosen = candidate_keys[0] if candidate_keys else None
        return chosen
