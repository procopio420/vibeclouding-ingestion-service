"""Progress summary generator for discovery phase."""
from typing import Dict, List


class ProgressSummaryService:
    def compute_progress(self, checklist: List[Dict], readiness: Dict) -> Dict[str, any]:
        total = len(checklist) if checklist else 0
        completed = sum(1 for c in checklist if c.get("status") in ("confirmed", "completed", "answered"))
        missing = [c for c in checklist if c.get("status") == "missing"]
        percentage = (completed / total * 100.0) if total else 0.0
        return {
            "completed": completed,
            "total": total,
            "percentage": round(percentage, 2),
            "missing": [m.get("key") for m in missing],
            "readiness": readiness or {},
        }

__all__ = ["ProgressSummaryService"]
