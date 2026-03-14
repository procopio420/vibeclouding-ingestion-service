"""Assistant runner with streaming response and typing simulation."""
import asyncio
import logging
import random
from typing import AsyncGenerator, Dict, Any, Optional

from app.websocket.schemas import ServerEventType

logger = logging.getLogger(__name__)

MIN_DELAY = 0.02
MAX_DELAY = 0.08


class StreamEvent:
    """Represents a streaming event from the assistant."""
    
    def __init__(self, type: ServerEventType, data: Dict[str, Any]):
        self.type = type
        self.data = data
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data
        }


class AssistantRunner:
    """Generates streaming AI responses with typing simulation."""
    
    def __init__(self):
        self._cancelled_runs: set = set()
    
    def cancel_run(self, run_id: str) -> None:
        """Mark a run as cancelled."""
        self._cancelled_runs.add(run_id)
    
    def _is_cancelled(self, run_id: str) -> bool:
        """Check if a run was cancelled."""
        if run_id in self._cancelled_runs:
            self._cancelled_runs.discard(run_id)
            return True
        return False
    
    async def run(
        self,
        project_id: str,
        user_message: str,
        run_id: str,
        orchestrator,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Run the assistant and yield streaming events.
        
        Args:
            project_id: The project context
            user_message: The user's message
            run_id: Unique ID for this run
            orchestrator: DiscoveryOrchestrator instance
            
        Yields:
            StreamEvent objects representing the response
        """
        if self._is_cancelled(run_id):
            yield StreamEvent(
                ServerEventType.RUN_STATUS,
                {"run_id": run_id, "status": "cancelled", "message": "Run was cancelled"}
            )
            return
        
        try:
            yield StreamEvent(
                ServerEventType.RUN_STATUS,
                {"run_id": run_id, "status": "running"}
            )
            
            result = orchestrator.handle_user_message(project_id, user_message)
            
            assistant_content = result.get("assistant_message", {}).get("content", "")
            assistant_message_id = result.get("assistant_message", {}).get("id")
            user_message_id = result.get("user_message", {}).get("id")
            
            yield StreamEvent(
                ServerEventType.MESSAGE_ACCEPTED,
                {"user_message_id": user_message_id}
            )
            
            yield StreamEvent(
                ServerEventType.ASSISTANT_RESPONSE_STARTED,
                {"run_id": run_id}
            )
            
            accumulated = ""
            for char in assistant_content:
                if self._is_cancelled(run_id):
                    yield StreamEvent(
                        ServerEventType.RUN_STATUS,
                        {"run_id": run_id, "status": "cancelled", "message": "Run was cancelled"}
                    )
                    return
                
                accumulated += char
                
                yield StreamEvent(
                    ServerEventType.ASSISTANT_RESPONSE_DELTA,
                    {"run_id": run_id, "delta": char}
                )
                
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                await asyncio.sleep(delay)
            
            yield StreamEvent(
                ServerEventType.ASSISTANT_RESPONSE_COMPLETED,
                {
                    "run_id": run_id,
                    "message_id": assistant_message_id,
                    "content": accumulated
                }
            )
            
            yield StreamEvent(
                ServerEventType.ASSISTANT_MESSAGE_CREATED,
                {
                    "id": assistant_message_id,
                    "role": "assistant",
                    "content": accumulated
                }
            )
            
            yield StreamEvent(
                ServerEventType.RUN_STATUS,
                {"run_id": run_id, "status": "completed"}
            )
            
        except Exception as e:
            logger.error(f"Assistant run failed: {e}")
            yield StreamEvent(
                ServerEventType.RUN_STATUS,
                {"run_id": run_id, "status": "failed", "message": str(e)}
            )
            yield StreamEvent(
                ServerEventType.ERROR,
                {"code": "RUN_FAILED", "message": str(e)}
            )


assistant_runner = AssistantRunner()
