"""Alembic-driven Postgres DB access for Phase 1 (Postgres-only)."""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey, Boolean, Integer
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://vibe:vibe@db:5432/vibe_context")

engine = create_engine(DATABASE_URL, future=True, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()

class ProjectModel(Base):
    __tablename__ = "projects"
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(50), default="created", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    revision_decision = Column(String(50), nullable=True)  # vibe_economica | vibe_performance

class JobModel(Base):
    __tablename__ = "jobs"
    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), index=True)
    job_type = Column(String(50), index=True)
    status = Column(String(50), index=True)
    payload = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    retries = Column(String(10), default="0")

class ArtifactModel(Base):
    __tablename__ = "artifacts"
    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), index=True)
    name = Column(String(255))
    path = Column(String(1024))
    type = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class ArchitectureResultModel(Base):
    __tablename__ = "architecture_results"
    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), index=True)
    schema_version = Column(String(20), default="1.0")
    analise_entrada = Column(Text)
    vibe_economica = Column(Text)
    vibe_performance = Column(Text)
    raw_payload = Column(Text)
    raw_payload_storage_key = Column(String(512))
    is_latest = Column(String(10), default="true")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DiscoverySessionModel(Base):
    __tablename__ = "discovery_sessions"
    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), index=True)
    state = Column(String(50), default="collecting_initial_context", index=True)
    readiness_status = Column(String(50), default="not_ready")
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    last_transition_at = Column(DateTime, nullable=True)
    last_user_message_at = Column(DateTime, nullable=True)
    last_system_message_at = Column(DateTime, nullable=True)
    active_ingestion_job_ids = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    # Readiness tracking
    quick_readiness_status = Column(String(20), nullable=True)
    quick_readiness_result = Column(Text, nullable=True)
    quick_readiness_at = Column(DateTime, nullable=True)
    full_readiness_status = Column(String(20), nullable=True)
    full_readiness_result = Column(Text, nullable=True)
    full_readiness_at = Column(DateTime, nullable=True)
    last_meaningful_update_at = Column(DateTime, nullable=True)
    # Architecture trigger tracking
    eligible_for_architecture = Column(Boolean, default=False)
    architecture_triggered = Column(Boolean, default=False)
    architecture_triggered_at = Column(DateTime, nullable=True)
    architecture_trigger_status = Column(String(50), nullable=True)
    architecture_trigger_target = Column(String(512), nullable=True)
    architecture_started_by = Column(String(50), nullable=True)
    # Answer sufficiency: stay on topic until resolved
    current_focus_key = Column(String(100), nullable=True, index=True)
    focus_attempt_count = Column(Integer, default=0)
    resolution_status = Column(String(30), nullable=True)  # sufficient | partial | ambiguous | not_answered


class DiscoveryQuestionLifecycleModel(Base):
    __tablename__ = "discovery_question_lifecycle"
    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), index=True)
    intent_key = Column(String(100), index=True)
    status = Column(String(20), default="open", index=True)
    answer_message_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), index=True)
    session_id = Column(String(36), ForeignKey("discovery_sessions.id"), index=True)
    client_id = Column(String(36), nullable=True, index=True)
    run_id = Column(String(36), nullable=True, index=True)
    role = Column(String(20))
    content = Column(Text)
    message_type = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ChecklistItemModel(Base):
    __tablename__ = "checklist_items"
    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), index=True)
    key = Column(String(50), index=True)
    label = Column(String(255))
    status = Column(String(20), default="missing")
    priority = Column(String(20), nullable=True)
    value = Column(Text, nullable=True)  # Full extracted value from user response
    evidence = Column(Text, nullable=True)  # Brief evidence snippet
    updated_at = Column(DateTime, default=datetime.utcnow)


class ClarificationQuestionModel(Base):
    __tablename__ = "clarification_questions"
    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), index=True)
    question = Column(Text)
    reason = Column(Text, nullable=True)
    priority = Column(String(20), nullable=True)
    status = Column(String(20), default="open", index=True)
    related_checklist_key = Column(String(50), nullable=True)
    answer_source = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

def get_engine():
    return engine

def get_session():
    return SessionLocal()

def init_db():
    # Alembic manages schema in Phase 1
    pass

def ensure_migrations():
    if os.environ.get("MIGRATE_ON_STARTUP", "0").lower() in ("1", "true", "yes"):
        try:
            from alembic.config import Config
            from alembic import command
            cfg_path = os.environ.get("ALEMBIC_CONFIG", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")))
            cfg = Config(cfg_path)
            command.upgrade(cfg, "head")
        except Exception:
            pass

try:
    ensure_migrations()
except Exception:
    pass
