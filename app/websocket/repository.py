"""Repository for chat message persistence."""
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.db import get_session, ChatMessageModel

logger = logging.getLogger(__name__)


class ChatMessageRepository:
    """Repository for persisting chat messages."""
    
    def create_message(
        self,
        project_id: str,
        session_id: str,
        role: str,
        content: str,
        client_id: Optional[str] = None,
        run_id: Optional[str] = None,
        message_type: str = "free_text",
    ) -> ChatMessageModel:
        """Create a new chat message."""
        session = get_session()
        try:
            msg = ChatMessageModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                session_id=session_id,
                role=role,
                content=content,
                client_id=client_id,
                run_id=run_id,
                message_type=message_type,
                created_at=datetime.utcnow(),
            )
            session.add(msg)
            session.commit()
            logger.info(f"Created {role} message: {msg.id}")
            return msg
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create message: {e}")
            raise
        finally:
            session.close()
    
    def get_conversation_history(
        self,
        project_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all messages for a project."""
        session = get_session()
        try:
            msgs = session.query(ChatMessageModel).filter(
                ChatMessageModel.project_id == project_id
            ).order_by(ChatMessageModel.created_at.asc()).limit(limit).all()
            
            return [self._to_dict(m) for m in msgs]
        finally:
            session.close()
    
    def get_message(self, message_id: str) -> Optional[ChatMessageModel]:
        """Get a message by ID."""
        session = get_session()
        try:
            return session.query(ChatMessageModel).filter(
                ChatMessageModel.id == message_id
            ).first()
        finally:
            session.close()
    
    def _to_dict(self, model: ChatMessageModel) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": model.id,
            "project_id": model.project_id,
            "session_id": model.session_id,
            "role": model.role,
            "content": model.content,
            "message_type": model.message_type,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }


chat_message_repository = ChatMessageRepository()
