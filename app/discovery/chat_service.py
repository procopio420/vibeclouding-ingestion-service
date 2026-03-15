"""Chat service for persisting and retrieving messages."""
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db import get_session, ChatMessageModel

logger = logging.getLogger(__name__)


GITHUB_URL_PATTERNS = [
    r'https?://github\.com/[\w-]+/[\w.-]+(?:\.git)?',
    r'git@github\.com:[\w-]+/[\w.-]+\.git',
]


class ChatService:
    """Service for managing chat messages."""
    
    TRIVIAL_RESPONSES = {
        "ok", "thanks", "got it", "yep", "sure", "👍", "thank you", 
        "np", "no problem", "kk", "okay", "cool", "nice", "great",
        "sounds good", "perfect", "alright", "yes", "no", "maybe"
    }
    
    MEANINGFUL_KEYWORDS = {
        "login", "password", "auth", "database", "postgres", "mysql",
        "api", "whatsapp", "stripe", "payment", "integration", "email",
        "background", "worker", "queue", "redis", "cache", "file", 
        "upload", "storage", "s3", "mobile", "web", "frontend", "backend",
        "server", "cloud", "aws", "gcp", "azure", "docker", "kubernetes",
        "microservice", "monolith", "rest", "graphql", "http", "https",
        "user", "users", "customer", "admin", "authentication", "authorization",
        "session", "token", "jwt", "oauth", "saml", "ldap",
        "realtime", "websocket", "socket", "pubsub", "message",
        "cron", "schedule", "task", "job", "batch",
        "email", "sms", "notification", "push", "twilio",
        "ai", "ml", "machine learning", "openai", "gemini", "llm",
        "cost", "budget", "price", "expensive", "cheap", "free",
        "scale", "performance", "latency", "throughput", "traffic",
        "high availability", "ha", "failover", "backup", "disaster",
        "security", "encryption", "tls", "ssl", "certificate",
        "compliance", "gdpr", "hipaa", "pci", "soc2",
    }
    
    def save_message(
        self,
        project_id: str,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "free_text"
    ) -> Dict[str, Any]:
        """Save a chat message."""
        logger.info(f"Saving {role} message - content length: {len(content)}, content: '{content[:100]}...'")
        session = get_session()
        try:
            message = ChatMessageModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                session_id=session_id,
                role=role,
                content=content,
                message_type=message_type,
                created_at=datetime.utcnow(),
            )
            session.add(message)
            session.commit()
            
            logger.info(f"Saved {role} message for project {project_id}, id: {message.id}")
            return self._message_to_dict(message)
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save message: {e}")
            raise
        finally:
            session.close()
    
    def get_messages(
        self, 
        project_id: str, 
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get chat messages for a project."""
        session = get_session()
        try:
            query = session.query(ChatMessageModel).filter(
                ChatMessageModel.project_id == project_id
            ).order_by(ChatMessageModel.created_at.asc())
            
            if limit:
                query = query.limit(limit)
            
            messages = query.all()
            logger.info(f"Query returned {len(messages)} messages from DB for project {project_id}")
            for m in messages:
                logger.info(f"DB Message: id={m.id}, role={m.role}, content='{m.content[:50] if m.content else 'EMPTY'}...'")
            return [self._message_to_dict(m) for m in messages]
        finally:
            session.close()
    
    def get_session_messages(
        self, 
        session_id: str, 
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get messages for a specific session."""
        session = get_session()
        try:
            query = session.query(ChatMessageModel).filter(
                ChatMessageModel.session_id == session_id
            ).order_by(ChatMessageModel.created_at.asc())
            
            if limit:
                query = query.limit(limit)
            
            messages = query.all()
            return [self._message_to_dict(m) for m in messages]
        finally:
            session.close()
    
    def detect_repo_url(self, message: str) -> Optional[str]:
        """Detect a GitHub repository URL in the message."""
        for pattern in GITHUB_URL_PATTERNS:
            match = re.search(pattern, message)
            if match:
                url = match.group(0)
                if url.endswith('.git'):
                    url = url[:-4]
                normalized = self.normalize_github_repo_url(url)
                return normalized
        return None

    @staticmethod
    def normalize_github_repo_url(raw: str) -> Optional[str]:
        """Normalize and minimally validate to a GitHub https URL. Returns None if invalid."""
        if not raw or not raw.strip():
            return None
        raw = raw.strip()
        # Already https?://github.com/...
        if raw.startswith("https://github.com/") or raw.startswith("http://github.com/"):
            rest = raw.split("github.com/", 1)[-1].strip().rstrip("/")
            if rest and "/" in rest:
                return f"https://github.com/{rest}"
            return f"https://github.com/{rest}" if rest else None
        # git@github.com:owner/repo
        if raw.startswith("git@github.com:"):
            path = raw.replace("git@github.com:", "", 1).strip().rstrip("/")
            if path and "/" in path:
                return f"https://github.com/{path}"
        return None
    
    def extract_checklist_updates(self, message: str, checklist_items: List[Dict]) -> Dict[str, Any]:
        """Extract potential checklist updates from user message."""
        updates = {}
        message_lower = message.lower()
        
        keyword_mappings = {
            "database": ["database", "postgresql", "mysql", "postgres", "sql", "db"],
            "auth_model": ["login", "auth", "authentication", "user", "password", "oauth"],
            "external_integrations": ["api", "whatsapp", "stripe", "payment", "integration", "sendgrid", "email"],
            "background_processing": ["background", "worker", "queue", "cron", "task"],
            "file_storage": ["file", "image", "upload", "storage", "s3", "storage"],
            "cache_or_queue": ["cache", "redis", "queue", "message"],
        }
        
        for item in checklist_items:
            if item["status"] != "missing":
                continue
                
            key = item["key"]
            keywords = keyword_mappings.get(key, [])
            
            for kw in keywords:
                if kw in message_lower:
                    updates[key] = {
                        "status": "inferred",
                        "evidence": f"Mentioned in message: {message[:200]}"
                    }
                    break
        
        return updates
    
    def is_meaningful_message(
        self, 
        message: str, 
        checklist_updates: Dict[str, Any],
        repo_url: Optional[str] = None
    ) -> bool:
        """Check if message meaningfully updates project context.
        
        Returns True if:
        - checklist updates detected
        - repo URL detected
        - message contains architecture-relevant keywords
        - message is longer than trivial acknowledgment
        
        Returns False for trivial responses like "ok", "thanks", etc.
        """
        if checklist_updates:
            return True
        
        if repo_url:
            return True
        
        message_lower = message.lower().strip()
        
        if message_lower in self.TRIVIAL_RESPONSES:
            return False
        
        if len(message_lower) < 3:
            return False
        
        for keyword in self.MEANINGFUL_KEYWORDS:
            if keyword in message_lower:
                return True
        
        if len(message) > 30:
            return True
        
        return False
    
    def _message_to_dict(self, model: ChatMessageModel) -> Dict[str, Any]:
        """Convert message model to dict."""
        return {
            "id": model.id,
            "project_id": model.project_id,
            "session_id": model.session_id,
            "role": model.role,
            "content": model.content,
            "message_type": model.message_type,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }


__all__ = ["ChatService"]
