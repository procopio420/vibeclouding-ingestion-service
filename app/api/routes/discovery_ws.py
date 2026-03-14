"""WebSocket endpoint for real-time discovery chat."""
import json
import logging
import uuid
from typing import Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.websocket.connection_manager import connection_manager
from app.websocket.schemas import ServerEventType, ClientEventType
from app.websocket.service import discovery_service

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_MESSAGE_LENGTH = 4096


@router.websocket("/ws/discovery/{project_id}")
async def websocket_discovery(
    websocket: WebSocket,
    project_id: str,
    display_name: str = Query(None),
):
    """WebSocket endpoint for discovery chat.
    
    Protocol:
    1. Client connects
    2. Server sends connection.ready with full state
    3. Client sends events (message.create, session.start, etc.)
    4. Server sends events (message.created, assistant.response.delta, etc.)
    5. Disconnect cleans up
    """
    client_id = str(uuid.uuid4())
    
    await websocket.accept()
    
    async def send_event(event: Dict[str, Any]) -> None:
        """Send event to client."""
        await websocket.send_json(event)
    
    try:
        await connection_manager.connect(client_id, project_id, websocket, display_name)
    except ValueError as e:
        await websocket.send_json({
            "type": ServerEventType.ERROR.value,
            "data": {"code": "CONNECTION_EXISTS", "message": str(e)}
        })
        await websocket.close(code=409)
        return
    
    try:
        state = await discovery_service.get_connection_state(project_id)
        
        await websocket.send_json({
            "type": ServerEventType.CONNECTION_READY.value,
            "data": {
                "client_id": client_id,
                "conversation_id": project_id,
                "session": state["session"],
                "messages": state["messages"],
                "checklist": state["checklist"],
                "readiness": state["readiness"],
                "questions": state["questions"],
            }
        })
        
        if not state.get("session", {}).get("id"):
            await websocket.send_json({
                "type": ServerEventType.ERROR.value,
                "data": {
                    "code": "NO_SESSION",
                    "message": "No discovery session found. Send session.start to begin."
                }
            })
        
    except Exception as e:
        logger.error(f"Failed to initialize connection: {e}")
        await websocket.send_json({
            "type": ServerEventType.ERROR.value,
            "data": {"code": "INIT_FAILED", "message": str(e)}
        })
    
    try:
        while True:
            try:
                data = await websocket.receive_text()
            except Exception:
                break
            
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": ServerEventType.ERROR.value,
                    "data": {"code": "INVALID_JSON", "message": "Invalid JSON payload"}
                })
                continue
            
            event_type = event.get("type")
            event_data = event.get("data", {})
            
            if event_type == ClientEventType.PING.value:
                await websocket.send_json({
                    "type": ServerEventType.PONG.value,
                    "data": {}
                })
            
            elif event_type == ClientEventType.SESSION_START.value:
                await discovery_service.start_session(project_id, send_event)
            
            elif event_type == ClientEventType.MESSAGE_CREATE.value:
                content = event_data.get("content", "")
                
                if not content:
                    await websocket.send_json({
                        "type": ServerEventType.ERROR.value,
                        "data": {"code": "EMPTY_MESSAGE", "message": "Message cannot be empty"}
                    })
                    continue
                
                if len(content) > MAX_MESSAGE_LENGTH:
                    await websocket.send_json({
                        "type": ServerEventType.ERROR.value,
                        "data": {"code": "MESSAGE_TOO_LONG", "message": f"Message exceeds {MAX_MESSAGE_LENGTH} characters"}
                    })
                    continue
                
                await discovery_service.handle_message(
                    project_id=project_id,
                    client_id=client_id,
                    content=content,
                    send_event=send_event,
                )
            
            elif event_type == ClientEventType.CHECKLIST_UPDATE.value:
                key = event_data.get("key")
                status = event_data.get("status")
                evidence = event_data.get("evidence")
                
                if not key or not status:
                    await websocket.send_json({
                        "type": ServerEventType.ERROR.value,
                        "data": {"code": "INVALID_CHECKLIST_UPDATE", "message": "key and status required"}
                    })
                    continue
                
                await discovery_service.handle_checklist_update(
                    project_id=project_id,
                    key=key,
                    status=status,
                    evidence=evidence,
                    send_event=send_event,
                )
            
            elif event_type == ClientEventType.QUESTION_ANSWER.value:
                question_id = event_data.get("question_id")
                answer = event_data.get("answer")
                
                if not question_id or not answer:
                    await websocket.send_json({
                        "type": ServerEventType.ERROR.value,
                        "data": {"code": "INVALID_QUESTION_ANSWER", "message": "question_id and answer required"}
                    })
                    continue
                
                await discovery_service.handle_question_answer(
                    project_id=project_id,
                    question_id=question_id,
                    answer=answer,
                    send_event=send_event,
                )
            
            elif event_type == ClientEventType.RESPONSE_CANCEL.value:
                run_id = event_data.get("run_id")
                if run_id:
                    connection_manager.cancel_run(run_id)
            
            else:
                await websocket.send_json({
                    "type": ServerEventType.ERROR.value,
                    "data": {"code": "UNKNOWN_EVENT", "message": f"Unknown event type: {event_type}"}
                })
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": ServerEventType.ERROR.value,
                "data": {"code": "WS_ERROR", "message": str(e)}
            })
        except:
            pass
    finally:
        await connection_manager.disconnect(client_id)


__all__ = ["router"]
