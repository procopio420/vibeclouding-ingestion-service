"""Canonical context normalization from extracted signals."""
from typing import Any, Dict, List

from app.domain.models import (
    Component,
    Dependency,
    Flow,
    InputSource,
    ProjectContext,
    Stack,
)


def normalize_signals(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize extracted signals into canonical ProjectContext format."""
    if not signals:
        return _empty_context()
    
    primary = signals[0]
    
    stack_data = primary.get("stack", {})
    stack = Stack(
        languages=stack_data.get("languages", []),
        frameworks=stack_data.get("frameworks", []),
        databases=stack_data.get("databases", []),
        infrastructure=stack_data.get("infrastructure", []),
        external_services=stack_data.get("external_services", []),
    )
    
    components = [
        Component(
            name=c.get("name", "unknown"),
            type=c.get("type", "module"),
            description=c.get("description", ""),
            tech=c.get("tech", []),
        )
        for c in primary.get("components", [])
    ]
    
    flows = [
        Flow(
            name=f.get("name", "flow"),
            source=f.get("source", ""),
            target=f.get("target", ""),
            description=f.get("description", ""),
            confidence=f.get("confidence", 0.0),
        )
        for f in primary.get("flows", [])
    ]
    
    dependencies = [
        Dependency(
            name=d.get("name", "unknown"),
            type=d.get("type", "dependency"),
            role=d.get("role", "dependency"),
            confidence=d.get("confidence", 0.0),
        )
        for d in primary.get("dependencies", [])
    ]
    
    project_name = primary.get("project_name", "Unknown Project")
    summary = primary.get("summary", "")
    project_type = primary.get("project_type", "unknown")
    
    if summary:
        if project_type != "unknown":
            summary = f"[{project_type.upper()}] {summary}"
    
    input_sources = [
        InputSource(
            id="repo",
            type="repo",
            source=primary.get("repo_url", "local"),
            metadata={
                "structure": primary.get("structure", {}),
                "project_type": project_type,
            },
        )
    ]
    
    context = ProjectContext(
        version=1,
        project_name=project_name,
        summary=summary,
        input_sources=input_sources,
        stack=stack,
        components=components,
        flows=flows,
        dependencies=dependencies,
        assumptions=primary.get("assumptions", []),
        open_questions=primary.get("open_questions", []),
        uncertainties=primary.get("uncertainties", []),
        artifacts=[],
    )
    
    return context.dict()


def _empty_context() -> Dict[str, Any]:
    """Return an empty context structure."""
    context = ProjectContext(
        version=1,
        project_name="Unknown Project",
        summary="No analysis data available",
        stack=Stack(),
        components=[],
        flows=[],
        dependencies=[],
        assumptions=[],
        open_questions=["Could not analyze repository"],
        uncertainties=["Analysis failed"],
        artifacts=[],
    )
    return context.dict()


def merge_signals(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple signal sources (for future multi-source support)."""
    if len(signals) == 1:
        return normalize_signals(signals)
    
    merged = {
        "project_name": signals[0].get("project_name", "Merged Project"),
        "project_type": "multi-source",
        "summary": "Multiple source analysis",
        "stack": {
            "languages": [],
            "frameworks": [],
            "databases": [],
            "infrastructure": [],
            "external_services": [],
        },
        "components": [],
        "flows": [],
        "dependencies": [],
        "assumptions": [],
        "open_questions": [],
        "uncertainties": [],
    }
    
    for sig in signals:
        stack = sig.get("stack", {})
        for key in merged["stack"]:
            merged["stack"][key] = list(set(merged["stack"][key] + stack.get(key, [])))
        
        merged["components"].extend(sig.get("components", []))
        merged["flows"].extend(sig.get("flows", []))
        merged["dependencies"].extend(sig.get("dependencies", []))
        merged["assumptions"].extend(sig.get("assumptions", []))
        merged["open_questions"].extend(sig.get("open_questions", []))
        merged["uncertainties"].extend(sig.get("uncertainties", []))
    
    return normalize_signals([merged])
