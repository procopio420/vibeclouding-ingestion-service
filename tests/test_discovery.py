"""Tests for discovery flow."""
import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.discovery.state_machine import DiscoveryStateMachine
from app.discovery.chat_service import ChatService

client = TestClient(app)


def test_project_auto_starts_discovery():
    """Test that creating a project auto-starts discovery."""
    with patch('app.api.routes.projects.orchestrator') as mock_orch:
        mock_orch.start_discovery.return_value = {
            "session": {"id": "sess-123", "state": "collecting_initial_context"},
            "checklist": [],
            "response": "Hi!"
        }
        
        response = client.post("/projects", json={
            "project_name": "Test Project",
            "summary": "A test project"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] is not None
        assert data["status"] == "collecting_initial_context"


def test_get_discovery_session():
    """Test getting discovery session."""
    with patch('app.api.routes.discovery.orchestrator') as mock_orch:
        mock_orch.get_discovery_state.return_value = {
            "session": {"id": "sess-123", "state": "collecting_initial_context"},
            "checklist": [],
            "readiness": {"status": "not_ready"}
        }
        
        response = client.get("/projects/test-project-id/discovery/session")
        
        assert response.status_code == 200


def test_get_checklist():
    """Test getting checklist."""
    with patch('app.api.routes.discovery.checklist_service') as mock_svc:
        mock_svc.get_checklist.return_value = [
            {"key": "product_goal", "status": "missing", "priority": "high"}
        ]
        
        response = client.get("/projects/test-id/checklist")
        
        assert response.status_code == 200
        data = response.json()
        assert "checklist" in data


def test_get_questions():
    """Test getting open questions."""
    with patch('app.api.routes.discovery.question_service') as mock_svc:
        mock_svc.get_open_questions.return_value = [
            {"id": "q1", "question": "What does your project do?", "status": "open"}
        ]
        
        response = client.get("/projects/test-id/questions")
        
        assert response.status_code == 200
        data = response.json()
        assert "questions" in data


def test_get_readiness():
    """Test getting readiness."""
    with patch('app.api.routes.discovery.readiness_service') as mock_svc:
        mock_svc.compute_readiness.return_value = {
            "status": "not_ready",
            "confidence": 0.1,
            "coverage": 0.0
        }
        
        response = client.get("/projects/test-id/readiness")
        
        assert response.status_code == 200
        data = response.json()
        assert "readiness" in data


def test_state_machine_valid_transitions():
    """Test state machine transitions."""
    assert DiscoveryStateMachine.can_transition("idle", "collecting_initial_context")
    assert DiscoveryStateMachine.can_transition("collecting_initial_context", "ingesting_sources")
    assert DiscoveryStateMachine.can_transition("ingesting_sources", "clarifying_core_requirements")
    assert DiscoveryStateMachine.can_transition("clarifying_core_requirements", "merging_context")
    assert DiscoveryStateMachine.can_transition("merging_context", "ready_for_architecture")
    assert not DiscoveryStateMachine.can_transition("idle", "ready_for_architecture")
    assert not DiscoveryStateMachine.can_transition("ready_for_architecture", "idle")


def test_chat_service_detects_github_url():
    """Test GitHub URL detection in messages."""
    service = ChatService()
    
    url1 = service.detect_repo_url("Check out https://github.com/user/repo")
    assert url1 == "https://github.com/user/repo"
    
    url2 = service.detect_repo_url("My repo is git@github.com:user/project.git")
    assert url2 == "git@github.com:user/project"
    
    url3 = service.detect_repo_url("I don't have a repo yet")
    assert url3 is None


def test_chat_message_persisted():
    """Test posting a chat message."""
    with patch('app.api.routes.discovery.orchestrator') as mock_orch:
        mock_orch.handle_user_message.return_value = {
            "user_message": {"id": "m1", "role": "user", "content": "Hello"},
            "assistant_message": {"id": "m2", "role": "assistant", "content": "Hi!"},
            "checklist": [],
            "readiness": {"status": "not_ready"},
            "repo_url_detected": False
        }
        
        response = client.post(
            "/projects/test-id/chat/messages",
            json={"message": "Hello"}
        )
        
        assert response.status_code == 200


def test_project_not_found():
    """Test 404 for non-existent project."""
    response = client.get("/projects/nonexistent/discovery/session")
    assert response.status_code == 404


# ============================================================================
# Hardened Readiness Tests
# ============================================================================

def test_quick_readiness_not_ready_when_critical_missing():
    """Test quick readiness returns not_ready when critical items missing."""
    from app.discovery.readiness_service import DiscoveryReadinessService
    
    service = DiscoveryReadinessService()
    
    checklist = [
        {"key": "product_goal", "status": "missing", "priority": "high"},
        {"key": "target_users", "status": "missing", "priority": "high"},
        {"key": "application_type", "status": "missing", "priority": "high"},
        {"key": "database", "status": "missing", "priority": "medium"},
    ]
    
    result = service.quick_readiness_check("test-project", checklist)
    
    assert result["status"] == "not_ready"
    assert "product_goal" in result["missing_critical_items"]


def test_quick_readiness_needs_clarification_when_coverage_low():
    """Test quick readiness returns needs_clarification with partial coverage."""
    from app.discovery.readiness_service import DiscoveryReadinessService
    
    service = DiscoveryReadinessService()
    
    checklist = [
        {"key": "product_goal", "status": "confirmed", "priority": "high"},
        {"key": "target_users", "status": "confirmed", "priority": "high"},
        {"key": "application_type", "status": "missing", "priority": "medium"},
        {"key": "database", "status": "missing", "priority": "medium"},
    ]
    
    result = service.quick_readiness_check("test-project", checklist)
    
    assert result["status"] == "needs_clarification"


def test_quick_readiness_maybe_ready_at_40_percent():
    """Test quick readiness returns maybe_ready at 40% coverage."""
    from app.discovery.readiness_service import DiscoveryReadinessService
    
    service = DiscoveryReadinessService()
    
    # 6 items, 3 confirmed = 50% coverage
    checklist = [
        {"key": "product_goal", "status": "confirmed", "priority": "high"},
        {"key": "target_users", "status": "confirmed", "priority": "high"},
        {"key": "database", "status": "confirmed", "priority": "medium"},
        {"key": "auth_model", "status": "inferred", "priority": "medium"},
        {"key": "application_type", "status": "missing", "priority": "medium"},
        {"key": "external_integrations", "status": "missing", "priority": "low"},
    ]
    
    result = service.quick_readiness_check("test-project", checklist)
    
    assert result["status"] == "maybe_ready"
    assert result["coverage"] >= 0.4


def test_quick_readiness_ready_at_70_percent():
    """Test quick readiness returns ready_for_architecture at 70% coverage."""
    from app.discovery.readiness_service import DiscoveryReadinessService
    
    service = DiscoveryReadinessService()
    
    # 10 items, 7 covered = 70% coverage
    checklist = [
        {"key": "product_goal", "status": "confirmed", "priority": "high"},
        {"key": "target_users", "status": "confirmed", "priority": "high"},
        {"key": "application_type", "status": "confirmed", "priority": "high"},
        {"key": "database", "status": "confirmed", "priority": "medium"},
        {"key": "auth_model", "status": "confirmed", "priority": "medium"},
        {"key": "external_integrations", "status": "inferred", "priority": "medium"},
        {"key": "entry_channels", "status": "inferred", "priority": "medium"},
        {"key": "core_components", "status": "missing", "priority": "low"},
        {"key": "cache_or_queue", "status": "missing", "priority": "low"},
        {"key": "background_processing", "status": "missing", "priority": "low"},
    ]
    
    result = service.quick_readiness_check("test-project", checklist)
    
    assert result["status"] == "ready_for_architecture"
    assert result["coverage"] >= 0.7


def test_quick_readiness_with_blocking_questions():
    """Test quick readiness considers blocking questions."""
    from app.discovery.readiness_service import DiscoveryReadinessService
    
    service = DiscoveryReadinessService()
    
    checklist = [
        {"key": "product_goal", "status": "confirmed", "priority": "high"},
        {"key": "target_users", "status": "confirmed", "priority": "high"},
    ]
    
    open_questions = [
        {"question": "What database will you use?", "priority": "high"},
    ]
    
    result = service.quick_readiness_check("test-project", checklist, open_questions)
    
    assert result["status"] == "needs_clarification"
    assert len(result["blocking_questions"]) > 0


def test_full_readiness_considers_context():
    """Test full readiness evaluates consolidated context."""
    from app.discovery.readiness_service import DiscoveryReadinessService
    
    service = DiscoveryReadinessService()
    
    checklist = [
        {"key": "product_goal", "status": "confirmed", "priority": "high"},
        {"key": "target_users", "status": "confirmed", "priority": "high"},
    ]
    
    with patch('app.discovery.readiness_service.DiscoveryReadinessService._has_consolidated_context', return_value=True):
        with patch('app.discovery.readiness_service.DiscoveryReadinessService._is_ingestion_complete', return_value=True):
            result = service.full_readiness_check("test-project", checklist)
    
    assert result["check_type"] == "full"
    assert result["context_summary_available"] == True
    assert result["ingestion_complete"] == True


def test_full_readiness_ready_with_context_and_ingestion():
    """Test full readiness returns ready when context and ingestion available."""
    from app.discovery.readiness_service import DiscoveryReadinessService
    
    service = DiscoveryReadinessService()
    
    # Good coverage checklist
    checklist = [
        {"key": "product_goal", "status": "confirmed", "priority": "high"},
        {"key": "target_users", "status": "confirmed", "priority": "high"},
        {"key": "application_type", "status": "confirmed", "priority": "high"},
        {"key": "database", "status": "confirmed", "priority": "medium"},
        {"key": "auth_model", "status": "inferred", "priority": "medium"},
        {"key": "external_integrations", "status": "inferred", "priority": "medium"},
    ]
    
    with patch('app.discovery.readiness_service.DiscoveryReadinessService._has_consolidated_context', return_value=True):
        with patch('app.discovery.readiness_service.DiscoveryReadinessService._is_ingestion_complete', return_value=True):
            result = service.full_readiness_check("test-project", checklist)
    
    # Full check with context + ingestion + good coverage should be ready
    assert result["status"] == "ready_for_architecture"


# ============================================================================
# Meaningful Message Detection Tests
# ============================================================================

def test_is_meaningful_trivial_responses():
    """Test that trivial responses are not meaningful."""
    from app.discovery.chat_service import ChatService
    
    service = ChatService()
    
    trivial_messages = [
        "ok", "thanks", "got it", "yep", "sure", "👍", 
        "thank you", "np", "no problem", "kk", "okay", 
        "cool", "nice", "great", "sounds good", "perfect",
        "alright", "yes", "no", "maybe"
    ]
    
    for msg in trivial_messages:
        result = service.is_meaningful_message(msg, {})
        assert result == False, f"Expected '{msg}' to be trivial"


def test_is_meaningful_short_responses():
    """Test that very short responses are not meaningful."""
    from app.discovery.chat_service import ChatService
    
    service = ChatService()
    
    short_messages = ["a", "ab", "hi", "hey"]
    
    for msg in short_messages:
        result = service.is_meaningful_message(msg, {})
        assert result == False, f"Expected '{msg}' to be trivial"


def test_is_meaningful_with_checklist_updates():
    """Test that messages with checklist updates are meaningful."""
    from app.discovery.chat_service import ChatService
    
    service = ChatService()
    
    updates = {"database": {"status": "inferred"}}
    result = service.is_meaningful_message("I'll use PostgreSQL", updates)
    
    assert result == True


def test_is_meaningful_with_repo_url():
    """Test that messages with repo URLs are meaningful."""
    from app.discovery.chat_service import ChatService
    
    service = ChatService()
    
    result = service.is_meaningful_message("My repo is github.com/user/repo", {}, repo_url="https://github.com/user/repo")
    
    assert result == True


def test_is_meaningful_with_architecture_keywords():
    """Test that messages with architecture keywords are meaningful."""
    from app.discovery.chat_service import ChatService
    
    service = ChatService()
    
    keyword_messages = [
        "I need a database with postgres",
        "Will use AWS for hosting",
        "Need authentication with OAuth",
        "Whatsapp API integration needed",
        "Background worker with Redis queue",
        "File storage on S3",
    ]
    
    for msg in keyword_messages:
        result = service.is_meaningful_message(msg, {})
        assert result == True, f"Expected '{msg}' to be meaningful"


def test_is_meaningful_long_messages():
    """Test that longer messages are meaningful even without keywords."""
    from app.discovery.chat_service import ChatService
    
    service = ChatService()
    
    long_message = "I'm building a web application that will help small businesses manage their inventory and orders."
    result = service.is_meaningful_message(long_message, {})
    
    assert result == True
