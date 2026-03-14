"""Checklist service for tracking architecture readiness."""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db import get_session, ChecklistItemModel

logger = logging.getLogger(__name__)


class ChecklistService:
    """Service for managing checklist items."""
    
    def get_checklist(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all checklist items for a project."""
        session = get_session()
        try:
            items = session.query(ChecklistItemModel).filter(
                ChecklistItemModel.project_id == project_id
            ).all()
            
            return [self._item_to_dict(item) for item in items]
        finally:
            session.close()
    
    def update_item(
        self, 
        project_id: str, 
        key: str, 
        status: str, 
        evidence: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update a checklist item's status and evidence."""
        session = get_session()
        try:
            item = session.query(ChecklistItemModel).filter(
                ChecklistItemModel.project_id == project_id,
                ChecklistItemModel.key == key
            ).first()
            
            if not item:
                logger.warning(f"Checklist item {key} not found for project {project_id}")
                return None
            
            item.status = status
            if evidence:
                item.evidence = evidence
            item.updated_at = datetime.utcnow()
            
            session.commit()
            logger.info(f"Updated checklist item {key} to status {status}")
            
            return self._item_to_dict(item)
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update checklist item: {e}")
            raise
        finally:
            session.close()
    
    def get_missing_items(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all missing checklist items."""
        session = get_session()
        try:
            items = session.query(ChecklistItemModel).filter(
                ChecklistItemModel.project_id == project_id,
                ChecklistItemModel.status == "missing"
            ).order_by(
                ChecklistItemModel.priority.desc()
            ).all()
            
            return [self._item_to_dict(item) for item in items]
        finally:
            session.close()
    
    def get_confirmed_items(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all confirmed checklist items."""
        session = get_session()
        try:
            items = session.query(ChecklistItemModel).filter(
                ChecklistItemModel.project_id == project_id,
                ChecklistItemModel.status == "confirmed"
            ).all()
            
            return [self._item_to_dict(item) for item in items]
        finally:
            session.close()
    
    def get_inferred_items(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all inferred checklist items."""
        session = get_session()
        try:
            items = session.query(ChecklistItemModel).filter(
                ChecklistItemModel.project_id == project_id,
                ChecklistItemModel.status == "inferred"
            ).all()
            
            return [self._item_to_dict(item) for item in items]
        finally:
            session.close()
    
    def get_items_by_status(self, project_id: str, status: str) -> List[Dict[str, Any]]:
        """Get checklist items by status."""
        session = get_session()
        try:
            items = session.query(ChecklistItemModel).filter(
                ChecklistItemModel.project_id == project_id,
                ChecklistItemModel.status == status
            ).all()
            
            return [self._item_to_dict(item) for item in items]
        finally:
            session.close()
    
    def _item_to_dict(self, model: ChecklistItemModel) -> Dict[str, Any]:
        """Convert checklist item model to dict."""
        return {
            "id": model.id,
            "project_id": model.project_id,
            "key": model.key,
            "label": model.label,
            "status": model.status,
            "priority": model.priority,
            "evidence": model.evidence,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }


__all__ = ["ChecklistService"]
