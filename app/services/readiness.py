"""Readiness computation for project context."""
from typing import Any, Dict, List


def compute_readiness(context: Dict[str, Any]) -> Dict[str, Any]:
    """Compute readiness status for downstream architecture agent.
    
    Analyzes the consolidated context to determine if enough information
    is available for the architecture agent to work with.
    
    Args:
        context: Consolidated project context
        
    Returns:
        Readiness dict with status, missing info, confidence, notes
    """
    missing: List[str] = []
    confidence: Dict[str, float] = {}
    notes: List[str] = []
    
    project = context.get("project", {})
    stack = context.get("stack", {})
    components = context.get("components", [])
    dependencies = context.get("dependencies", [])
    open_questions = context.get("open_questions", [])
    assumptions = context.get("assumptions", [])
    
    summary = project.get("summary", "")
    if not summary or summary == "No summary available.":
        missing.append("project_summary")
        confidence["summary"] = 0.0
    else:
        confidence["summary"] = 1.0
        notes.append("Project has a summary description")
    
    has_languages = bool(stack.get("languages"))
    has_frameworks = bool(stack.get("frameworks"))
    if not has_languages and not has_frameworks:
        missing.append("stack_technology")
        confidence["stack"] = 0.0
    else:
        confidence["stack"] = 0.8 if has_frameworks else 0.6
        langs = stack.get("languages", [])
        fws = stack.get("frameworks", [])
        notes.append(f"Detected {len(langs)} language(s), {len(fws)} framework(s)")
    
    if not components:
        missing.append("components")
        confidence["components"] = 0.0
    else:
        confidence["components"] = min(1.0, len(components) / 5.0)
        notes.append(f"Identified {len(components)} component(s)")
    
    if not dependencies:
        confidence["dependencies"] = 0.3
        notes.append("No external dependencies detected - may be a simple project")
    else:
        confidence["dependencies"] = min(1.0, len(dependencies) / 10.0)
        notes.append(f"Found {len(dependencies)} dependency definitions")
    
    critical_missing = len(missing)
    total_checks = 4
    overall_confidence = (total_checks - critical_missing) / total_checks
    
    if critical_missing >= 3:
        status = "insufficient_context"
        notes.append("Critical information missing - manual input required")
    elif critical_missing >= 1:
        status = "needs_clarification"
        notes.append("Some information missing - architecture decisions may need refinement")
    elif overall_confidence >= 0.7:
        status = "ready_for_architecture"
        notes.append("Context appears sufficient for architecture work")
    else:
        status = "needs_clarification"
        notes.append("Low confidence - consider enrichment")
    
    confidence["overall"] = overall_confidence
    
    return {
        "status": status,
        "missing_critical_information": missing,
        "confidence_summary": confidence,
        "notes": notes,
    }
