"""Architecture trigger service for discovery-to-architecture phase transition."""
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from app.db import get_session, DiscoverySessionModel, ProjectModel
from app.services.context_aggregator import get_repo_url_for_panel
from app.repositories.architecture_result_repo import ArchitectureResultRepository

logger = logging.getLogger(__name__)

ARCHITECTURE_WEBHOOK_URL = os.environ.get(
    "ARCHITECTURE_WEBHOOK_URL",
    "https://boccaletti.vps-kinghost.net:5678/webhook-test/vibe-arch-input"
)


class ArchitectureTriggerService:
    """Service for triggering architecture phase when project becomes eligible."""

    @staticmethod
    def is_eligible(project_id: str) -> bool:
        """Check if project is eligible for architecture trigger.

        Requires: readiness in (maybe_ready, ready_for_architecture), repo_url exists,
        architecture not already triggered, no architecture result yet.
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

            if discovery_session.readiness_status not in ("maybe_ready", "ready_for_architecture"):
                logger.info(
                    f"Project {project_id} not ready for architecture (readiness: {discovery_session.readiness_status})"
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

        finally:
            session.close()

    @staticmethod
    def trigger(project_id: str) -> Dict[str, Any]:
        """Trigger architecture phase for a project (manual start)."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()

            if not discovery_session:
                return {"success": False, "error": "No discovery session found"}

            if discovery_session.architecture_triggered:
                return {"success": False, "error": "Already triggered", "skipped": True}

            if discovery_session.readiness_status not in ("maybe_ready", "ready_for_architecture"):
                return {"success": False, "error": "Not ready for architecture"}

            repo_url, has_repo_url = get_repo_url_for_panel(project_id)
            if not has_repo_url or not repo_url:
                return {"success": False, "error": "Repo missing"}

            if ArchitectureResultRepository().get_latest(project_id) is not None:
                return {"success": False, "error": "Architecture result already exists", "skipped": True}

            base_url = os.environ.get("BASE_URL", "").strip() or "http://localhost:8000"
            context_url = f"{base_url}/projects/{project_id}/context"
            now = datetime.utcnow()
            webhook_payload = {
                "event_type": "project.architecture.requested",
                "project_id": project_id,
                "occurred_at": now.isoformat(),
                "context_url": context_url,
                "repo_url": repo_url,
            }

            webhook_url = ARCHITECTURE_WEBHOOK_URL
            result = ArchitectureTriggerService._send_webhook(webhook_payload)

            discovery_session.architecture_triggered = result.get("success", False)
            discovery_session.architecture_triggered_at = now if result.get("success") else None
            discovery_session.architecture_trigger_status = "success" if result.get("success") else "failed"
            discovery_session.eligible_for_architecture = True
            if result.get("success"):
                discovery_session.architecture_trigger_target = webhook_url
                discovery_session.architecture_started_by = "manual_button"
                discovery_session.updated_at = now
                logger.info(f"Successfully triggered architecture for project {project_id}")

            session.commit()

            return {
                "success": result.get("success", False),
                "webhook_response": result.get("response"),
                "error": result.get("error"),
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to trigger architecture for project {project_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def _send_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send webhook to n8n."""
        webhook_url = ARCHITECTURE_WEBHOOK_URL

        if not webhook_url:
            logger.warning("Architecture webhook URL not configured")
            return {"success": False, "error": "Webhook URL not configured"}

        try:
            logger.info(f"Sending architecture webhook for project {payload.get('project_id')}")
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Architecture webhook sent successfully for project {payload.get('project_id')}")
                return {
                    "success": True,
                    "response": {"status_code": response.status_code, "body": response.text}
                }
            else:
                logger.error(f"Architecture webhook failed for project {payload.get('project_id')}: HTTP {response.status_code}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "response": {"status_code": response.status_code, "body": response.text[:500]}
                }

        except requests.RequestException as e:
            logger.error(f"Architecture webhook request failed for project {payload.get('project_id')}: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def trigger_if_eligible(project_id: str) -> Dict[str, Any]:
        """Check eligibility and trigger if eligible. Convenience method."""
        if ArchitectureTriggerService.is_eligible(project_id):
            return ArchitectureTriggerService.trigger(project_id)
        return {"success": False, "error": "Not eligible", "skipped": True}


__all__ = ["ArchitectureTriggerService"]
