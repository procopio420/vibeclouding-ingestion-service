"""Discovery readiness service with two-level evaluation."""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db import get_session, DiscoverySessionModel, JobModel

logger = logging.getLogger(__name__)


class DiscoveryReadinessService:
    """Service for computing discovery readiness with two-level evaluation."""
    
    HIGH_PRIORITY_KEYS = ["product_goal", "target_users", "application_type", "database"]
    MEDIUM_PRIORITY_KEYS = ["core_components", "external_integrations", "auth_model", "entry_channels"]
    
    CRITICAL_KEYS = HIGH_PRIORITY_KEYS + ["database", "application_type"]
    
    def quick_readiness_check(
        self, 
        project_id: str, 
        checklist: Optional[List[Dict[str, Any]]] = None,
        open_questions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Quick readiness check - cheap, deterministic, no LLM.
        
        Evaluates:
        - Checklist coverage
        - Critical missing items
        - Open questions
        
        Returns one of: not_ready, needs_clarification, maybe_ready, ready_for_architecture
        """
        if checklist is None:
            from app.discovery.checklist_service import ChecklistService
            checklist = ChecklistService().get_checklist(project_id)
        
        if open_questions is None:
            from app.discovery.question_service import QuestionService
            open_questions = QuestionService().get_open_questions(project_id)
        
        missing = []
        inferred = []
        confirmed = []
        
        for item in checklist:
            status = item.get("status", "missing")
            key = item.get("key", "")
            priority = item.get("priority", "low")
            
            if status == "missing":
                missing.append({"key": key, "priority": priority})
            elif status == "inferred":
                inferred.append({"key": key, "priority": priority})
            elif status == "confirmed":
                confirmed.append({"key": key})
        
        critical_missing = [m for m in missing if m["key"] in self.CRITICAL_KEYS]
        high_priority_missing = [m for m in missing if m["priority"] == "high"]
        medium_priority_missing = [m for m in missing if m["priority"] == "medium"]
        
        total_items = len(checklist) if checklist else 0
        covered_items = len(confirmed) + len(inferred)
        coverage = covered_items / total_items if total_items > 0 else 0
        
        blocking_questions = [q["question"] for q in open_questions if q.get("priority") == "high"]
        
        notes = []
        if critical_missing:
            notes.append(f"Itens críticos faltando: {', '.join([m['key'] for m in critical_missing])}")
            if blocking_questions:
                notes.append(f"Perguntas abertas: {len(blocking_questions)}")
        
        # Check for missing required repo
        repo_missing = any(m["key"] == "repo_exists" for m in missing)
        missing_required_repo = repo_missing
        
        status = self._determine_quick_status(
            critical_missing=critical_missing,
            high_priority_missing=high_priority_missing,
            medium_priority_missing=medium_priority_missing,
            coverage=coverage,
            blocking_questions=blocking_questions,
            confirmed_count=len(confirmed),
            inferred_count=len(inferred)
        )
        
        result = {
            "status": status,
            "check_type": "quick",
            "coverage": coverage,
            "missing_critical_items": [m["key"] for m in critical_missing],
            "missing_high_priority": [m["key"] for m in high_priority_missing],
            "confirmed_items": [c["key"] for c in confirmed],
            "inferred_items": [i["key"] for i in inferred],
            "blocking_questions": blocking_questions,
            "missing_required_repo": missing_required_repo,
            "notes": notes,
            "evaluated_at": datetime.utcnow().isoformat(),
        }
        
        self._persist_quick_result(project_id, result)
        
        return result
    
    def full_readiness_check(
        self, 
        project_id: str,
        checklist: Optional[List[Dict[str, Any]]] = None,
        open_questions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Full readiness check - comprehensive evaluation.
        
        Evaluates:
        - Checklist state
        - Consolidated project context
        - Ingestion results
        - Open questions
        
        Returns one of: not_ready, needs_clarification, maybe_ready, ready_for_architecture
        """
        if checklist is None:
            from app.discovery.checklist_service import ChecklistService
            checklist = ChecklistService().get_checklist(project_id)
        
        if open_questions is None:
            from app.discovery.question_service import QuestionService
            open_questions = QuestionService().get_open_questions(project_id)
        
        quick_result = self.quick_readiness_check(project_id, checklist, open_questions)
        
        session = get_session()
        try:
            has_consolidated_context = self._has_consolidated_context(project_id)
            ingestion_complete = self._is_ingestion_complete(project_id)
            
            context_summary = ""
            if has_consolidated_context:
                try:
                    from app.services.context_aggregator import get_consolidated_context
                    ctx = get_consolidated_context(project_id)
                    context_summary = ctx.get("project", {}).get("summary", "")
                except Exception:
                    pass
        finally:
            session.close()
        
        has_summary = bool(context_summary)
        has_components = bool(ctx.get("components", [])) if has_consolidated_context else False
        has_stack = bool(ctx.get("stack", {}).get("languages") or ctx.get("stack", {}).get("frameworks")) if has_consolidated_context else False
        
        critical_from_context = []
        if not has_summary:
            critical_from_context.append("project_summary_missing")
        if not has_stack:
            critical_from_context.append("stack_unclear")
        if not has_components:
            critical_from_context.append("components_unclear")
        
        blocking_questions = [q["question"] for q in open_questions if q.get("priority") in ["high", "medium"]]
        
        notes = []
        if critical_from_context:
            notes.append(f"GAPs de contexto: {', '.join(critical_from_context)}")
        if ingestion_complete:
            notes.append("Análise do repositório completa")
        else:
            notes.append("Análise do repositório pendente")
        
        status = self._determine_full_status(
            quick_status=quick_result["status"],
            critical_from_context=critical_from_context,
            ingestion_complete=ingestion_complete,
            has_summary=has_summary,
            has_stack=has_stack,
            has_components=has_components,
            blocking_questions=blocking_questions,
            coverage=quick_result["coverage"]
        )
        
        result = {
            "status": status,
            "check_type": "full",
            "quick_check": quick_result,
            "context_summary_available": has_summary,
            "components_available": has_components,
            "stack_available": has_stack,
            "ingestion_complete": ingestion_complete,
            "critical_context_gaps": critical_from_context,
            "blocking_questions": blocking_questions,
            "notes": notes,
            "evaluated_at": datetime.utcnow().isoformat(),
        }
        
        self._persist_full_result(project_id, result)
        
        return result
    
    def _determine_quick_status(
        self,
        critical_missing: List[Dict],
        high_priority_missing: List[Dict],
        medium_priority_missing: List[Dict],
        coverage: float,
        blocking_questions: List[str],
        confirmed_count: int,
        inferred_count: int
    ) -> str:
        """Determine quick readiness status."""
        if critical_missing:
            return "not_ready"
        
        if blocking_questions:
            return "needs_clarification"
        
        if confirmed_count + inferred_count >= 3 and coverage >= 0.4:
            return "maybe_ready"
        
        if coverage >= 0.6 and not high_priority_missing:
            return "maybe_ready"
        
        if coverage >= 0.7:
            return "ready_for_architecture"
        
        return "needs_clarification"
    
    def _determine_full_status(
        self,
        quick_status: str,
        critical_from_context: List[str],
        ingestion_complete: bool,
        has_summary: bool,
        has_stack: bool,
        has_components: bool,
        blocking_questions: List[str],
        coverage: float
    ) -> str:
        """Determine full readiness status."""
        if critical_from_context:
            return "needs_clarification"
        
        if quick_status == "not_ready":
            return "not_ready"
        
        if blocking_questions and not ingestion_complete:
            return "needs_clarification"
        
        if quick_status == "ready_for_architecture":
            if has_summary and (has_stack or has_components):
                return "ready_for_architecture"
            return "maybe_ready"
        
        if quick_status == "maybe_ready":
            if has_summary and has_stack and ingestion_complete:
                return "ready_for_architecture"
            return "maybe_ready"
        
        return "needs_clarification"
    
    def _has_consolidated_context(self, project_id: str) -> bool:
        """Check if project has consolidated context."""
        try:
            from app.adapters import get_storage_adapter
            storage = get_storage_adapter()
            path = f"{project_id}/output/consolidated_context.json"
            storage.retrieve(path)
            return True
        except Exception:
            return False
    
    def _is_ingestion_complete(self, project_id: str) -> bool:
        """Check if repo ingestion is complete."""
        session = get_session()
        try:
            job = session.query(JobModel).filter(
                JobModel.project_id == project_id,
                JobModel.job_type == "repo_ingest",
                JobModel.status == "completed"
            ).first()
            return job is not None
        finally:
            session.close()
    
    def _persist_quick_result(self, project_id: str, result: Dict[str, Any]) -> None:
        """Persist quick readiness result to session."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            
            if discovery_session:
                discovery_session.quick_readiness_status = result["status"]
                discovery_session.quick_readiness_result = json.dumps(result)
                discovery_session.quick_readiness_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to persist quick readiness: {e}")
        finally:
            session.close()
    
    def _persist_full_result(self, project_id: str, result: Dict[str, Any]) -> None:
        """Persist full readiness result to session."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            
            if discovery_session:
                discovery_session.full_readiness_status = result["status"]
                discovery_session.full_readiness_result = json.dumps(result)
                discovery_session.full_readiness_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to persist full readiness: {e}")
        finally:
            session.close()
    
    def compute_readiness(self, project_id: str, checklist: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Legacy method - redirects to quick check."""
        return self.quick_readiness_check(project_id, checklist)


__all__ = ["DiscoveryReadinessService"]
