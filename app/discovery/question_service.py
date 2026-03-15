"""Clarification question service."""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db import get_session, ClarificationQuestionModel

logger = logging.getLogger(__name__)


QUESTION_TEMPLATES = {
    "product_goal": "O que seu projeto faz? Pode descrever qual problema ele resolve?",
    "target_users": "Quem são os usuários alvo?",
    "entry_channels": "Como você espera que os usuários acessem o app? (web, mobile, API, WhatsApp, etc.)",
    "application_type": "Que tipo de aplicação você está construindo? (web app, mobile, API, chatbot, etc.)",
    "core_components": "Quais são os principais componentes ou funcionalidades do seu aplicativo?",
    "database": "Você vai precisar armazenar dados em um banco de dados? Se sim, que tipo de dados?",
    "cache_or_queue": "Você vai precisar de cache para performance ou filas de mensagens para processamento em background?",
    "background_processing": "O app vai precisar processar coisas em background?",
    "external_integrations": "Vai conectar com APIs externas como WhatsApp, pagamentos, mapas ou email?",
    "auth_model": "Os usuários vão precisar fazer login? Qual método de autenticação?",
    "file_storage": "Você vai precisar armazenar arquivos, imagens ou documentos?",
    "traffic_expectation": "Quantos usuários você espera inicialmente? É um protótipo rápido ou algo que precisa escalar?",
    "availability_requirement": "É aceitável o app ficar fora do ar por alguns minutos, ou precisa de alta disponibilidade?",
    "cost_priority": "O que é mais importante agora - manter custos baixos ou construir para escalar?",
    "compliance_or_sensitive_data": "Seu aplicativo lida com dados sensíveis ou tem requisitos de conformidade?",
}


class QuestionService:
    """Service for managing clarification questions."""
    
    def create_question(
        self,
        project_id: str,
        question: str,
        reason: Optional[str] = None,
        priority: str = "medium",
        related_checklist_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new clarification question."""
        session = get_session()
        try:
            q = ClarificationQuestionModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                question=question,
                reason=reason,
                priority=priority,
                status="open",
                related_checklist_key=related_checklist_key,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(q)
            session.commit()
            
            logger.info(f"Created clarification question for project {project_id}")
            return self._question_to_dict(q)
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create question: {e}")
            raise
        finally:
            session.close()
    
    def get_open_questions(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all open questions for a project."""
        session = get_session()
        try:
            questions = session.query(ClarificationQuestionModel).filter(
                ClarificationQuestionModel.project_id == project_id,
                ClarificationQuestionModel.status == "open"
            ).order_by(
                ClarificationQuestionModel.priority.desc(),
                ClarificationQuestionModel.created_at.asc()
            ).all()
            
            return [self._question_to_dict(q) for q in questions]
        finally:
            session.close()
    
    def get_all_questions(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all questions for a project."""
        session = get_session()
        try:
            questions = session.query(ClarificationQuestionModel).filter(
                ClarificationQuestionModel.project_id == project_id
            ).order_by(
                ClarificationQuestionModel.created_at.desc()
            ).all()
            
            return [self._question_to_dict(q) for q in questions]
        finally:
            session.close()
    
    def answer_question(
        self, 
        question_id: str, 
        answer: str, 
        source: str = "user"
    ) -> Optional[Dict[str, Any]]:
        """Mark a question as answered."""
        session = get_session()
        try:
            question = session.query(ClarificationQuestionModel).filter(
                ClarificationQuestionModel.id == question_id
            ).first()
            
            if not question:
                logger.warning(f"Question {question_id} not found")
                return None
            
            question.status = "answered"
            question.answer_source = answer
            question.updated_at = datetime.utcnow()
            
            session.commit()
            logger.info(f"Answered question {question_id}")
            
            return self._question_to_dict(question)
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to answer question: {e}")
            raise
        finally:
            session.close()
    
    def dismiss_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Dismiss a question."""
        session = get_session()
        try:
            question = session.query(ClarificationQuestionModel).filter(
                ClarificationQuestionModel.id == question_id
            ).first()
            
            if not question:
                return None
            
            question.status = "dismissed"
            question.updated_at = datetime.utcnow()
            
            session.commit()
            return self._question_to_dict(question)
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to dismiss question: {e}")
            raise
        finally:
            session.close()
    
    def generate_question_for_checklist_key(
        self, 
        checklist_key: str, 
        project_id: str
    ) -> Dict[str, Any]:
        """Generate a question for a specific checklist key."""
        question_text = QUESTION_TEMPLATES.get(checklist_key, f"Tell me more about {checklist_key}")
        
        existing = session = get_session()
        try:
            existing = session.query(ClarificationQuestionModel).filter(
                ClarificationQuestionModel.project_id == project_id,
                ClarificationQuestionModel.related_checklist_key == checklist_key,
                ClarificationQuestionModel.status == "open"
            ).first()
            
            if existing:
                return self._question_to_dict(existing)
        finally:
            session.close()
        
        return self.create_question(
            project_id=project_id,
            question=question_text,
            reason=f"Needed for {checklist_key}",
            related_checklist_key=checklist_key
        )
    
    def _question_to_dict(self, model: ClarificationQuestionModel) -> Dict[str, Any]:
        """Convert question model to dict."""
        return {
            "id": model.id,
            "project_id": model.project_id,
            "question": model.question,
            "reason": model.reason,
            "priority": model.priority,
            "status": model.status,
            "related_checklist_key": model.related_checklist_key,
            "answer_source": model.answer_source,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }


__all__ = ["QuestionService", "QUESTION_TEMPLATES"]
