"""Discovery orchestrator with Gemini integration and hardened readiness."""
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db import get_session, DiscoverySessionModel
from app.discovery.state_machine import DiscoveryStateMachine
from app.discovery.session_service import DiscoverySessionService
from app.discovery.checklist_service import ChecklistService
from app.discovery.question_service import QuestionService, QUESTION_TEMPLATES
from app.discovery.chat_service import ChatService
from app.discovery.readiness_service import DiscoveryReadinessService
from app.discovery.answer_extractor import AnswerExtractor
from app.discovery.question_selector import QuestionSelector
from app.discovery.question_lifecycle_service import QuestionLifecycleService
from app.discovery.progress_summary_service import ProgressSummaryService
from app.discovery.natural_language_mapper import NaturalLanguageMapper
from app.discovery.sufficiency import evaluate as evaluate_sufficiency, is_sufficient

logger = logging.getLogger(__name__)

BOOTSTRAP_QUESTIONS = [
    "O que seu projeto faz? Pode descrever qual problema ele resolve?",
    "Você já tem um repositório no GitHub para ele?",
    "Tem alguma documentação, diagrama ou notas?",
    "O que é mais importante agora: menor custo ou melhor performance?",
]


class DiscoveryOrchestrator:
    """Main orchestrator for the discovery flow."""
    
    def __init__(self):
        self.session_service = DiscoverySessionService()
        self.checklist_service = ChecklistService()
        self.question_service = QuestionService()
        self.chat_service = ChatService()
        self.readiness_service = DiscoveryReadinessService()
        # Hardening: discovery engine helpers
        self.answer_extractor = AnswerExtractor()
        self.question_selector = QuestionSelector()
        # Note: lifecycle is created per-request in handle_user_message to load DB state
        self.progress = ProgressSummaryService()
    
    def start_discovery(self, project_id: str, project_name: str = "") -> Dict[str, Any]:
        """Start a new discovery session."""
        session = self.session_service.create_session(project_id, project_name)
        
        if not session:
            raise Exception("Failed to create discovery session")
        
        checklist = self.checklist_service.get_checklist(project_id)
        
        quick_result = self.readiness_service.quick_readiness_check(project_id, checklist)
        
        response = self._generate_initial_response(project_id, session)
        
        return {
            "session": session,
            "checklist": checklist,
            "readiness": quick_result,
            "response": response,
        }
    
    def get_discovery_state(self, project_id: str) -> Dict[str, Any]:
        """Get current discovery state."""
        session = self.session_service.get_session(project_id)
        if not session:
            return {"error": "No discovery session found"}
        
        checklist = self.checklist_service.get_checklist(project_id)
        questions = self.question_service.get_open_questions(project_id)
        readiness = self.readiness_service.quick_readiness_check(project_id, checklist, questions)
        
        return {
            "session": session,
            "checklist": checklist,
            "open_questions": questions,
            "readiness": readiness,
        }
    
    def handle_user_message(self, project_id: str, message: str) -> Dict[str, Any]:
        """Handle a user message and generate a response."""
        logger.info(f"handle_user_message called - project: {project_id}, message: '{message[:100]}...'")
        
        # Create lifecycle with project_id to load state from DB
        lifecycle = QuestionLifecycleService(project_id)
        
        # Get turn count for repo-first enforcement
        turn_count = self._get_turn_count(project_id) + 1
        self._save_turn_count(project_id, turn_count)
        
        session = self.session_service.get_session(project_id)
        if not session:
            raise Exception("No discovery session found")
        
        session_id = session["id"]
        logger.info(f"Session found: {session_id}, turn: {turn_count}")
        
        # Load current focus (answer sufficiency: stay on topic until resolved)
        current_focus_key = session.get("current_focus_key")
        focus_attempt_count = session.get("focus_attempt_count") or 0
        if not current_focus_key:
            next_key_initial = self._select_next_key_deterministic(
                self.checklist_service.get_checklist(project_id),
                lifecycle,
                self.readiness_service.quick_readiness_check(project_id, self.checklist_service.get_checklist(project_id)),
                turn_count,
            )
            current_focus_key = next_key_initial
            focus_attempt_count = 1
            self.session_service.update_focus(project_id, current_focus_key=current_focus_key, focus_attempt_count=1)
            logger.info(f"[Discovery] {project_id} - no focus yet, set current_focus_key={current_focus_key}")
        
        user_msg = self.chat_service.save_message(
            project_id=project_id,
            session_id=session_id,
            role="user",
            content=message,
            message_type="free_text"
        )
        logger.info(f"User message saved: {user_msg.get('content', 'EMPTY')}")
        
        self.session_service.update_timestamps(project_id, user_message=True)
        
        repo_url = self.chat_service.detect_repo_url(message)
        
        checklist = self.checklist_service.get_checklist(project_id)
        
        logger.info(f"[Discovery] {project_id} - BEFORE extraction: checklist={[c['key']+':'+c['status'] for c in checklist]}")
        
        # Use answer extractor for structured updates
        extraction = self.answer_extractor.extract(message, checklist, None)
        
        logger.info(f"[Discovery] {project_id} - extraction result: {extraction}")
        
        # Evaluate sufficiency for current focus (hybrid: heuristics + AI)
        sufficiency_outcome = evaluate_sufficiency(
            current_focus_key,
            message,
            repo_url=repo_url,
            extraction=extraction,
        )
        logger.info(f"[Discovery] {project_id} - sufficiency for {current_focus_key}: {sufficiency_outcome}")
        
        # Use safe extraction handling to prevent crashes on malformed data
        from app.discovery.answer_extraction_parser import safe_get_updates, safe_get_answered_keys
        
        checklist_updates = {}
        valid_keys = {item.get("key") for item in checklist if item.get("key")}
        
        for upd in safe_get_updates(extraction):
            try:
                if not isinstance(upd, dict):
                    logger.warning(f"[Discovery] {project_id} - Skipping invalid update (not a dict): {type(upd)}")
                    continue
                
                key = upd.get("key")
                if not key:
                    continue
                if key not in valid_keys:
                    logger.warning(f"[Discovery] {project_id} - Skipping update for non-existent checklist item: {key}")
                    continue
                
                # Do not apply or mark answered for current focus when answer was not sufficient
                if key == current_focus_key and not is_sufficient(sufficiency_outcome):
                    logger.info(f"[Discovery] {project_id} - skipping apply for {key} (insufficient: {sufficiency_outcome})")
                    continue
                
                status = upd.get("status") if isinstance(upd.get("status"), str) else "inferred"
                value = upd.get("value") if upd.get("value") is not None else ""
                evidence = upd.get("evidence") if isinstance(upd.get("evidence"), str) else ""
                
                self.checklist_service.update_item(
                    project_id=project_id,
                    key=key,
                    status=status,
                    value=value,
                    evidence=evidence,
                )
                checklist_updates[key] = {"status": status, "value": value, "evidence": evidence}
                lifecycle.mark_asked(project_id, key)
                lifecycle.mark_answered(project_id, key)
            except Exception as e:
                logger.warning(f"[Discovery] {project_id} - Failed to process update: {e}")
                continue
        
        for k in safe_get_answered_keys(extraction):
            if k == current_focus_key and not is_sufficient(sufficiency_outcome):
                continue
            try:
                lifecycle.mark_answered(project_id, k)
            except Exception as e:
                logger.warning(f"[Discovery] {project_id} - Failed to mark answered: {e}")
        
        if repo_url:
            self._trigger_repo_ingestion(project_id, repo_url)
            lifecycle.mark_asked(project_id, "repo_exists")
            if current_focus_key == "repo_exists" and is_sufficient(sufficiency_outcome):
                lifecycle.mark_answered(project_id, "repo_exists")
                self.checklist_service.update_item(
                    project_id=project_id,
                    key="repo_exists",
                    status="confirmed",
                    value=repo_url,
                    evidence="repo URL provided",
                )
        
        checklist = self.checklist_service.get_checklist(project_id)
        
        logger.info(f"[Discovery] {project_id} - AFTER extraction: checklist={[c['key']+':'+c['status'] for c in checklist]}")
        logger.info(f"[Discovery] {project_id} - asked_keys: {list(lifecycle.asked_keys)}, answered_keys: {list(lifecycle.answered_keys)}")
        
        quick_result = None
        full_result = None
        
        is_meaningful = self.chat_service.is_meaningful_message(message, checklist_updates, repo_url)
        logger.info(f"[Discovery] {project_id} - is_meaningful: {is_meaningful}")
        
        if is_meaningful:
            self._update_meaningful_timestamp(project_id)
            quick_result = self.readiness_service.quick_readiness_check(project_id, checklist)
            
            if is_sufficient(sufficiency_outcome):
                next_key = self._select_next_key_deterministic(
                    checklist, lifecycle, quick_result, turn_count
                )
                self.session_service.update_focus(
                    project_id,
                    current_focus_key=next_key,
                    focus_attempt_count=0,
                    resolution_status="sufficient",
                )
                lifecycle.current_focus_key = next_key
                logger.info(f"[Discovery] {project_id} - sufficient, advanced to next_key: {next_key}")
            else:
                next_key = current_focus_key
                self.session_service.update_focus(
                    project_id,
                    focus_attempt_count=focus_attempt_count + 1,
                    resolution_status=sufficiency_outcome,
                )
                lifecycle.current_focus_key = current_focus_key
                logger.info(f"[Discovery] {project_id} - not sufficient ({sufficiency_outcome}), re-ask same key: {next_key}, attempt: {focus_attempt_count + 1}")
            
            logger.info(f"[Discovery] {project_id} - READINESS: status={quick_result.get('status')}, coverage={quick_result.get('coverage')}, missing_critical={quick_result.get('missing_critical_items')}")
            logger.info(f"[Discovery] {project_id} - selected next_key: {next_key}, turn: {turn_count}")
            
            progress = self.progress.compute_progress(checklist, quick_result)
            state_transition = None
            if quick_result["status"] == "maybe_ready":
                full_result = self.readiness_service.full_readiness_check(project_id, checklist)
                state_transition = self._maybe_update_state(project_id, session, checklist, full_result)
            elif quick_result["status"] == "ready_for_architecture":
                full_result = self.readiness_service.full_readiness_check(project_id, checklist)
                state_transition = self._maybe_update_state(project_id, session, checklist, full_result)
            else:
                state_transition = self._maybe_update_state(project_id, session, checklist, quick_result)
        else:
            state_transition = None
            quick_result = self.readiness_service.quick_readiness_check(project_id, checklist)
            if not lifecycle.current_focus_key:
                lifecycle.current_focus_key = current_focus_key
        
        response_text = self._generate_response_with_gemini(
            project_id=project_id,
            user_message=message,
            checklist=checklist,
            readiness=quick_result or {},
            repo_url_detected=bool(repo_url),
            next_key=lifecycle.current_focus_key,
            reask_attempt=focus_attempt_count if not is_sufficient(sufficiency_outcome) else 0,
            resolution_status=sufficiency_outcome if not is_sufficient(sufficiency_outcome) else None,
        )
        
        assistant_msg = self.chat_service.save_message(
            project_id=project_id,
            session_id=session_id,
            role="assistant",
            content=response_text,
            message_type="response"
        )
        
        self.session_service.update_timestamps(project_id, system_message=True)
        
        updated_checklist = self.checklist_service.get_checklist(project_id)
        
        final_readiness = quick_result
        if full_result:
            final_readiness = full_result
        
        # Return lifecycle state for debugging
        lifecycle_snapshot = list(lifecycle.asked_keys)
        
        # Build understanding summary from current checklist
        understanding_summary = self._build_understanding_summary(updated_checklist)
        
        # Compute next best step
        next_step = self._compute_next_step(updated_checklist, lifecycle, final_readiness or {})
        
        logger.info(f"[Discovery] {project_id} - FINAL STATE: next_key={lifecycle.current_focus_key}, turn={turn_count}")
        logger.info(f"[Discovery] {project_id} - UNDERSTANDING_SUMMARY: {understanding_summary}")
        logger.info(f"[Discovery] {project_id} - NEXT_STEP: {next_step}")
        
        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "checklist": updated_checklist,
            "readiness": final_readiness,
            "understanding_summary": understanding_summary,
            "next_best_step": next_step,
            "repo_url_detected": repo_url,
            "meaningful_update": is_meaningful,
            "lifecycle": lifecycle_snapshot,
            "next_key": lifecycle.current_focus_key,
            "turn": turn_count,
            "state_transition": state_transition if is_meaningful else None,
            "questions_created": [],
        }
    
    def _update_meaningful_timestamp(self, project_id: str) -> None:
        """Update the last meaningful update timestamp."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            if discovery_session:
                discovery_session.last_meaningful_update_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to update meaningful timestamp: {e}")
        finally:
            session.close()
    
    def _trigger_repo_ingestion(self, project_id: str, repo_url: str) -> str:
        """Trigger repo ingestion job."""
        job_id = str(uuid.uuid4())
        
        try:
            from app.celery_app import celery_app
            celery_app.send_task(
                "repo_ingest_worker",
                args=[job_id, project_id, repo_url],
                queue="repo_ingest"
            )
            self.session_service.add_ingestion_job(project_id, job_id)
            self.session_service.update_state(project_id, "ingesting_sources")
            logger.info(f"Triggered repo ingestion {job_id} for {repo_url}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger repo ingestion: {e}")
            return ""
    
    def _maybe_update_state(
        self,
        project_id: str,
        session: Dict,
        checklist: List[Dict],
        readiness: Dict
    ) -> Optional[Dict[str, str]]:
        """Update discovery state based on current progress.
        Returns state_transition dict (old_state, new_state) when a transition occurred, else None.
        """
        current_state = session["state"]
        readiness_status = readiness.get("status", "not_ready") if isinstance(readiness, dict) else "not_ready"
        state_transition = None

        if current_state == "ingesting_sources":
            out = self.session_service.update_state(project_id, "clarifying_core_requirements")
            state_transition = out.get("state_transition") if out else None
        elif current_state in ["clarifying_core_requirements", "merging_context"]:
            if readiness_status == "ready_for_architecture":
                out = self.session_service.update_state(project_id, "ready_for_architecture")
                state_transition = out.get("state_transition") if out else None
            elif readiness_status == "maybe_ready":
                out = self.session_service.update_state(project_id, "merging_context")
                state_transition = out.get("state_transition") if out else None
            else:
                out = self.session_service.update_state(project_id, "clarifying_core_requirements")
                state_transition = out.get("state_transition") if out else None

        return state_transition
    
    def _generate_initial_response(self, project_id: str, session: Dict) -> str:
        """Generate initial response with bootstrap questions."""
        return self._generate_response_with_gemini(
            project_id=project_id,
            user_message="",
            checklist=self.checklist_service.get_checklist(project_id),
            readiness={"status": "not_ready", "coverage": 0},
            is_initial=True
        )
    
    def _generate_response_with_gemini(
        self,
        project_id: str,
        user_message: str,
        checklist: List[Dict],
        readiness: Dict,
        repo_url_detected: bool = False,
        is_initial: bool = False,
        next_key: Optional[str] = None,
        reask_attempt: int = 0,
        resolution_status: Optional[str] = None,
    ) -> str:
        """Generate a natural response using Gemini."""
        try:
            from app.repo_analysis.llm_enrichment import get_llm_analyzer
            analyzer = get_llm_analyzer()
            
            if not analyzer.is_available() or analyzer.__class__.__name__ == "NoOpAnalyzer":
                return self._fallback_response(checklist, repo_url_detected, is_initial, next_key=next_key, reask_attempt=reask_attempt)
            
            missing_items = [c for c in checklist if c["status"] == "missing"]
            high_priority = [c for c in missing_items if c["priority"] == "high"]
            
            prompt = self._build_response_prompt(
                user_message=user_message,
                checklist=checklist,
                readiness=readiness,
                repo_url_detected=repo_url_detected,
                is_initial=is_initial,
                missing_items=missing_items,
                high_priority=high_priority,
                next_key=next_key,
                reask_attempt=reask_attempt,
                resolution_status=resolution_status,
            )
            
            response = analyzer.generate_chat_response(prompt)
            
            if not response:
                logger.warning("Gemini returned empty response, using fallback")
                return self._fallback_response(checklist, repo_url_detected, is_initial, next_key=next_key, reask_attempt=reask_attempt)
            
            return response
            
        except Exception as e:
            logger.warning(f"Gemini response generation failed: {e}")
            return self._fallback_response(checklist, repo_url_detected, is_initial, next_key=next_key, reask_attempt=reask_attempt)
    
    def _build_response_prompt(
        self,
        user_message: str,
        checklist: List[Dict],
        readiness: Dict,
        repo_url_detected: bool,
        is_initial: bool,
        missing_items: List[Dict],
        high_priority: List[Dict],
        next_key: Optional[str] = None,
        reask_attempt: int = 0,
        resolution_status: Optional[str] = None,
    ) -> str:
        """Build prompt for Gemini."""
        if is_initial:
            return f"""Você é um assistente técnico de descoberta que ajuda pessoas a definir seus projetos.

IMPORTANTE: Responda SEMPRE em português brasileiro (pt-BR).
NUNCA use termos técnicos internos como "core_components", "entry_channels", etc.

Faça perguntas naturais e não-técnicas para entender o projeto. Comece com:
1. Você tem um repositório no GitHub para o projeto?
2. O que seu projeto faz?
3. Quem são os usuários alvo?

IMPORTANTE: Pergunte sobre o repositório primeiro se ainda não foi fornecido.
Mantenha conversacional e friendly. Faça no máximo 1-2 perguntas."""

        context_parts = []
        
        # Build understanding summary from answered items
        answered = [c for c in checklist if c.get("status") in ("confirmed", "inferred")]
        if answered:
            summary_parts = []
            for item in answered[:5]:  # Limit to 5 items
                value = item.get("value") or item.get("label", "")
                if value and len(str(value)) < 100:
                    summary_parts.append(f"- {item.get('label', item.get('key', ''))}: {value}")
            
            if summary_parts:
                context_parts.append(f"Informações já coletadas:\n" + "\n".join(summary_parts))
        
        if repo_url_detected:
            context_parts.append("O usuário compartilhou uma URL de repositório. Reconheça isso e informe que está analisando o código.")
        
        readiness_status = readiness.get("status", "") if isinstance(readiness, dict) else ""
        
        if readiness_status == "ready_for_architecture":
            return """Você é um assistente técnico de descoberta.

IMPORTANTE: Responda SEMPRE em português brasileiro (pt-BR).

Com base na conversa, o projeto tem informações suficientes para seguir para a fase de arquitetura.

Responda de forma conversacional, confirmando o que entendeu e perguntando se o usuário gostaria de prosseguir para as recomendações de arquitetura.

Exemplo: "Ótimo! Pelo que entendi, [resumo breve do projeto]. Vamos seguir para a arquitetura?" """
        
        if readiness_status == "maybe_ready":
            context_parts.append("O projeto está próximo de ter informações suficientes. Pergunte se há algo mais importante que ainda não covered.")

        # Re-ask: same topic but different phrasing when answer was insufficient
        if next_key and reask_attempt and reask_attempt > 0:
            context_parts.append(
                "O usuário ainda não respondeu de forma clara o suficiente. NÃO mude de assunto. "
                "Faça a MESMA pergunta de outro jeito: mais simples, com exemplos ou reformulada. "
                "Não repita a mesma frase; seja natural e acolhedor."
            )
        # Force asking about the specific next_key using NATURAL language
        if next_key:
            natural_question = NaturalLanguageMapper.get_full_question(next_key)
            context_parts.append(f"Pergunte naturalmente sobre: {natural_question}")
        
        # Add inference instruction
        context_parts.append("IMPORTANTE: INFIRA sempre que possível. Se o usuário mencionar algo que indique uma necessidade (ex: 'vai ter fotos dos produtos' → armazenamento de imagens), já marque isso como identificado e não perguntem novamente.")

        context = "\n\n".join(context_parts) if context_parts else "Continue ajudando o usuário a definir seu projeto de forma conversacional."
        
        return f"""Você é um assistente técnico de descoberta que ajuda pessoas a construir seus projetos.

IMPORTANTE: 
- Responda SEMPRE em português brasileiro (pt-BR)
- NUNCA exponha termos técnicos internos (como "core_components", "entry_channels", "background_processing") para o usuário
- Use perguntas naturais e explicativas
- INFIRA sempre que possível a partir do que o usuário disse

O usuário disse: "{user_message}"

{context}

Resposta:
- Mantenha sua resposta curta (2-3 frases), conversacional e amigável
- Faça uma pergunta de acompanhamento se apropriado
- Nunca use termos técnicos internos nas perguntas"""
    
    def _fallback_response(
        self,
        checklist: List[Dict],
        repo_url_detected: bool,
        is_initial: bool,
        next_key: Optional[str] = None,
        reask_attempt: int = 0,
    ) -> str:
        """Generate a simple fallback response without Gemini."""
        if is_initial:
            return "Olá! Estou aqui para ajudar a definir seu projeto. O que ele faz? Você tem um repositório no GitHub?"
        
        if repo_url_detected:
            return "Obrigado por compartilhar o repositório! Estou analisando agora. Enquanto isso, pode me contar mais sobre o que o projeto faz?"
        
        # Re-ask variants when answer was insufficient (same topic, different phrasing)
        if next_key and reask_attempt and reask_attempt > 0:
            reask_variants = {
                "repo_exists": "Sem problema — você já criou um repositório no GitHub para esse projeto ou ainda vai criar? Se já tiver, pode me mandar a URL?",
                "product_goal": "Tudo bem — no dia a dia, o que esse sistema vai ajudar a pessoa a fazer melhor? Qual problema ele resolve na prática?",
                "target_users": "Quem são as pessoas que vão usar esse sistema no dia a dia? Pode dar um exemplo?",
                "entry_channels": "Como as pessoas vão acessar? Pelo celular, computador, WhatsApp ou outro jeito?",
                "core_components": "Beleza. Pensando no básico: cadastro, pedidos, painel, catálogo, pagamentos… o que disso é realmente essencial no começo?",
            }
            if next_key in reask_variants:
                return reask_variants[next_key]
        
        missing = [c for c in checklist if c.get("status") == "missing"]
        if missing:
            next_q = missing[0]
            key = next_q.get("key", "")
            # Use natural language mapper instead of raw templates
            return NaturalLanguageMapper.get_full_question(key)
        
        return "Entendi! Tenho uma boa visão do seu projeto. Me avise quando quiser prosseguir para a fase de arquitetura."

    def _get_turn_count(self, project_id: str) -> int:
        """Get the current turn count for the project."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            # Count turns based on user message count
            from app.db import ChatMessageModel
            msg_count = session.query(ChatMessageModel).filter(
                ChatMessageModel.project_id == project_id,
                ChatMessageModel.role == "user"
            ).count()
            return msg_count - 1 if msg_count > 0 else 0
        except Exception:
            return 0
        finally:
            session.close()
    
    def _save_turn_count(self, project_id: str, count: int) -> None:
        """Save turn count (currently just logs - turn is derived from message count)."""
        logger.info(f"[Discovery] {project_id} - turn count: {count}")
    
    def _select_next_key_deterministic(
        self, 
        checklist: List[Dict], 
        lifecycle, 
        readiness: Dict, 
        turn_count: int
    ) -> Optional[str]:
        """Deterministic next key selection with repo-first enforcement.
        
        Rules:
        1. If turn <= 3 and repo not answered, force repo_exists
        2. Use strict priority order for remaining keys
        3. Skip keys that were just answered in this turn
        4. Fall back to question_selector for edge cases
        """
        # Rule 1: Repo-first enforcement
        if turn_count <= 3 and "repo_exists" not in lifecycle.answered_keys:
            logger.info(f"[Discovery] Repo-first: forcing repo_exists (turn={turn_count})")
            return "repo_exists"
        
        # Strict priority order
        priority_order = [
            "repo_exists", "product_goal", "target_users", 
            "entry_channels", "application_type", "core_components",
            "database", "auth_model", "external_integrations",
            "file_storage", "cache_or_queue", "background_processing",
            "traffic_expectation", "availability_requirement", 
            "cost_priority", "compliance_or_sensitive_data"
        ]
        
        # Get missing items
        missing_keys = {c['key'] for c in checklist if c.get('status') == 'missing'}
        
        for key in priority_order:
            if key in missing_keys and key not in lifecycle.answered_keys:
                # Don't ask the same high-priority question twice in a row
                # unless it's been answered
                if key in lifecycle.asked_keys and key not in lifecycle.answered_keys:
                    continue
                logger.info(f"[Discovery] Selected next key from priority: {key}")
                return key
        
        # Fallback to question selector
        try:
            next_key = self.question_selector.select(
                checklist, 
                list(lifecycle.asked_keys), 
                list(lifecycle.answered_keys), 
                readiness
            )
            if next_key:
                logger.info(f"[Discovery] Fallback to question_selector: {next_key}")
            return next_key
        except Exception as e:
            logger.warning(f"[Discovery] question_selector failed: {e}")
            return None

    def _build_understanding_summary(self, checklist: List[Dict]) -> Dict[str, Any]:
        """Build understanding summary from current checklist items."""
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

    def _compute_next_step(self, checklist: List[Dict], lifecycle, readiness: Dict) -> Dict[str, Any]:
        """Compute next best step from current state."""
        from app.discovery.question_intents import QUESTION_INTENTS
        from app.discovery.config import NEXT_STEP_DESCRIPTIONS_PT, NEXT_STEP_FALLBACK
        
        next_key = lifecycle.current_focus_key
        if not next_key:
            return {"title": None, "description": None, "type": None}
        
        # Get title from QUESTION_INTENTS
        title = None
        for intent, meta in QUESTION_INTENTS.items():
            if meta.get("checklist_key") == next_key:
                title = meta.get("question")
                break
        if not title:
            title = f"{NEXT_STEP_FALLBACK}{next_key}"
        
        # Get description
        step_type = "repo" if next_key == "repo_exists" else "clarification"
        description = NEXT_STEP_DESCRIPTIONS_PT.get(next_key)
        if not description:
            # Try to get from QUESTION_INTENTS
            for intent, meta in QUESTION_INTENTS.items():
                if meta.get("checklist_key") == next_key:
                    description = meta.get("question")
                    break
        
        return {"title": title, "description": description, "type": step_type}


__all__ = ["DiscoveryOrchestrator"]
