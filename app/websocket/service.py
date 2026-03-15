"""WebSocket service for discovery chat orchestration."""
import logging
import uuid
from typing import Dict, Any, Callable, Awaitable, Optional, List

from app.discovery.orchestrator import DiscoveryOrchestrator
from app.discovery.session_service import DiscoverySessionService
from app.discovery.checklist_service import ChecklistService
from app.discovery.question_service import QuestionService
from app.discovery.chat_service import ChatService
from app.discovery.readiness_service import DiscoveryReadinessService
from app.websocket.schemas import ServerEventType
from app.websocket.assistant_runner import assistant_runner

logger = logging.getLogger(__name__)

SendEventFn = Callable[[Dict[str, Any]], Awaitable[None]]


class DiscoveryWebSocketService:
    """Orchestrates discovery flow over WebSocket."""
    
    def __init__(self):
        self.orchestrator = DiscoveryOrchestrator()
        self.session_service = DiscoverySessionService()
        self.checklist_service = ChecklistService()
        self.question_service = QuestionService()
        self.chat_service = ChatService()
        self.readiness_service = DiscoveryReadinessService()
    
    async def get_connection_state(self, project_id: str) -> Dict[str, Any]:
        """Get full state for a new connection."""
        session = self.session_service.get_session(project_id)
        messages = self.chat_service.get_messages(project_id)
        checklist = self.checklist_service.get_checklist(project_id)
        questions = self.question_service.get_open_questions(project_id)
        
        readiness = {}
        if session:
            readiness = self.readiness_service.quick_readiness_check(
                project_id, checklist, questions
            )
        
        return {
            "session": session or {},
            "messages": messages,
            "checklist": checklist,
            "readiness": readiness,
            "questions": questions,
        }
    
    async def start_session(
        self,
        project_id: str,
        send_event: SendEventFn,
    ) -> None:
        """Start a new discovery session."""
        try:
            result = self.orchestrator.start_discovery(project_id)
            
            await send_event({
                "type": ServerEventType.SESSION_STARTED.value,
                "data": {"session": result.get("session", {})}
            })
            
            await self._send_checklist_delta(send_event, result.get("checklist", []))
            await self._send_readiness_delta(send_event, result.get("readiness", {}))
            
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            await send_event({
                "type": ServerEventType.ERROR.value,
                "data": {"code": "SESSION_FAILED", "message": str(e)}
            })
    
    async def handle_message(
        self,
        project_id: str,
        client_id: str,
        content: str,
        send_event: SendEventFn,
    ) -> None:
        """Handle incoming user message."""
        session = self.session_service.get_session(project_id)
        if not session:
            await send_event({
                "type": ServerEventType.ERROR.value,
                "data": {"code": "NO_SESSION", "message": "No active session. Send session.start first."}
            })
            return
        
        session_id = session["id"]
        run_id = str(uuid.uuid4())
        
        user_msg = self.chat_service.save_message(
            project_id=project_id,
            session_id=session_id,
            role="user",
            content=content,
            message_type="free_text"
        )
        
        await send_event({
            "type": ServerEventType.MESSAGE_CREATED.value,
            "data": {
                "id": user_msg["id"],
                "project_id": project_id,
                "role": "user",
                "content": content,
                "created_at": user_msg.get("created_at"),
            }
        })
        
        await send_event({
            "type": ServerEventType.MESSAGE_ACCEPTED.value,
            "data": {"user_message_id": user_msg["id"]}
        })
        
        self.session_service.update_timestamps(project_id, user_message=True)
        
        async for event in assistant_runner.run(
            project_id=project_id,
            user_message=content,
            run_id=run_id,
            orchestrator=self.orchestrator,
        ):
            await send_event(event.to_dict())
    
    async def handle_checklist_update(
        self,
        project_id: str,
        key: str,
        status: str,
        evidence: Optional[str],
        send_event: SendEventFn,
    ) -> None:
        """Handle checklist item update."""
        old_checklist = self.checklist_service.get_checklist(project_id)
        
        self.checklist_service.update_item(
            project_id=project_id,
            key=key,
            status=status,
            evidence=evidence,
        )
        
        new_checklist = self.checklist_service.get_checklist(project_id)
        
        await self._send_checklist_delta(send_event, new_checklist)
        
        checklist_item = next((c for c in new_checklist if c["key"] == key), None)
        if checklist_item:
            await send_event({
                "type": ServerEventType.CHECKLIST_UPDATED.value,
                "data": {
                    "key": key,
                    "status": checklist_item["status"],
                    "evidence": checklist_item.get("evidence"),
                }
            })
    
    async def handle_question_answer(
        self,
        project_id: str,
        question_id: str,
        answer: str,
        send_event: SendEventFn,
    ) -> None:
        """Handle question answer."""
        self.question_service.answer_question(question_id, answer)
        
        await send_event({
            "type": ServerEventType.QUESTION_ANSWERED.value,
            "data": {"id": question_id, "answer": answer}
        })
        
        questions = self.question_service.get_open_questions(project_id)
        checklist = self.checklist_service.get_checklist(project_id)
        readiness = self.readiness_service.quick_readiness_check(project_id, checklist, questions)
        
        await self._send_readiness_delta(send_event, readiness)
    
    async def _send_checklist_delta(
        self,
        send_event: SendEventFn,
        checklist: List[Dict],
    ) -> None:
        """Send checklist progress update."""
        completed = sum(1 for c in checklist if c["status"] != "missing")
        total = len(checklist)
        percentage = (completed / total * 100) if total > 0 else 0
        
        await send_event({
            "type": ServerEventType.CHECKLIST_PROGRESS.value,
            "data": {
                "completed": completed,
                "total": total,
                "percentage": percentage,
            }
        })
    
    async def _send_readiness_delta(
        self,
        send_event: SendEventFn,
        readiness: Dict[str, Any],
    ) -> None:
        """Send readiness update."""
        missing = readiness.get("missing_critical_items", [])
        
        await send_event({
            "type": ServerEventType.READINESS_UPDATED.value,
            "data": {
                "status": readiness.get("status", "not_ready"),
                "coverage": readiness.get("coverage", 0),
                "missing": missing,
            }
        })


discovery_service = DiscoveryWebSocketService()
