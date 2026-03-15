"""Architecture trigger service: eligibility check for architecture phase."""
import logging
from typing import Optional

from app.db import get_session, DiscoverySessionModel
from app.services.context_aggregator import get_repo_url_for_panel
from app.repositories.architecture_result_repo import ArchitectureResultRepository
from app.discovery.readiness_service import DiscoveryReadinessService
from app.discovery.checklist_service import ChecklistService
from app.discovery.question_service import QuestionService

logger = logging.getLogger(__name__)


def _get_effective_readiness(project_id: str) -> Optional[str]:
    """Compute readiness the same way as project context (quick_readiness_check)."""
    try:
        checklist = ChecklistService().get_checklist(project_id)
        open_questions = QuestionService().get_open_questions(project_id)
        result = DiscoveryReadinessService().quick_readiness_check(
            project_id, checklist=checklist, open_questions=open_questions
        )
        if isinstance(result, dict):
            return result.get("status")
    except Exception as e:
        logger.warning(f"Failed to get effective readiness for {project_id}: {e}")
    return None


class ArchitectureTriggerService:
    """Service for architecture phase eligibility (actual generation is in ArchitectureAgentService)."""

    @staticmethod
    def is_eligible(project_id: str) -> bool:
        """Check if project is eligible for architecture generation.

        Requires: readiness in (maybe_ready, ready_for_architecture), repo_url exists,
        architecture not already triggered, no architecture result yet.
        Uses live quick_readiness_check (same as project context), not DB readiness_status.
        """
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()

            if not discovery_session:
                logger.warning(f"No discovery session found for project {project_id}")
                return False

            if discovery_session.architecture_triggered:
                logger.info(f"Architecture already triggered for project {project_id}")
                return False
        finally:
            session.close()

        effective_status = _get_effective_readiness(project_id)
        if effective_status not in ("maybe_ready", "ready_for_architecture"):
            logger.info(
                f"Project {project_id} not ready for architecture (effective readiness: {effective_status})"
            )
            return False

        repo_url, has_repo_url = get_repo_url_for_panel(project_id)
        if not has_repo_url or not repo_url:
            logger.info(f"Project {project_id} has no linked repo URL")
            return False

        if ArchitectureResultRepository().get_latest(project_id) is not None:
            logger.info(f"Project {project_id} already has an architecture result")
            return False

        return True


__all__ = ["ArchitectureTriggerService"]
