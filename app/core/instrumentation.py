import json
import logging
from datetime import datetime


def get_logger(name: str = __name__) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_event(logger: logging.Logger, event: str, payload: dict | None = None) -> None:
    data = {
        "event": event,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if payload:
        if isinstance(payload, dict):
            data.update(payload)
    logger.info(json.dumps(data))
