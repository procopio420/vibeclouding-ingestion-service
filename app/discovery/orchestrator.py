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

logger = logging.getLogger(__name__)

BOOTSTRAP_QUESTIONS = [
    "What does your project do? Can you describe what problem it solves?",
    "Do you already have a repository for it?",
    "Do you have any docs, diagrams, or notes?",
    "What matters more right now: lower cost or stronger performance?",
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
        
        checklist_updates = {}
        for upd in extraction.get("updates", []) or []:
            key = upd.get("key")
            if not key:
                continue
            self.checklist_service.update_item(
                project_id=project_id,
                key=key,
                status=upd.get("status", "inferred"),
                evidence=upd.get("evidence"),
            )
            checklist_updates[key] = {"status": upd.get("status", "inferred"), "evidence": upd.get("evidence")}
            # Mark as asked and answered in lifecycle
            lifecycle.mark_asked(project_id, key)
            lifecycle.mark_answered(project_id, key)
        
        # Also mark any explicitly answered keys
        answered_keys = extraction.get("answered_keys", [])
        for k in answered_keys:
            lifecycle.mark_answered(project_id, k)
        
        if repo_url:
            self._trigger_repo_ingestion(project_id, repo_url)
            # Mark repo as answered
            lifecycle.mark_asked(project_id, "repo_exists")
            lifecycle.mark_answered(project_id, "repo_exists")
        
        checklist = self.checklist_service.get_checklist(project_id)
        
        logger.info(f"[Discovery] {project_id} - AFTER extraction: checklist={[c['key']+':'+c['status'] for c in checklist]}")
        logger.info(f"[Discovery] {project_id} - asked_keys: {list(lifecycle.asked_keys)}, answered_keys: {list(lifecycle.answered_keys)}")
        
        quick_result = None
        full_result = None
        
        is_meaningful = self.chat_service.is_meaningful_message(message, checklist_updates, repo_url)
        
        if is_meaningful:
            self._update_meaningful_timestamp(project_id)
            quick_result = self.readiness_service.quick_readiness_check(project_id, checklist)
            
            # Deterministic next key selection with repo-first enforcement
            next_key = self._select_next_key_deterministic(
                checklist, lifecycle, quick_result, turn_count
            )
            lifecycle.current_focus_key = next_key
            
            logger.info(f"[Discovery] {project_id} - selected next_key: {next_key}, turn: {turn_count}")
            
            progress = self.progress.compute_progress(checklist, quick_result)
            
            if quick_result["status"] == "maybe_ready":
                full_result = self.readiness_service.full_readiness_check(project_id, checklist)
                self._maybe_update_state(project_id, session, checklist, full_result)
            elif quick_result["status"] == "ready_for_architecture":
                full_result = self.readiness_service.full_readiness_check(project_id, checklist)
                self._maybe_update_state(project_id, session, checklist, full_result)
            else:
                self._maybe_update_state(project_id, session, checklist, quick_result)
        else:
            quick_result = self.readiness_service.quick_readiness_check(project_id, checklist)
        
        response_text = self._generate_response_with_gemini(
            project_id=project_id,
            user_message=message,
            checklist=checklist,
            readiness=quick_result or {},
            repo_url_detected=bool(repo_url),
            next_key=lifecycle.current_focus_key
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
        
        logger.info(f"[Discovery] {project_id} - FINAL STATE: next_key={lifecycle.current_focus_key}, turn={turn_count}")
        
        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "checklist": updated_checklist,
            "readiness": final_readiness,
            "repo_url_detected": repo_url,
            "meaningful_update": is_meaningful,
            "lifecycle": lifecycle_snapshot,
            "next_key": lifecycle.current_focus_key,
            "turn": turn_count,
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
    ) -> None:
        """Update discovery state based on current progress."""
        current_state = session["state"]
        readiness_status = readiness.get("status", "not_ready") if readiness else "not_ready"
        
        if current_state == "ingesting_sources":
            self.session_service.update_state(project_id, "clarifying_core_requirements")
        
        elif current_state in ["clarifying_core_requirements", "merging_context"]:
            if readiness_status == "ready_for_architecture":
                self.session_service.update_state(project_id, "ready_for_architecture")
            elif readiness_status == "maybe_ready":
                self.session_service.update_state(project_id, "merging_context")
            else:
                self.session_service.update_state(project_id, "clarifying_core_requirements")
    
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
        next_key: Optional[str] = None
    ) -> str:
        """Generate a natural response using Gemini."""
        try:
            from app.repo_analysis.llm_enrichment import get_llm_analyzer
            analyzer = get_llm_analyzer()
            
            if not analyzer.is_available() or analyzer.__class__.__name__ == "NoOpAnalyzer":
                return self._fallback_response(checklist, repo_url_detected, is_initial)
            
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
                next_key=next_key
            )
            
            response = analyzer.generate_chat_response(prompt)
            
            if not response:
                logger.warning("Gemini returned empty response, using fallback")
                return self._fallback_response(checklist, repo_url_detected, is_initial)
            
            return response
            
        except Exception as e:
            logger.warning(f"Gemini response generation failed: {e}")
            return self._fallback_response(checklist, repo_url_detected, is_initial)
    
    def _build_response_prompt(
        self,
        user_message: str,
        checklist: List[Dict],
        readiness: Dict,
        repo_url_detected: bool,
        is_initial: bool,
        missing_items: List[Dict],
        high_priority: List[Dict],
        next_key: Optional[str] = None
    ) -> str:
        """Build prompt for Gemini."""
        if is_initial:
            return f"""You are a helpful technical discovery assistant helping a user define their project.

Ask natural, non-technical questions to understand the project. Start with:
1. Do you have a GitHub repo for this project?
2. What does your project do?
3. Who are your target users?

IMPORTANT: Ask about the GitHub repo FIRST if not already provided.
Keep it conversational and friendly. Ask 1-2 questions max."""

        context_parts = []
        if repo_url_detected:
            context_parts.append("The user shared a repository URL. Acknowledge this and let them know you're analyzing it.")
        
        readiness_status = readiness.get("status", "") if readiness else ""
        
        if readiness_status == "ready_for_architecture":
            return "Great! Based on our conversation, I have enough information to help with architecture. Would you like me to proceed with generating architecture recommendations?"
        
        if readiness_status == "maybe_ready":
            context_parts.append("The project is close to having enough information. Ask if there's anything else important to know.")
        
        # Force asking about the specific next_key if provided (deterministic progression)
        if next_key:
            from app.discovery.question_intents import QUESTION_INTENTS
            next_question = QUESTION_INTENTS.get(next_key, {}).get("question", f"Tell me more about {next_key}")
            context_parts.append(f"Ask specifically about: {next_question}")
        
        if high_priority:
            keys = [c["key"] for c in high_priority[:2]]
            context_parts.append(f"Also address if needed: {', '.join(keys)}")
        
        context = " ".join(context_parts) if context_parts else "Continue helping the user define their project."
        
        return f"""You are a helpful technical discovery assistant.

User said: "{user_message}"

{context}

IMPORTANT: Do NOT ask broad questions that were already answered (like "what does your project do?" if they already explained it).
Keep your response short (2-3 sentences), conversational, and non-technical. Ask one follow-up question if appropriate."""
    
    def _fallback_response(
        self, 
        checklist: List[Dict], 
        repo_url_detected: bool,
        is_initial: bool
    ) -> str:
        """Generate a simple fallback response without Gemini."""
        if is_initial:
            return "Hi! I'm here to help you define your project. What does your project do? Do you have a repository for it?"
        
        if repo_url_detected:
            return "Thanks for sharing the repository! I'm analyzing it now. In the meantime, can you tell me more about what the project does?"
        
        missing = [c for c in checklist if c["status"] == "missing"]
        if missing:
            next_q = missing[0]
            return f"{QUESTION_TEMPLATES.get(next_q['key'], 'Can you tell me more about your project?')}"
        
        return "Thanks! I have a good understanding of your project. Let me know if you'd like to proceed to the architecture phase."

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


__all__ = ["DiscoveryOrchestrator"]
