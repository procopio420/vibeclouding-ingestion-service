"""Client for notifying the terraform generator service when a revision decision is set."""
import logging
import os
import time
import uuid
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


def notify_terraform_process(project_id: str, decision: str, json_url_r2: str) -> bool:
    """POST to the terraform generator service /process endpoint with decision and R2 URL.

    When TERRAFORM_GENERATOR_URL is set, the ingestor calls this after the user sets their
    revision decision. The terraform service should fetch the architecture JSON from
    json_url_r2 and use decision to choose the right vibe for terraform generation.

    Environment variables:
    - TERRAFORM_GENERATOR_URL: Base URL of the terraform generator (e.g. https://terraform-gen.example.com)
    - TERRAFORM_GENERATOR_SECRET: Optional - sent as X-Terraform-Secret header

    Args:
        project_id: The project identifier.
        decision: "vibe_economica" or "vibe_performance".
        json_url_r2: Fetchable HTTP URL for the architecture result JSON (e.g. presigned R2 URL).

    Returns:
        True if the request was sent and returned 2xx, False otherwise.
    """
    base_url = os.environ.get("TERRAFORM_GENERATOR_URL", "").strip()
    if not base_url:
        logger.info(
            "terraform_generator_skip url_not_configured project_id=%s decision=%s",
            project_id,
            decision,
        )
        return False

    process_url = f"{base_url.rstrip('/')}/process"
    secret = os.environ.get("TERRAFORM_GENERATOR_SECRET", "").strip()
    event_id = str(uuid.uuid4())
    sent_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "decision": decision,
        "project_id": project_id,
        "json_url_r2": json_url_r2,
        "event_id": event_id,
        "sent_at": sent_at,
    }

    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Terraform-Secret"] = secret

    logger.info(
        "terraform_generator_request_start url=%s project_id=%s decision=%s event_id=%s",
        process_url,
        project_id,
        decision,
        event_id,
    )
    start = time.monotonic()
    try:
        response = requests.post(
            process_url,
            json=payload,
            headers=headers,
            timeout=10,
        )
        duration_ms = (time.monotonic() - start) * 1000
        response.raise_for_status()
        logger.info(
            "terraform_generator_request_success project_id=%s event_id=%s status=%s duration_ms=%.0f",
            project_id,
            event_id,
            response.status_code,
            duration_ms,
        )
        return True
    except requests.RequestException as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning(
            "terraform_generator_request_failed project_id=%s event_id=%s duration_ms=%.0f error=%s",
            project_id,
            event_id,
            duration_ms,
            e,
        )
        return False


__all__ = ["notify_terraform_process"]
