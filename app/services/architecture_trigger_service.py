"""Architecture trigger service: eligibility check for architecture phase."""
import logging

from app.db import get_session, DiscoverySessionModel
from app.services.context_aggregator import get_repo_url_for_panel
from app.repositories.architecture_result_repo import ArchitectureResultRepository
from app.discovery.readiness_service import DiscoveryReadinessService
from app.discovery.checklist_service import ChecklistService

logger = logging.getLogger(__name__)


class ArchitectureTriggerService:
    """Service for architecture phase eligibility (actual generation is in ArchitectureAgentService)."""

    @staticmethod
    def is_eligible(project_id: str) -> bool:
        """Check if project is eligible for architecture generation.

        Requires: readiness in (maybe_ready, ready_for_architecture), repo_url exists,
        architecture not already triggered, no architecture result yet.
        Uses the exact same readiness source as get_context: quick_readiness_check(project_id, checklist, None).
        Discovery session is resolved deterministically by updated_at desc when multiple exist.
        """
        session = get_session()
        try:
            discovery_session = (
                session.query(DiscoverySessionModel)
                .filter(DiscoverySessionModel.project_id == project_id)
                .order_by(DiscoverySessionModel.updated_at.desc())
                .first()
            )

            if not discovery_session:
                logger.warning(f"No discovery session found for project {project_id}")
                return False

            if discovery_session.architecture_triggered:
                logger.info(f"Architecture already triggered for project {project_id}")
                return False
        finally:
            session.close()

        # Same readiness as get_context (checklist + quick_readiness_check with open_questions=None)
        try:
            checklist = ChecklistService().get_checklist(project_id)
            result = DiscoveryReadinessService().quick_readiness_check(
                project_id, checklist, None
            )
            effective_status = result.get("status") if isinstance(result, dict) else None
        except Exception as e:
            logger.warning(f"Failed to get readiness for {project_id}: {e}")
            effective_status = None

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
