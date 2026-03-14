"""Webhook sender service for outbound notifications."""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def send_context_generated_webhook(project_id: str) -> bool:
    """Send webhook notification when project context is generated.
    
    Environment variables:
    - WEBHOOK_URL: Endpoint to POST to (if not set, does nothing)
    - WEBHOOK_SECRET: Optional - sent as X-Webhook-Secret header
    - BASE_URL: Base URL for the API (used to construct context_url)
    
    Args:
        project_id: The project identifier
        
    Returns:
        True if webhook sent successfully, False otherwise
    """
    webhook_url = os.environ.get("WEBHOOK_URL", "").strip()
    
    if not webhook_url:
        logger.debug("WEBHOOK_URL not configured, skipping webhook")
        return False
    
    base_url = os.environ.get("BASE_URL", "").strip()
    if not base_url:
        logger.warning("BASE_URL not configured, context_url may be incomplete")
        base_url = "http://localhost:8000"
    
    webhook_secret = os.environ.get("WEBHOOK_SECRET", "").strip()
    
    event_id = str(uuid.uuid4())
    occurred_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    context_url = f"{base_url}/projects/{project_id}/context"
    
    payload = {
        "event_type": "project.context.generated",
        "event_id": event_id,
        "occurred_at": occurred_at,
        "project_id": project_id,
        "status": "ready",
        "context_url": context_url,
    }
    
    headers = {
        "Content-Type": "application/json",
    }
    
    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        
        logger.info(
            f"Webhook sent successfully for project {project_id}: "
            f"event_id={event_id}, status={response.status_code}"
        )
        return True
        
    except requests.RequestException as e:
        logger.warning(
            f"Failed to send webhook for project {project_id}: {str(e)}"
        )
        return False


__all__ = ["send_context_generated_webhook"]
