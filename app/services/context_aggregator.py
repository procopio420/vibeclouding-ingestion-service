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
    """Load consolidated context from storage or rebuild from artifacts/DB.
    
    Tries multiple strategies in order:
    1. Load from storage (consolidated_context.json)
    2. Rebuild from artifacts (context.json + graphs)
    3. Rebuild from DB (checklist items)
    
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
    
    # Get repo_url from database to ensure it's always populated
    repo_url = _get_repo_url_from_db(project_id)
    
    # Strategy 1: Try loading from storage
    try:
        content = storage.retrieve(path)
        if isinstance(content, (bytes, bytearray)):
            content = content.decode('utf-8')
        context = json.loads(content)
        # Always ensure project_id is set from parameter
        context.setdefault("project_id", project_id)
        # Ensure repo_url is set from DB if not in context
        if not context.get("repo_url") and repo_url:
            context["repo_url"] = repo_url
        return context
    except Exception as e:
        logger.warning(f"[Context] Could not load from storage ({path}): {e}")
    
    # Strategy 2: Rebuild from artifacts
    try:
        context = _rebuild_from_artifacts(project_id, storage, repo_url)
        if context.get("components") or context.get("stack", {}).get("languages"):
            logger.info(f"[Context] Rebuilt context from artifacts for {project_id}")
            return context
    except Exception as e:
        logger.warning(f"[Context] Could not rebuild from artifacts: {e}")
    
    # Strategy 3: Rebuild from DB
    try:
        context = rebuild_context_from_db(project_id)
        if context and context.get("project_id"):
            logger.info(f"[Context] Rebuilt context from DB for {project_id}")
            return context
    except Exception as e:
        logger.warning(f"[Context] Could not rebuild from DB: {e}")
    
    # All strategies failed - return minimal context
    logger.warning(f"[Context] All rebuild strategies failed for {project_id}")
    return {
        "project_id": project_id,
        "project_name": "Unknown",
        "repo_url": repo_url,
        "analysis_status": "no_context_available"
    }


def _get_repo_url_from_db(project_id: str) -> str:
    """Get repo_url from database (checklist or jobs)."""
    try:
        from app.db import get_session, ChecklistItemModel, JobModel
        session = get_session()
        
        # Try checklist first
        checklist_item = session.query(ChecklistItemModel).filter(
            ChecklistItemModel.project_id == project_id,
            ChecklistItemModel.key == "repo_exists"
        ).first()
        
        if checklist_item and checklist_item.value:
            session.close()
            return checklist_item.value
        
        # Try completed repo_ingest job
        job = session.query(JobModel).filter(
            JobModel.project_id == project_id,
            JobModel.job_type == "repo_ingest",
            JobModel.status == "completed"
        ).first()
        
        if job and job.payload:
            try:
                import json
                payload = json.loads(job.payload)
                repo_url = payload.get("repo_url", "")
                session.close()
                return repo_url
            except:
                pass
        
        session.close()
        return ""
    except Exception as e:
        logger.warning(f"Could not get repo_url from DB: {e}")
        return ""


def rebuild_context_from_db(project_id: str) -> Dict[str, Any]:
    """Rebuild consolidated context directly from database checklist.
    
    This function is called when:
    - Storage file is missing
    - We want to ensure context is always available
    
    Args:
        project_id: Project identifier
        
    Returns:
        Consolidated context built from DB state
    """
    from app.db import get_session, ChecklistItemModel, ProjectModel
    
    session = get_session()
    try:
        # Get project info
        project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        project_name = project.name if project and project.name else ""
        
        # Get all checklist items
        checklist_items = session.query(ChecklistItemModel).filter(
            ChecklistItemModel.project_id == project_id
        ).all()
        
        # Build context from checklist
        context = {
            "project_id": project_id,
            "project_name": project_name,
            "repo_url": "",
            "overview": {},
            "stack": {"languages": [], "frameworks": [], "databases": []},
            "components": [],
            "dependencies": [],
            "flows": [],
            "assumptions": [],
            "open_questions": [],
            "uncertainties": [],
            "graphs": {},
        }
        
        # Extract values from checklist
        for item in checklist_items:
            key = item.key
            status = item.status
            value = item.value
            
            if status in ("confirmed", "inferred") and value:
                if key == "repo_exists" and value:
                    # Handle repo URL
                    if value.startswith("http") or value.startswith("git"):
                        context["repo_url"] = value
                elif key == "product_goal":
                    context["overview"]["summary"] = value
                elif key == "target_users":
                    context["overview"]["target_users"] = value
                elif key == "application_type":
                    context["overview"]["application_type"] = value
                # Add more key mappings as needed
        
        # Get repo_url from checklist if not set
        if not context.get("repo_url"):
            repo_item = next((i for i in checklist_items if i.key == "repo_exists"), None)
            if repo_item and repo_item.value:
                context["repo_url"] = repo_item.value
        
        context["analysis_status"] = "rebuilt_from_db"
        
        logger.info(f"[ContextRebuild] Built context from DB for project {project_id}")
        return context
        
    except Exception as e:
        logger.error(f"[ContextRebuild] Failed to rebuild from DB: {e}")
        return {
            "project_id": project_id,
            "project_name": "",
            "error": str(e),
            "analysis_status": "rebuild_failed"
        }
    finally:
        session.close()


def _rebuild_from_artifacts(project_id: str, storage, repo_url: str = "") -> Dict[str, Any]:
    """Rebuild consolidated context from individual artifact files.
    
    This is a fallback if consolidated context is not available.
    
    Args:
        project_id: Project identifier
        storage: Storage adapter instance
        repo_url: Repo URL from database (optional)
        
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
    
    # Add repo_url to context if not present and we have one
    if repo_url and not context.get("repo_url"):
        context["repo_url"] = repo_url
    
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
