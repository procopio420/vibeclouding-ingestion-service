"""Merge multiple source signals into a canonical ProjectContext."""
from app.repo_analysis.context_normalizer import normalize_signals as normalize


def merge_signals(signals: list) -> dict:
    """Merge multiple source signals into canonical context."""
    if not signals:
        return {"project_name": "Merged Project"}
    return normalize(signals)


def normalize_signals(signals: list) -> dict:
    """Normalize signals to canonical context format."""
    return normalize(signals)
