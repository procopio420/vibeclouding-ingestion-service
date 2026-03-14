"""Context aggregation service for unified project context."""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.readiness import compute_readiness

logger = logging.getLogger(__name__)

CONSOLIDATED_PATH = "{project_id}/output/consolidated_context.json"


def build_consolidated_context(
    context: Dict[str, Any],
    graph_artifacts: Dict[str, Any],
    artifact_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a consolidated context from normalized context and graph artifacts.
    
    Args:
        context: Normalized context dict from analysis
        graph_artifacts: Dict of graph JSON/DSL files
        artifact_names: List of artifact filenames (optional)
        
    Returns:
        Fully consolidated context JSON
    """
    project_id = context.get("project_id", "")
    project_name = context.get("project_name", "Unknown Project")
    summary = context.get("summary", "")
    
    stack = context.get("stack", {})
    if isinstance(stack, dict):
        stack_data = {
            "languages": stack.get("languages", []),
            "frameworks": stack.get("frameworks", []),
            "libraries": stack.get("databases", []) + stack.get("infrastructure", []),
            "infrastructure_clues": stack.get("infrastructure", []),
            "external_services": stack.get("external_services", []),
        }
    else:
        stack_data = {
            "languages": [],
            "frameworks": [],
            "libraries": [],
            "infrastructure_clues": [],
            "external_services": [],
        }
    
    components = context.get("components", [])
    if components and isinstance(components[0], dict):
        components_list = [
            {
                "name": c.get("name", "unknown"),
                "type": c.get("type", "module"),
                "description": c.get("description", ""),
                "responsibilities": c.get("responsibilities", []),
                "tech": c.get("tech", []),
                "depends_on": c.get("depends_on", []),
            }
            for c in components
        ]
    else:
        components_list = []
    
    dependencies = context.get("dependencies", [])
    if dependencies and isinstance(dependencies[0], dict):
        deps_list = [
            {
                "name": d.get("name", "unknown"),
                "type": d.get("type", "dependency"),
                "role": d.get("role", "dependency"),
                "confidence": d.get("confidence", 0.0),
            }
            for d in dependencies
        ]
    else:
        deps_list = []
    
    flows = context.get("flows", [])
    if flows and isinstance(flows[0], dict):
        flows_list = [
            {
                "name": f.get("name", "flow"),
                "source": f.get("source", ""),
                "target": f.get("target", ""),
                "description": f.get("description", ""),
                "confidence": f.get("confidence", 0.0),
            }
            for f in flows
        ]
    else:
        flows_list = []
    
    source_types = []
    input_sources = context.get("input_sources", [])
    if input_sources:
        if isinstance(input_sources[0], dict):
            source_types = [s.get("type", "unknown") for s in input_sources]
        else:
            source_types = [s.type for s in input_sources]
    if not source_types:
        source_types = ["repo"]
    
    overview = {
        "project_name": project_name,
        "summary": summary,
        "project_type": context.get("project_type", "unknown"),
        "repo_url": context.get("repo_url", ""),
    }
    
    system_graph = graph_artifacts.get("system_graph.json", {})
    flow_graph = graph_artifacts.get("flow_graph.json", {})
    deployment_hints = graph_artifacts.get("deployment_hints.json", {})
    system_graph_dsl = graph_artifacts.get("system_graph.dsl", "")
    flow_graph_dsl = graph_artifacts.get("flow_graph.dsl", "")
    
    if isinstance(system_graph, str):
        try:
            system_graph = json.loads(system_graph)
        except (json.JSONDecodeError, TypeError):
            system_graph = {}
    if isinstance(flow_graph, str):
        try:
            flow_graph = json.loads(flow_graph)
        except (json.JSONDecodeError, TypeError):
            flow_graph = {}
    if isinstance(deployment_hints, str):
        try:
            deployment_hints = json.loads(deployment_hints)
        except (json.JSONDecodeError, TypeError):
            deployment_hints = {}
    
    consolidated = {
        "project": {
            "project_id": project_id,
            "project_name": project_name,
            "summary": summary,
            "analysis_status": "completed",
            "source_types": source_types,
            "created_at": context.get("created_at", datetime.utcnow().isoformat()),
            "updated_at": datetime.utcnow().isoformat(),
        },
        "overview": overview,
        "stack": stack_data,
        "components": components_list,
        "dependencies": deps_list,
        "flows": flows_list,
        "assumptions": context.get("assumptions", []),
        "open_questions": context.get("open_questions", []),
        "uncertainties": context.get("uncertainties", []),
        "graphs": {
            "system_graph": system_graph,
            "flow_graph": flow_graph,
            "deployment_hints": deployment_hints,
            "system_graph_dsl": system_graph_dsl,
            "flow_graph_dsl": flow_graph_dsl,
        },
        "readiness": {},
        "artifacts": {
            "markdown_files": [],
            "graph_files": [],
        },
    }
    
    consolidated["readiness"] = compute_readiness(consolidated)
    
    return consolidated


def persist_consolidated(project_id: str, context: Dict[str, Any]) -> str:
    """Persist consolidated context to R2 storage.
    
    Args:
        project_id: Project identifier
        context: Consolidated context dict
        
    Returns:
        Storage path where context was saved
    """
    from app.adapters import get_storage_adapter
    
    storage = get_storage_adapter()
    path = CONSOLIDATED_PATH.format(project_id=project_id)
    
    uri = storage.store(path, json.dumps(context, indent=2))
    logger.info(f"Persisted consolidated context to {uri}")
    
    return uri


def get_consolidated_context(project_id: str) -> Dict[str, Any]:
    """Load consolidated context from storage or rebuild from artifacts.
    
    Args:
        project_id: Project identifier
        
    Returns:
        Consolidated context dict
        
    Raises:
        FileNotFoundError: If no context found for project
    """
    from app.adapters import get_storage_adapter
    
    storage = get_storage_adapter()
    path = CONSOLIDATED_PATH.format(project_id=project_id)
    
    try:
        content = storage.retrieve(path)
        if isinstance(content, (bytes, bytearray)):
            content = content.decode('utf-8')
        return json.loads(content)
    except Exception as e:
        logger.warning(f"Could not load consolidated context from {path}: {e}")
        
        return _rebuild_from_artifacts(project_id, storage)


def _rebuild_from_artifacts(project_id: str, storage) -> Dict[str, Any]:
    """Rebuild consolidated context from individual artifact files.
    
    This is a fallback if consolidated context is not available.
    
    Args:
        project_id: Project identifier
        storage: Storage adapter instance
        
    Returns:
        Rebuilt consolidated context
    """
    context_json_path = f"{project_id}/output/context.json"
    
    try:
        context_content = storage.retrieve(context_json_path)
        if isinstance(context_content, (bytes, bytearray)):
            context_content = context_content.decode('utf-8')
        context = json.loads(context_content)
    except Exception as e:
        logger.warning(f"Could not load context.json: {e}")
        context = {"project_id": project_id, "project_name": "Unknown"}
    
    graph_files = [
        "system_graph.json",
        "flow_graph.json", 
        "deployment_hints.json",
        "system_graph.dsl",
        "flow_graph.dsl",
    ]
    
    graph_artifacts = {}
    for gf in graph_files:
        gpath = f"{project_id}/output/graphs/{gf}"
        try:
            gcontent = storage.retrieve(gpath)
            if isinstance(gcontent, (bytes, bytearray)):
                gcontent = gcontent.decode('utf-8')
            graph_artifacts[gf] = gcontent
        except Exception:
            graph_artifacts[gf] = "" if gf.endswith(".dsl") else {}
    
    consolidated = build_consolidated_context(context, graph_artifacts)
    consolidated["project"]["analysis_status"] = "rebuilt_from_artifacts"
    
    return consolidated


__all__ = [
    "build_consolidated_context",
    "persist_consolidated",
    "get_consolidated_context",
]
