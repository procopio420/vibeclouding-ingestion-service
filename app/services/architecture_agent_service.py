"""In-house architecture agent: generates architecture result from project context."""
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from app.db import get_session, DiscoverySessionModel
from app.repositories.architecture_result_repo import ArchitectureResultRepository
from app.services.context_aggregator import get_consolidated_context

logger = logging.getLogger(__name__)


def _normalize_vibe(raw: Any) -> Dict[str, Any]:
    """Ensure vibe has descricao, custo_estimado, recursos (list of {servico, config})."""
    if not raw or not isinstance(raw, dict):
        return {
            "descricao": "",
            "custo_estimado": "",
            "recursos": [],
        }
    descricao = raw.get("descricao")
    if descricao is None:
        descricao = raw.get("description", "")
    custo_estimado = raw.get("custo_estimado") or raw.get("estimated_cost", "")
    recursos = raw.get("recursos") or raw.get("resources", [])
    if not isinstance(recursos, list):
        recursos = []
    normalized_recursos = []
    for r in recursos:
        if isinstance(r, dict):
            normalized_recursos.append({
                "servico": r.get("servico") or r.get("service", ""),
                "config": r.get("config") or r.get("configuration", {}),
            })
    return {
        "descricao": str(descricao) if descricao else "",
        "custo_estimado": str(custo_estimado) if custo_estimado else "",
        "recursos": normalized_recursos,
    }


def _normalize_analise_entrada(raw: Any) -> Any:
    """Keep analise_entrada as string or object; ensure it's serializable."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return raw
    return str(raw)


def _normalize_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize agent output to the expected contract."""
    return {
        "analise_entrada": _normalize_analise_entrada(raw.get("analise_entrada")),
        "vibe_economica": _normalize_vibe(raw.get("vibe_economica")),
        "vibe_performance": _normalize_vibe(raw.get("vibe_performance")),
    }


def _heuristic_generate(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate architecture result from context using heuristics (no LLM)."""
    project_id = context.get("project_id", "")
    project_name = context.get("project_name", "Unknown")
    repo_url = context.get("repo_url", "")
    overview = context.get("overview", {}) or {}
    stack = context.get("stack", {}) if isinstance(context.get("stack"), dict) else {}
    components = context.get("components", []) or []
    languages = stack.get("languages", []) if isinstance(stack, dict) else []
    frameworks = stack.get("frameworks", []) if isinstance(stack, dict) else []

    # analise_entrada: short summary
    parts = [f"Projeto: {project_name}"]
    if repo_url:
        parts.append(f"Repositório: {repo_url}")
    if overview:
        summary = overview.get("summary") or overview.get("description") or ""
        if isinstance(summary, str) and summary:
            parts.append(summary[:500])
    if languages:
        parts.append(f"Stack: {', '.join(languages[:5])}")
    if frameworks:
        parts.append(f"Frameworks: {', '.join(frameworks[:5])}")
    if components:
        part = f"Componentes: {len(components)} detectados"
        if isinstance(components[0], dict):
            names = [c.get("name") or c.get("type", "") for c in components[:5] if c]
            if any(names):
                part += f" ({', '.join(str(n) for n in names if n)})"
        parts.append(part)
    analise_entrada = " | ".join(parts) if parts else "Contexto carregado; sem detalhes adicionais."

    # vibe_economica: cost-conscious option
    vibe_economica = {
        "descricao": "Opção econômica com foco em custo inicial reduzido e pay-as-you-grow.",
        "custo_estimado": "Variável; estimativa inicial baixa com escalonamento conforme uso.",
        "recursos": [
            {"servico": "Compute serverless ou container (ex: Lambda/Cloud Run)", "config": {"scale_to_zero": True}},
            {"servico": "Banco gerenciado pequeno (ex: RDS/SQL menor instância)", "config": {"instance": "small"}},
        ],
    }

    # vibe_performance: performance-oriented option
    vibe_performance = {
        "descricao": "Opção orientada a performance e escalabilidade.",
        "custo_estimado": "Maior que a econômica; adequada para carga e latência previsíveis.",
        "recursos": [
            {"servico": "Load balancer + instâncias dedicadas ou Kubernetes", "config": {"ha": True}},
            {"servico": "Banco com réplicas e cache (ex: RDS + ElastiCache)", "config": {"replicas": True}},
            {"servico": "CDN e cache de conteúdo", "config": {"edge_caching": True}},
        ],
    }

    return {
        "analise_entrada": analise_entrada,
        "vibe_economica": vibe_economica,
        "vibe_performance": vibe_performance,
    }


def _try_llm_generate(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Optionally generate via LLM; return None if unavailable or parse failure."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from app.repo_analysis.llm_enrichment import generate_chat
    except ImportError:
        return None

    prompt = """Com base no contexto do projeto abaixo, gere um JSON com exatamente as chaves: analise_entrada, vibe_economica, vibe_performance.

Regras:
- analise_entrada: string em português resumindo o que foi detectado (tipo de projeto, stack, componentes).
- vibe_economica: objeto com descricao (string), custo_estimado (string), recursos (array de objetos com servico e config).
- vibe_performance: mesmo formato que vibe_economica, focado em performance/escalabilidade.

Retorne APENAS o JSON, sem markdown ou texto extra.

Contexto do projeto:
"""
    context_str = json.dumps(context, ensure_ascii=False, indent=0)[:12000]
    prompt += context_str

    try:
        text = generate_chat(api_key, prompt)
        if not text or not text.strip():
            return None
        # Strip possible markdown code fence
        text = text.strip()
        for pattern in (r"^```(?:json)?\s*", r"\s*```\s*$"):
            text = re.sub(pattern, "", text).strip()
        parsed = json.loads(text)
        if isinstance(parsed, dict) and ("vibe_economica" in parsed or "vibe_performance" in parsed):
            return parsed
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"LLM architecture generation failed or invalid JSON: {e}")
    return None


def _generate_payload(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate architecture payload: try LLM then fall back to heuristic; normalize."""
    raw = _try_llm_generate(context)
    if not raw:
        raw = _heuristic_generate(context)
    return _normalize_payload(raw)


def _update_session_success(project_id: str) -> None:
    """Mark discovery session as architecture triggered (success)."""
    session = get_session()
    try:
        discovery_session = session.query(DiscoverySessionModel).filter(
            DiscoverySessionModel.project_id == project_id
        ).first()
        if discovery_session:
            now = datetime.utcnow()
            discovery_session.architecture_triggered = True
            discovery_session.architecture_triggered_at = now
            discovery_session.architecture_trigger_status = "success"
            discovery_session.architecture_trigger_target = "internal"
            discovery_session.architecture_started_by = "manual_button"
            discovery_session.eligible_for_architecture = True
            discovery_session.updated_at = now
            session.commit()
            logger.info(f"Updated discovery session for project {project_id}: architecture success")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update discovery session: {e}")
        raise
    finally:
        session.close()


def _update_session_failure(project_id: str) -> None:
    """Mark discovery session architecture trigger as failed."""
    session = get_session()
    try:
        discovery_session = session.query(DiscoverySessionModel).filter(
            DiscoverySessionModel.project_id == project_id
        ).first()
        if discovery_session:
            discovery_session.architecture_trigger_status = "failed"
            discovery_session.eligible_for_architecture = True
            discovery_session.updated_at = datetime.utcnow()
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update discovery session failure state: {e}")
    finally:
        session.close()


class ArchitectureAgentService:
    """In-house service that generates architecture result from project context and persists it."""

    @staticmethod
    def generate(project_id: str) -> Dict[str, Any]:
        """
        Load context, generate architecture JSON, persist, update session.
        Returns {"success": True, "payload": ...} or {"success": False, "error": str}.
        Does not call any external webhook.
        """
        # Eligibility (lazy import to avoid circular import with session_service)
        from app.services.architecture_trigger_service import ArchitectureTriggerService
        if not ArchitectureTriggerService.is_eligible(project_id):
            return {"success": False, "error": "Not eligible for architecture"}

        # Load context (same source as /context)
        try:
            context = get_consolidated_context(project_id)
        except Exception as e:
            logger.error(f"Failed to load context for {project_id}: {e}")
            _update_session_failure(project_id)
            return {"success": False, "error": f"Failed to load context: {e}"}

        if not context or not context.get("project_id"):
            _update_session_failure(project_id)
            return {"success": False, "error": "No usable context"}

        # Generate payload (heuristic + optional LLM, then normalize)
        try:
            payload = _generate_payload(context)
        except Exception as e:
            logger.exception(f"Architecture generation failed for {project_id}")
            _update_session_failure(project_id)
            return {"success": False, "error": f"Generation failed: {e}"}

        # Persist
        try:
            ArchitectureResultRepository().save(project_id, payload)
        except Exception as e:
            logger.exception(f"Failed to persist architecture result for {project_id}")
            _update_session_failure(project_id)
            return {"success": False, "error": f"Failed to save result: {e}"}

        _update_session_success(project_id)
        return {"success": True, "payload": payload}


__all__ = ["ArchitectureAgentService", "_normalize_payload", "_heuristic_generate"]
