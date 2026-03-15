from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import json
import logging

from app.serializers.markdown_serializer import render_all as render_markdown_skeleton
from app.adapters import get_storage_adapter
from pathlib import Path
from app.pipelines.graph_pipeline import generate_graph_artifacts
from app.discovery.checklist_service import ChecklistService
from app.discovery.config import NEXT_STEP_DESCRIPTIONS_PT
from app.services.context_aggregator import get_consolidated_context

logger = logging.getLogger(__name__)

router = APIRouter()

storage = get_storage_adapter()

def _build_understanding_summary(project_id: str) -> Dict[str, Any]:
    """Derive a compact understanding summary from current checklist items."""
    try:
        cs = ChecklistService()
        checklist = cs.get_checklist(project_id)
        items = []
        for it in checklist:
            status = it.get("status")
            if status in ("confirmed", "inferred"):
                # Use full value field first, then evidence, then status
                value = it.get("value") or it.get("evidence") or status
                items.append({
                    "key": it.get("key"),
                    "label": it.get("label"),
                    "value": value,
                    "source": status,
                })
        return {"items": items}
    except Exception:
        return {"items": []}

def _compute_next_best_step(project_id: str, context: Dict[str, Any]):
    """Compute the next best step for discovery context."""
    try:
        from app.discovery.lifecycle_repository import DiscoveryQuestionLifecycleRepository
        from app.discovery.question_selector import QuestionSelector
        from app.discovery.question_intents import QUESTION_INTENTS
        from app.discovery.checklist_service import ChecklistService
        from app.discovery.readiness_service import DiscoveryReadinessService

        life_repo = DiscoveryQuestionLifecycleRepository(project_id)
        state = life_repo.get_state()
        asked_keys = [str(row.get("intent_key")) for row in state if row.get("status") == "open" and row.get("intent_key")]
        answered_keys = [str(row.get("intent_key")) for row in state if row.get("status") == "answered" and row.get("intent_key")]

        checklist = ChecklistService().get_checklist(project_id)
        readiness = DiscoveryReadinessService().quick_readiness_check(project_id, checklist, None)
        next_key = QuestionSelector().select(checklist, asked_keys, answered_keys, readiness)
        if not next_key:
            return None

        # Resolve a human-friendly title for the next key
        title = None
        for intent, meta in QUESTION_INTENTS.items():
            if meta.get("checklist_key") == next_key:
                title = meta.get("question")
                break
        if not title:
            from app.discovery.config import NEXT_STEP_FALLBACK
            title = f"{NEXT_STEP_FALLBACK}{next_key}"

        step_type = "repo" if next_key == "repo_exists" else "clarification"
        description = None
        if next_key == "repo_exists":
            from app.discovery.config import NEXT_STEP_DESCRIPTIONS_PT
            description = NEXT_STEP_DESCRIPTIONS_PT.get("repo_exists", "Verificar se existe um repositório para o projeto.")
        else:
            try:
                from app.discovery.question_service import QUESTION_TEMPLATES
                description = QUESTION_TEMPLATES.get(next_key)
            except Exception:
                description = None
            if not description:
                from app.discovery.config import NEXT_STEP_DESCRIPTIONS_PT
                description = NEXT_STEP_DESCRIPTIONS_PT.get(next_key, f"Necessária clarification para {next_key}.")
        return {"title": title, "description": description, "type": step_type}
    except Exception:
        return None


def _build_default_context(project_id: str) -> Dict[str, Any]:
    """Build stable default context for new projects without consolidated context."""
    try:
        from app.discovery.checklist_service import ChecklistService
        from app.discovery.readiness_service import DiscoveryReadinessService
        
        # Try to get real state from DB if available
        cs = ChecklistService()
        checklist = cs.get_checklist(project_id)
        
        rs = DiscoveryReadinessService()
        readiness = rs.quick_readiness_check(project_id, checklist)
        
        # Build summary from checklist
        items = []
        for it in checklist:
            status = it.get("status")
            if status in ("confirmed", "inferred"):
                value = it.get("value") or it.get("evidence") or status
                items.append({
                    "key": it.get("key"),
                    "label": it.get("label"),
                    "value": value,
                    "source": status,
                })
        
        understanding_summary = {"items": items}
        
        # Compute next step if we have answers
        next_best_step = None
        if items:
            try:
                from app.discovery.lifecycle_repository import DiscoveryQuestionLifecycleRepository
                life_repo = DiscoveryQuestionLifecycleRepository(project_id)
                state = life_repo.get_state()
                answered_keys = [row.get("intent_key") for row in state if row.get("status") == "answered"]
                
                # Find first missing high priority item
                for item in checklist:
                    if item.get("status") == "missing" and item.get("priority") == "high":
                        if item.get("key") not in answered_keys:
                            from app.discovery.question_intents import QUESTION_INTENTS
                            from app.discovery.config import NEXT_STEP_DESCRIPTIONS_PT
                            item_key = item.get("key")
                            if item_key:
                                for intent, meta in QUESTION_INTENTS.items():
                                    if meta.get("checklist_key") == item_key:
                                        next_best_step = {
                                            "title": meta.get("question"),
                                            "description": NEXT_STEP_DESCRIPTIONS_PT.get(item_key, ""),
                                            "type": "repo" if item_key == "repo_exists" else "clarification"
                                        }
                                        break
                            break
            except Exception:
                pass
        
        return {
            "project": {"project_id": project_id, "project_name": ""},
            "overview": {},
            "stack": [],
            "components": [],
            "dependencies": [],
            "flows": [],
            "assumptions": [],
            "open_questions": [],
            "uncertainties": [],
            "graphs": {},
            "readiness": readiness,
            "understanding_summary": understanding_summary,
            "next_best_step": next_best_step,
        }
    except Exception as e:
        # Return minimal fallback if even DB queries fail
        logger.warning(f"[Context] Failed to build default context: {e}")
        return {
            "project": {"project_id": project_id, "project_name": ""},
            "overview": {},
            "stack": [],
            "components": [],
            "dependencies": [],
            "flows": [],
            "assumptions": [],
            "open_questions": [],
            "uncertainties": [],
            "graphs": {},
            "readiness": {"status": "not_ready", "coverage": 0.0},
            "understanding_summary": {"items": []},
            "next_best_step": None,
        }


@router.get("/projects/{project_id}/context")
async def get_context(project_id: str) -> Dict[str, Any]:
    try:
        context = get_consolidated_context(project_id)
    except FileNotFoundError:
        # Build stable default context from DB state
        logger.info(f"[Context] No consolidated context for {project_id}, building from DB state")
        context = _build_default_context(project_id)
    except Exception as e:
        logger.warning(f"[Context] Error loading consolidated context: {e}, building defaults")
        context = _build_default_context(project_id)
    
    # Enrich with additional discovery metadata
    try:
        understanding_summary = _build_understanding_summary(project_id)
        context["understanding_summary"] = understanding_summary
    except Exception:
        context["understanding_summary"] = {"items": []}

    try:
        next_best_step = _compute_next_best_step(project_id, context)
        if next_best_step:
            context["next_best_step"] = next_best_step
    except Exception:
        context["next_best_step"] = None

    # Ensure readiness is fresh from DB when discovery session exists
    try:
        from app.discovery.session_service import DiscoverySessionService
        from app.discovery.readiness_service import DiscoveryReadinessService
        session_svc = DiscoverySessionService()
        discovery_session = session_svc.get_session(project_id)
        if discovery_session:
            rs = DiscoveryReadinessService()
            checklist = ChecklistService().get_checklist(project_id)
            context["readiness"] = rs.quick_readiness_check(project_id, checklist, None)
    except Exception as e:
        logger.debug(f"[Context] Could not refresh readiness from discovery: {e}")

    return context


@router.get("/projects/{project_id}/markdown/{filename}")
async def get_markdown_skeleton(project_id: str, filename: str) -> Dict[str, Any]:
    md_path = f"{project_id}/output/markdown/{filename}"
    try:
        content = storage.retrieve(md_path)
        if isinstance(content, (bytes, bytearray)):
            content_dec = content.decode('utf-8')
        else:
            content_dec = str(content)
        return {"filename": filename, "content": content_dec}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Markdown file not found: {str(e)}")


@router.get("/projects/{project_id}/files")
async def list_project_files(project_id: str) -> Dict[str, Any]:
    # List known artifact files for the project (skeleton + artifacts)
    files = [f"{project_id}/output/markdown/{name}" for name in ["01-overview.md", "02-stack.md", "03-components.md", "04-dependencies.md", "05-flows.md", "06-assumptions.md", "07-open-questions.md"]]
    files += [f"{project_id}/output/graphs/{name}" for name in ["system_graph.json", "flow_graph.json", "deployment_hints.json", "system_graph.dsl", "flow_graph.dsl"]]
    return {"files": files}


@router.get("/projects/{project_id}/files/{filename}")
async def get_file(project_id: str, filename: str) -> Dict[str, Any]:
    # Try Markdown path first
    md_path = f"{project_id}/output/markdown/{filename}"
    try:
        content = storage.retrieve(md_path)
        if isinstance(content, (bytes, bytearray)):
            content_dec = content.decode('utf-8')
        else:
            content_dec = str(content)
        return {"filename": filename, "content": content_dec}
    except Exception:
        pass
    # Try graph artifacts
    for ext in ["system_graph.json", "flow_graph.json", "deployment_hints.json", "system_graph.dsl", "flow_graph.dsl"]:
        if filename == Path(ext).name:
            try:
                payload_path = f"{project_id}/output/graphs/{ext}"
                content = storage.retrieve(payload_path)
                if isinstance(content, (bytes, bytearray)):
                    content_dec = content.decode('utf-8')
                else:
                    content_dec = str(content)
                return {"filename": ext, "content": content_dec}
            except Exception:
                break
    raise HTTPException(status_code=404, detail="File not found for project")


@router.get("/projects/{project_id}/graphs/system_graph.json")
async def get_system_graph_json(project_id: str) -> Dict[str, Any]:
    path = f"{project_id}/output/graphs/system_graph.json"
    try:
        content = storage.retrieve(path)
        if isinstance(content, (bytes, bytearray)):
            content_dec = content.decode('utf-8')
        else:
            content_dec = str(content)
        return {"filename": "system_graph.json", "content": json.loads(content_dec)}
    except Exception as e:
        artifacts = generate_graph_artifacts({})
        return {"filename": "system_graph.json", "content": artifacts["system_graph.json"]}


@router.get("/projects/{project_id}/graphs/flow_graph.json")
async def get_flow_graph_json(project_id: str) -> Dict[str, Any]:
    path = f"{project_id}/output/graphs/flow_graph.json"
    try:
        content = storage.retrieve(path)
        if isinstance(content, (bytes, bytearray)):
            content_dec = content.decode('utf-8')
        else:
            content_dec = str(content)
        return {"filename": "flow_graph.json", "content": json.loads(content_dec)}
    except Exception as e:
        artifacts = generate_graph_artifacts({})
        return {"filename": "flow_graph.json", "content": artifacts["flow_graph.json"]}


@router.get("/projects/{project_id}/graphs/deployment_hints.json")
async def get_deployment_hints_json(project_id: str) -> Dict[str, Any]:
    path = f"{project_id}/output/graphs/deployment_hints.json"
    try:
        content = storage.retrieve(path)
        if isinstance(content, (bytes, bytearray)):
            content_dec = content.decode('utf-8')
        else:
            content_dec = str(content)
        return {"filename": "deployment_hints.json", "content": json.loads(content_dec)}
    except Exception as e:
        artifacts = generate_graph_artifacts({})
        return {"filename": "deployment_hints.json", "content": artifacts["deployment_hints.json"]}


@router.get("/projects/{project_id}/graphs/system_graph.dsl")
async def get_system_graph_dsl(project_id: str) -> Dict[str, Any]:
    path = f"{project_id}/output/graphs/system_graph.dsl"
    try:
        content = storage.retrieve(path)
        if isinstance(content, (bytes, bytearray)):
            content_dec = content.decode('utf-8')
        else:
            content_dec = str(content)
        return {"filename": "system_graph.dsl", "content": content_dec}
    except Exception as e:
        artifacts = generate_graph_artifacts({})
        return {"filename": "system_graph.dsl", "content": artifacts["system_graph.dsl"]}


@router.get("/projects/{project_id}/graphs/flow_graph.dsl")
async def get_flow_graph_dsl(project_id: str) -> Dict[str, Any]:
    path = f"{project_id}/output/graphs/flow_graph.dsl"
    try:
        content = storage.retrieve(path)
        if isinstance(content, (bytes, bytearray)):
            content_dec = content.decode('utf-8')
        else:
            content_dec = str(content)
        return {"filename": "flow_graph.dsl", "content": content_dec}
    except Exception as e:
        artifacts = generate_graph_artifacts({})
        return {"filename": "flow_graph.dsl", "content": artifacts["flow_graph.dsl"]}

@router.get("/projects/{project_id}/activity")
async def get_activity(project_id: str) -> Dict[str, Any]:
    """Return a lightweight activity feed for a project.

    Combines lifecycle questions (open/answered) with recent repository ingestion events.
    """
    events: list = []
    # Lifecycle events (open/answered/updated questions)
    try:
        from app.discovery.lifecycle_repository import DiscoveryQuestionLifecycleRepository
        life_repo = DiscoveryQuestionLifecycleRepository(project_id)
        rows = life_repo.get_state()
        for r in rows:
            intent_key = r.get("intent_key")
            status = r.get("status")
            # Resolve a human-friendly label from QUESTION_INTENTS
            label = intent_key
            from app.discovery.question_intents import QUESTION_INTENTS
            from app.discovery.config import ACTIVITY_LABELS_PT
            for key, meta in QUESTION_INTENTS.items():
                if meta.get("checklist_key") == intent_key:
                    label = meta.get("question", intent_key)
                    break
            etype = "unknown"
            if status == "open":
                etype = "question_open"
            elif status == "answered":
                etype = "question_answered"
            # Use pt-BR label for UI
            label_pt = ACTIVITY_LABELS_PT.get(etype, label)
            events.append({"type": etype, "label": label_pt, "timestamp": r.get("updated_at") or r.get("created_at")})
    except Exception:
        pass

    # Optional: repository ingestion events
    try:
        from app.db import JobModel, get_session
        session = get_session()
        jobs = session.query(JobModel).filter(JobModel.project_id == project_id, JobModel.job_type == "repo_ingest").order_by(JobModel.created_at.asc()).all()
        for j in jobs:
            ts = j.started_at or j.created_at
            if ts is None:
                continue
            label = f"Carregando repositório"
            events.append({"type": "repo_ingest", "label": label, "timestamp": ts})
        session.close()
    except Exception:
        pass

    # Sort by timestamp if available
    events.sort(key=lambda e: (e.get("timestamp") or ""))
    return {"events": events}
