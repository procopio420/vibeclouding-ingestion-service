"""Lifecycle tracking for discovery questions (asked/answered/state)."""
import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)


class QuestionLifecycleService:
    """Lifecycle tracking for discovery questions.
    DB-backed persistence is implemented via DiscoveryQuestionLifecycleModel.
    This class exposes helpers that operate per-project.
    """

    def __init__(self, project_id: Optional[str] = None):
        self.asked_keys: Set[str] = set()
        self.answered_keys: Set[str] = set()
        self.current_focus_key: Optional[str] = None
        if project_id:
            self.load_state(project_id)

    def load_state(self, project_id: str) -> None:
        """Load asked/answered state from DB at start of each request."""
        self.asked_keys.clear()
        self.answered_keys.clear()
        try:
            from app.discovery.lifecycle_repository import DiscoveryQuestionLifecycleRepository
            repo = DiscoveryQuestionLifecycleRepository(project_id)
            rows = repo.get_state()
            for row in rows:
                key = row.get("intent_key")
                if not key:
                    continue
                status = row.get("status")
                if status == "answered":
                    self.answered_keys.add(key)
                else:
                    self.asked_keys.add(key)
            logger.info(f"[Lifecycle] Loaded state for {project_id}: asked={list(self.asked_keys)}, answered={list(self.answered_keys)}")
        except Exception as e:
            logger.warning(f"[Lifecycle] Failed to load state for {project_id}: {e}")

    def mark_asked(self, project_id: str, key: str) -> None:
        if key:
            self.asked_keys.add(key)
            try:
                from app.discovery.lifecycle_repository import DiscoveryQuestionLifecycleRepository
                repo = DiscoveryQuestionLifecycleRepository(project_id)
                repo.upsert(key, status="open")
            except Exception:
                pass

    def mark_answered(self, project_id: str, key: str) -> None:
        if key:
            self.answered_keys.add(key)
            try:
                from app.discovery.lifecycle_repository import DiscoveryQuestionLifecycleRepository
                repo = DiscoveryQuestionLifecycleRepository(project_id)
                repo.upsert(key, status="answered")
            except Exception:
                pass

    def clear(self) -> None:
        self.asked_keys.clear()
        self.answered_keys.clear()
        self.current_focus_key = None
__all__ = ["QuestionLifecycleService"]
