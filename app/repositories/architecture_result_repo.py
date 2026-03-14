"""Repository for architecture result persistence."""
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.db import get_session, ArchitectureResultModel, ProjectModel
from app.adapters import get_storage_adapter

logger = logging.getLogger(__name__)


def _serialize_field(value: Any) -> str:
    """Serialize a field value to JSON string, handling strings properly."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


class ArchitectureResultRepository:
    """Repository for saving and retrieving architecture results."""
    
    STORAGE_KEY_TEMPLATE = "{project_id}/architecture/architecture_result.json"
    
    def save(
        self,
        project_id: str,
        payload: Dict[str, Any],
    ) -> ArchitectureResultModel:
        """Save architecture result to DB and object storage.
        
        Args:
            project_id: The project identifier
            payload: Full architecture result payload
            
        Returns:
            Saved ArchitectureResultModel
            
        Raises:
            Exception: If storage upload fails (DB not modified)
        """
        session = get_session()
        
        try:
            storage_key = self.STORAGE_KEY_TEMPLATE.format(project_id=project_id)
            storage = get_storage_adapter()
            raw_json = json.dumps(payload, indent=2)
            
            storage_uri = storage.store(storage_key, raw_json)
            logger.info(f"Uploaded architecture result to storage: {storage_uri}")
            
            existing = session.query(ArchitectureResultModel).filter(
                ArchitectureResultModel.project_id == project_id,
                ArchitectureResultModel.is_latest == "true"
            ).first()
            if existing:
                existing.is_latest = "false"
                existing.updated_at = datetime.utcnow()
            
            arch_result = ArchitectureResultModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                schema_version="1.0",
                analise_entrada=_serialize_field(payload.get("analise_entrada")),
                vibe_economica=_serialize_field(payload.get("vibe_economica")),
                vibe_performance=_serialize_field(payload.get("vibe_performance")),
                raw_payload=raw_json,
                raw_payload_storage_key=storage_key,
                is_latest="true",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(arch_result)
            
            project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if project:
                project.status = "architecture_ready"
            
            session.commit()
            logger.info(f"Saved architecture result {arch_result.id} for project {project_id}")
            
            return arch_result
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save architecture result: {e}")
            raise
    
    def get_latest(self, project_id: str) -> Optional[ArchitectureResultModel]:
        """Get the latest architecture result for a project.
        
        Args:
            project_id: The project identifier
            
        Returns:
            ArchitectureResultModel or None if not found
        """
        session = get_session()
        try:
            result = session.query(ArchitectureResultModel).filter(
                ArchitectureResultModel.project_id == project_id,
                ArchitectureResultModel.is_latest == "true"
            ).first()
            return result
        finally:
            session.close()
    
    def get_by_id(self, architecture_result_id: str) -> Optional[ArchitectureResultModel]:
        """Get architecture result by ID.
        
        Args:
            architecture_result_id: The architecture result identifier
            
        Returns:
            ArchitectureResultModel or None if not found
        """
        session = get_session()
        try:
            result = session.query(ArchitectureResultModel).filter(
                ArchitectureResultModel.id == architecture_result_id
            ).first()
            return result
        finally:
            session.close()


def parse_architecture_result(model: ArchitectureResultModel) -> Dict[str, Any]:
    """Parse ArchitectureResultModel into API response dict.
    
    Args:
        model: ArchitectureResultModel from DB
        
    Returns:
        Dict suitable for API response
    """
    def parse_json_field(field_value: Optional[str]) -> Any:
        if not field_value:
            return {}
        try:
            parsed = json.loads(field_value)
            return parsed
        except json.JSONDecodeError:
            return field_value
    
    return {
        "architecture_result_id": model.id,
        "project_id": model.project_id,
        "schema_version": model.schema_version,
        "analise_entrada": parse_json_field(model.analise_entrada),
        "vibe_economica": parse_json_field(model.vibe_economica),
        "vibe_performance": parse_json_field(model.vibe_performance),
        "raw_payload_storage_key": model.raw_payload_storage_key,
        "status": "saved",
        "created_at": model.created_at.isoformat() if model.created_at else "",
    }


__all__ = ["ArchitectureResultRepository", "parse_architecture_result"]
