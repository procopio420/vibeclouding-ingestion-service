"""Shared helpers for discovery panel state (understanding_summary, next_best_step).
Used by GET /context and WebSocket connection.ready so logic stays single-sourced.
"""
from typing import Any, Dict, Optional


def build_understanding_summary(project_id: str) -> Dict[str, Any]:
    """Derive a compact understanding summary from current checklist items."""
    try:
        from app.discovery.checklist_service import ChecklistService
        cs = ChecklistService()
        checklist = cs.get_checklist(project_id)
        items = []
        for it in checklist:
            status = it.get("status")
            if status in ("confirmed", "inferred"):
                value = it.get("value") or it.get("evidence") or status
                items.append({
                    "key": it.get("key"),
                    "label": it.get("label"),
                    "value": value,
                    "source": status,
                })
        return {"items": items}
    except Exception:
        return {"items": []}


def compute_next_best_step(project_id: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Compute the next best step for discovery context.
    context is optional and kept for API compatibility; computation uses DB state.
    """
    try:
        from app.discovery.lifecycle_repository import DiscoveryQuestionLifecycleRepository
        from app.discovery.question_selector import QuestionSelector
        from app.discovery.question_intents import QUESTION_INTENTS
        from app.discovery.checklist_service import ChecklistService
        from app.discovery.readiness_service import DiscoveryReadinessService

        life_repo = DiscoveryQuestionLifecycleRepository(project_id)
        state = life_repo.get_state()
        asked_keys = [str(row.get("intent_key")) for row in state if row.get("status") == "open" and row.get("intent_key")]
        answered_keys = [str(row.get("intent_key")) for row in state if row.get("status") == "answered" and row.get("intent_key")]

        checklist = ChecklistService().get_checklist(project_id)
        readiness = DiscoveryReadinessService().quick_readiness_check(project_id, checklist, None)
        next_key = QuestionSelector().select(checklist, asked_keys, answered_keys, readiness)
        if not next_key:
            return None

        title = None
        for intent, meta in QUESTION_INTENTS.items():
            if meta.get("checklist_key") == next_key:
                title = meta.get("question")
                break
        if not title:
            from app.discovery.config import NEXT_STEP_FALLBACK
            title = f"{NEXT_STEP_FALLBACK}{next_key}"

        step_type = "repo" if next_key == "repo_exists" else "clarification"
        description = None
        if next_key == "repo_exists":
            from app.discovery.config import NEXT_STEP_DESCRIPTIONS_PT
            description = NEXT_STEP_DESCRIPTIONS_PT.get("repo_exists", "Verificar se existe um repositório para o projeto.")
        else:
            try:
                from app.discovery.question_service import QUESTION_TEMPLATES
                description = QUESTION_TEMPLATES.get(next_key)
            except Exception:
                description = None
            if not description:
                from app.discovery.config import NEXT_STEP_DESCRIPTIONS_PT
                description = NEXT_STEP_DESCRIPTIONS_PT.get(next_key, f"Necessária clarification para {next_key}.")
        return {"title": title, "description": description, "type": step_type}
    except Exception:
        return None
