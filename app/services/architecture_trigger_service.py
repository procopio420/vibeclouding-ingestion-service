"""Architecture trigger service for discovery-to-architecture phase transition."""
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from app.db import get_session, DiscoverySessionModel, ProjectModel

logger = logging.getLogger(__name__)

ARCHITECTURE_WEBHOOK_URL = os.environ.get(
    "ARCHITECTURE_WEBHOOK_URL",
    "http://boccaletti.vps-kinghost.net:5678/webhook-test/vibe-arch-input"
)


class ArchitectureTriggerService:
    """Service for triggering architecture phase when project becomes eligible."""

    @staticmethod
    def is_eligible(project_id: str) -> bool:
        """Check if project is eligible for architecture trigger."""
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

            if discovery_session.readiness_status != "ready_for_architecture":
                logger.info(f"Project {project_id} not ready for architecture (readiness: {discovery_session.readiness_status})")
                return False

            return True

        finally:
            session.close()

    @staticmethod
    def trigger(project_id: str) -> Dict[str, Any]:
        """Trigger architecture phase for a project."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()

            if not discovery_session:
                logger.warning(f"No discovery session found for project {project_id}")
                return {"success": False, "error": "No discovery session found"}

            if discovery_session.architecture_triggered:
                logger.info(f"Architecture already triggered for project {project_id}")
                return {"success": False, "error": "Already triggered", "skipped": True}

            if discovery_session.readiness_status != "ready_for_architecture":
                logger.warning(f"Project {project_id} not ready for architecture")
                return {"success": False, "error": "Not ready for architecture"}

            project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            project_name = project.name if project else "Unknown"

            webhook_payload = {
                "project_id": project_id,
                "project_name": project_name,
                "triggered_at": datetime.utcnow().isoformat(),
                "trigger_id": str(uuid.uuid4()),
                "readiness_status": discovery_session.readiness_status,
            }

            result = ArchitectureTriggerService._send_webhook(webhook_payload)

            now = datetime.utcnow()
            discovery_session.architecture_triggered = result.get("success", False)
            discovery_session.architecture_triggered_at = now if result.get("success") else None
            discovery_session.architecture_trigger_status = "success" if result.get("success") else "failed"
            discovery_session.eligible_for_architecture = True

            if result.get("success"):
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
