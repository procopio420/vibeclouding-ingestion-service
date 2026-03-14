"""DB-backed lifecycle repository for discovery questions."""
import uuid
from datetime import datetime
from typing import List, Dict, Any

from app.db import get_session
from app.db import DiscoveryQuestionLifecycleModel


class DiscoveryQuestionLifecycleRepository:
    def __init__(self, project_id: str):
        self.project_id = project_id

    def upsert(self, intent_key: str, status: str, answer_message_id: str | None = None) -> Dict[str, Any]:
        session = get_session()
        try:
            row = session.query(DiscoveryQuestionLifecycleModel).filter_by(
                project_id=self.project_id, intent_key=intent_key
            ).first()
            if row:
                row.status = status
                if answer_message_id is not None:
                    row.answer_message_id = answer_message_id
                row.updated_at = datetime.utcnow()
            else:
                row = DiscoveryQuestionLifecycleModel(
                    id=str(uuid.uuid4()),
                    project_id=self.project_id,
                    intent_key=intent_key,
                    status=status,
                    answer_message_id=answer_message_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(row)
            session.commit()
            return {
                "id": row.id,
                "project_id": row.project_id,
                "intent_key": row.intent_key,
                "status": row.status,
                "answer_message_id": row.answer_message_id,
            }
        finally:
            session.close()

    def get_state(self) -> List[Dict[str, Any]]:
        session = get_session()
        try:
            rows = session.query(DiscoveryQuestionLifecycleModel).filter_by(project_id=self.project_id).order_by(DiscoveryQuestionLifecycleModel.created_at.asc()).all()
            return [
                {
                    "id": r.id,
                    "intent_key": r.intent_key,
                    "status": r.status,
                    "answer_message_id": r.answer_message_id,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ]
        finally:
            session.close()

__all__ = ["DiscoveryQuestionLifecycleRepository"]
