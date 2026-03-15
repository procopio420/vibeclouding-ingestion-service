"""Discovery session service."""
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db import get_session, DiscoverySessionModel, ProjectModel
from app.discovery.state_machine import DiscoveryStateMachine, get_readiness_from_state

logger = logging.getLogger(__name__)


DEFAULT_CHECKLIST_ITEMS = [
    ("repo_exists", "Você já tem um repositório no GitHub?", "high"),
    ("product_goal", "O que seu projeto faz?", "high"),
    ("target_users", "Quem são os usuários alvo?", "high"),
    ("entry_channels", "Como os usuários acessarão o app?", "medium"),
    ("application_type", "Que tipo de aplicação é?", "medium"),
    ("core_components", "Quais são os principais componentes?", "medium"),
    ("database", "Você vai precisar de banco de dados?", "medium"),
    ("cache_or_queue", "Você vai precisar de cache ou filas?", "medium"),
    ("background_processing", "Haverá tarefas em background?", "medium"),
    ("external_integrations", "Vai conectar com APIs externas?", "medium"),
    ("auth_model", "Você vai precisar de autenticação?", "medium"),
    ("file_storage", "Você vai armazenar arquivos ou imagens?", "low"),
    ("traffic_expectation", "Qual é o tráfego esperado?", "low"),
    ("availability_requirement", "Downtime é um problema?", "low"),
    ("cost_priority", "Prioridade em custo ou escala?", "low"),
    ("compliance_or_sensitive_data", "Requisitos de conformidade?", "low"),
    ("project_name", "Nome do projeto", "low"),
]


class DiscoverySessionService:
    """Service for managing discovery sessions."""
    
    def create_session(self, project_id: str, project_name: str = "") -> Dict[str, Any]:
        """Create a new discovery session with initial checklist."""
        session = get_session()
        try:
            existing = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            
            if existing:
                logger.info(f"Discovery session already exists for project {project_id}")
                return self._session_to_dict(existing)
            
            session_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            discovery_session = DiscoverySessionModel(
                id=session_id,
                project_id=project_id,
                state=DiscoveryStateMachine.get_initial_state(),
                readiness_status="not_ready",
                started_at=now,
                updated_at=now,
                last_transition_at=now,
            )
            session.add(discovery_session)
            
            project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if project:
                project.status = "collecting_initial_context"
            
            from app.db import ChecklistItemModel
            for key, label, priority in DEFAULT_CHECKLIST_ITEMS:
                item = ChecklistItemModel(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    key=key,
                    label=label,
                    status="missing",
                    priority=priority,
                    updated_at=now,
                )
                session.add(item)
            
            session.commit()
            logger.info(f"Created discovery session {session_id} for project {project_id}")
            
            return self._session_to_dict(discovery_session)
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create discovery session: {e}")
            raise
        finally:
            session.close()
    
    def get_session(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get discovery session for a project."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            
            if not discovery_session:
                return None
            
            return self._session_to_dict(discovery_session)
        finally:
            session.close()
    
    def update_state(self, project_id: str, new_state: str) -> Optional[Dict[str, Any]]:
        """Update the state of a discovery session."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            
            if not discovery_session:
                logger.warning(f"No discovery session found for project {project_id}")
                return None
            
            old_state = discovery_session.state
            
            if not DiscoveryStateMachine.can_transition(old_state, new_state):
                logger.warning(f"Invalid transition from {old_state} to {new_state}")
                return None
            
            discovery_session.state = new_state
            discovery_session.readiness_status = get_readiness_from_state(new_state)
            discovery_session.last_transition_at = datetime.utcnow()
            discovery_session.updated_at = datetime.utcnow()
            
            project = session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if project:
                project.status = new_state
            
            session.commit()
            logger.info(f"Transitioned discovery session from {old_state} to {new_state}")
            
            return self._session_to_dict(discovery_session)
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update discovery state: {e}")
            raise
        finally:
            session.close()
    
    def add_ingestion_job(self, project_id: str, job_id: str) -> None:
        """Add an active ingestion job ID to the session."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            
            if discovery_session:
                jobs = []
                if discovery_session.active_ingestion_job_ids:
                    jobs = json.loads(discovery_session.active_ingestion_job_ids)
                
                if job_id not in jobs:
                    jobs.append(job_id)
                    discovery_session.active_ingestion_job_ids = json.dumps(jobs)
                    discovery_session.updated_at = datetime.utcnow()
                    session.commit()
                    
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add ingestion job: {e}")
        finally:
            session.close()
    
    def remove_ingestion_job(self, project_id: str, job_id: str) -> None:
        """Remove an ingestion job ID from the session."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            
            if discovery_session and discovery_session.active_ingestion_job_ids:
                jobs = json.loads(discovery_session.active_ingestion_job_ids)
                if job_id in jobs:
                    jobs.remove(job_id)
                    discovery_session.active_ingestion_job_ids = json.dumps(jobs)
                    discovery_session.updated_at = datetime.utcnow()
                    session.commit()
                    
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to remove ingestion job: {e}")
        finally:
            session.close()
    
    def update_timestamps(self, project_id: str, user_message: bool = False, system_message: bool = False) -> None:
        """Update message timestamps."""
        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            
            if discovery_session:
                now = datetime.utcnow()
                if user_message:
                    discovery_session.last_user_message_at = now
                if system_message:
                    discovery_session.last_system_message_at = now
                discovery_session.updated_at = now
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update timestamps: {e}")
        finally:
            session.close()
    
    def _session_to_dict(self, model: DiscoverySessionModel) -> Dict[str, Any]:
        """Convert session model to dict."""
        return {
            "id": model.id,
            "project_id": model.project_id,
            "state": model.state,
            "readiness_status": model.readiness_status,
            "started_at": model.started_at.isoformat() if model.started_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            "last_transition_at": model.last_transition_at.isoformat() if model.last_transition_at else None,
            "last_user_message_at": model.last_user_message_at.isoformat() if model.last_user_message_at else None,
            "last_system_message_at": model.last_system_message_at.isoformat() if model.last_system_message_at else None,
            "active_ingestion_job_ids": json.loads(model.active_ingestion_job_ids) if model.active_ingestion_job_ids else [],
            "notes": model.notes,
        }


__all__ = ["DiscoverySessionService", "DEFAULT_CHECKLIST_ITEMS"]
