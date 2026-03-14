"""Tests for discovery flow progression and state management.

This test validates that:
1. The assistant asks about repo within first 3 turns
2. User answers update checklist state properly
3. Repeated broad questions are not asked
4. Next question selection is deterministic based on priority
5. Lifecycle tracking (asked/answered) works correctly
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestDiscoveryProgression:
    """Test suite for discovery flow progression."""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mocked orchestrator for testing."""
        with patch('app.discovery.orchestrator.DiscoveryOrchestrator') as MockOrch:
            orch = MockOrch.return_value
            orch.handle_user_message = MagicMock()
            return orch
    
    @pytest.fixture
    def sample_project_id(self):
        """Generate a unique project ID for testing."""
        return f"test-progression-{uuid.uuid4().hex[:8]}"

    def test_repo_asked_within_first_3_turns(self, sample_project_id):
        """Verify that repo_exists is asked within first 3 turns.
        
        This is a critical requirement - repo must be requested early.
        """
        # This test validates the deterministic selection logic
        from app.discovery.orchestrator import DiscoveryOrchestrator
        
        # Mock the dependencies
        with patch('app.discovery.orchestrator.QuestionLifecycleService') as MockLifecycle:
            with patch('app.discovery.orchestrator.ChatService') as MockChat:
                with patch('app.discovery.orchestrator.ChecklistService') as MockChecklist:
                    with patch('app.discovery.orchestrator.AnswerExtractor') as MockExtractor:
                        with patch('app.discovery.orchestrator.DiscoveryReadinessService') as MockReadiness:
                            with patch('app.discovery.orchestrator.QuestionSelector') as MockSelector:
                                with patch('app.discovery.orchestrator.SessionService') as MockSession:
                                    
                                    # Setup mocks
                                    mock_lifecycle = MagicMock()
                                    mock_lifecycle.asked_keys = set()
                                    mock_lifecycle.answered_keys = set()
                                    mock_lifecycle.current_focus_key = None
                                    MockLifecycle.return_value = mock_lifecycle
                                    
                                    mock_session = MagicMock()
                                    mock_session.__getitem__ = lambda s, k: {"id": "sess-123"}.get(k, None)
                                    mock_session.get = lambda k: {"id": "sess-123"}.get(k)
                                    MockSession.return_value.get_session.return_value = {"id": "sess-123"}
                                    
                                    MockChecklist.return_value.get_checklist.return_value = [
                                        {"key": "repo_exists", "status": "missing", "priority": "high"},
                                        {"key": "product_goal", "status": "missing", "priority": "high"},
                                        {"key": "target_users", "status": "missing", "priority": "high"},
                                    ]
                                    
                                    MockExtractor.return_value.extract.return_value = {
                                        "updates": [],
                                        "answered_keys": [],
                                    }
                                    
                                    MockReadiness.return_value.quick_readiness_check.return_value = {
                                        "status": "not_ready",
                                        "coverage": 0.1,
                                    }
                                    
                                    MockSelector.return_value.select.return_value = "product_goal"
                                    
                                    orch = DiscoveryOrchestrator()
                                    
                                    # Turn 1 - should force repo_exists
                                    mock_lifecycle.answered_keys = set()
                                    next_key = orch._select_next_key_deterministic(
                                        MockChecklist.return_value.get_checklist.return_value,
                                        mock_lifecycle,
                                        {"status": "not_ready"},
                                        1  # turn 1
                                    )
                                    assert next_key == "repo_exists", f"Turn 1 should ask for repo, got: {next_key}"
                                    
                                    # Turn 2 - should still ask for repo if not answered
                                    next_key = orch._select_next_key_deterministic(
                                        MockChecklist.return_value.get_checklist.return_value,
                                        mock_lifecycle,
                                        {"status": "not_ready"},
                                        2  # turn 2
                                    )
                                    assert next_key == "repo_exists", f"Turn 2 should ask for repo if not answered, got: {next_key}"
                                    
                                    # Turn 3 - should still ask for repo if not answered
                                    next_key = orch._select_next_key_deterministic(
                                        MockChecklist.return_value.get_checklist.return_value,
                                        mock_lifecycle,
                                        {"status": "not_ready"},
                                        3  # turn 3
                                    )
                                    assert next_key == "repo_exists", f"Turn 3 should ask for repo if not answered, got: {next_key}"
    
    def test_checklist_updated_from_user_response(self, sample_project_id):
        """Verify that user responses properly update checklist items.
        
        User says: "Software de gestão de uma fábrica de artefatos de cimento"
        Expected: product_goal should be updated to confirmed/inferred
        """
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        # Simulate user message about product
        user_message = "Software de gestão de uma fábrica de artefatos de cimento"
        checklist = [
            {"key": "product_goal", "status": "missing", "priority": "high"},
            {"key": "target_users", "status": "missing", "priority": "high"},
            {"key": "repo_exists", "status": "missing", "priority": "high"},
        ]
        
        result = extractor._extract_with_heuristics(user_message, checklist)
        
        # Should detect product_goal
        updated_keys = [u["key"] for u in result.get("updates", [])]
        
        # At minimum, product_goal should be addressed
        assert "product_goal" in updated_keys, f"product_goal should be updated, got: {updated_keys}"
        
    def test_user_response_with_target_users(self):
        """Verify target_users is detected from user response.
        
        User says: "we sell them to stores b2b"
        Expected: target_users should be inferred/confirmed
        """
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        user_message = "we sell them to stores b2b"
        checklist = [
            {"key": "product_goal", "status": "confirmed", "priority": "high"},
            {"key": "target_users", "status": "missing", "priority": "high"},
            {"key": "repo_exists", "status": "missing", "priority": "high"},
        ]
        
        result = extractor._extract_with_heuristics(user_message, checklist)
        
        updated_keys = [u["key"] for u in result.get("updates", [])]
        
        # target_users should be detected
        assert "target_users" in updated_keys, f"target_users should be updated, got: {updated_keys}"
        
    def test_no_repeated_broad_questions(self):
        """Verify that already-answered questions are not asked again.
        
        If product_goal is already answered, the selector should not return it again.
        """
        from app.discovery.orchestrator import DiscoveryOrchestrator
        
        with patch('app.discovery.orchestrator.QuestionLifecycleService') as MockLifecycle:
            with patch('app.discovery.orchestrator.QuestionSelector') as MockSelector:
                # Setup: product_goal already answered
                mock_lifecycle = MagicMock()
                mock_lifecycle.asked_keys = {"product_goal", "repo_exists"}
                mock_lifecycle.answered_keys = {"product_goal"}
                mock_lifecycle.current_focus_key = None
                MockLifecycle.return_value = mock_lifecycle
                
                checklist = [
                    {"key": "repo_exists", "status": "missing", "priority": "high"},
                    {"key": "product_goal", "status": "confirmed", "priority": "high"},
                    {"key": "target_users", "status": "missing", "priority": "high"},
                ]
                
                readiness = {"status": "not_ready"}
                
                orch = DiscoveryOrchestrator()
                
                # Turn 4, repo already answered, product_goal already answered
                next_key = orch._select_next_key_deterministic(
                    checklist,
                    mock_lifecycle,
                    readiness,
                    4  # turn 4
                )
                
                # Should NOT return product_goal (already answered)
                # Should return target_users (next priority)
                assert next_key != "product_goal", "Should not ask already-answered question"
                assert next_key in ["target_users", "repo_exists"], f"Should ask next priority item, got: {next_key}"

    def test_lifecycle_loads_state_from_db(self):
        """Verify lifecycle service loads state from database."""
        from app.discovery.question_lifecycle_service import QuestionLifecycleService
        
        with patch('app.discovery.lifecycle_repository.DiscoveryQuestionLifecycleRepository') as MockRepo:
            # Setup mock to return existing state
            mock_repo_instance = MagicMock()
            mock_repo_instance.get_state.return_value = [
                {"intent_key": "product_goal", "status": "answered"},
                {"intent_key": "repo_exists", "status": "open"},
            ]
            MockRepo.return_value = mock_repo_instance
            
            # Create lifecycle with project_id - should load state
            lifecycle = QuestionLifecycleService("test-project")
            
            # Verify state was loaded
            assert "product_goal" in lifecycle.answered_keys, "Should load answered keys from DB"
            assert "repo_exists" in lifecycle.asked_keys, "Should load asked keys from DB"

    def test_deterministic_priority_order(self):
        """Verify deterministic priority order is enforced.
        
        Priority should be: repo_exists -> product_goal -> target_users -> ...
        """
        from app.discovery.orchestrator import DiscoveryOrchestrator
        
        with patch('app.discovery.orchestrator.QuestionLifecycleService') as MockLifecycle:
            with patch('app.discovery.orchestrator.QuestionSelector') as MockSelector:
                mock_lifecycle = MagicMock()
                mock_lifecycle.asked_keys = set()
                mock_lifecycle.answered_keys = {"repo_exists"}  # repo already answered
                mock_lifecycle.current_focus_key = None
                MockLifecycle.return_value = mock_lifecycle
                
                checklist = [
                    {"key": "repo_exists", "status": "confirmed", "priority": "high"},
                    {"key": "product_goal", "status": "missing", "priority": "high"},
                    {"key": "target_users", "status": "missing", "priority": "high"},
                    {"key": "entry_channels", "status": "missing", "priority": "high"},
                    {"key": "application_type", "status": "missing", "priority": "high"},
                ]
                
                readiness = {"status": "not_ready"}
                
                orch = DiscoveryOrchestrator()
                
                # After repo is answered, should go to product_goal
                next_key = orch._select_next_key_deterministic(
                    checklist,
                    mock_lifecycle,
                    readiness,
                    4  # turn 4
                )
                
                assert next_key == "product_goal", f"After repo, should ask product_goal, got: {next_key}"
                
                # Mark product_goal as answered
                mock_lifecycle.answered_keys.add("product_goal")
                
                next_key = orch._select_next_key_deterministic(
                    checklist,
                    mock_lifecycle,
                    readiness,
                    5
                )
                
                assert next_key == "target_users", f"After product_goal, should ask target_users, got: {next_key}"


class TestAnswerExtraction:
    """Test suite for answer extraction."""
    
    def test_extracts_product_goal_from_description(self):
        """Test extraction of product_goal from project description."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        test_cases = [
            "Software de gestão de uma fábrica de artefatos de cimento",
            "I'm building a management system for a concrete factory",
            "We make postes de concreto and manilhas",
            "A platform for selling concrete products B2B",
        ]
        
        checklist = [
            {"key": "product_goal", "status": "missing", "priority": "high"},
            {"key": "target_users", "status": "missing", "priority": "high"},
        ]
        
        for message in test_cases:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = [u["key"] for u in result.get("updates", [])]
            # Each message should update product_goal
            assert "product_goal" in updated, f"Failed to extract from: {message}"
    
    def test_extracts_target_users_from_b2b(self):
        """Test extraction of target_users from B2B context."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        test_cases = [
            "we sell them to stores b2b",
            "selling to businesses B2B",
            "our customers are retail stores",
            "target users are companies and factories",
        ]
        
        checklist = [
            {"key": "product_goal", "status": "confirmed", "priority": "high"},
            {"key": "target_users", "status": "missing", "priority": "high"},
        ]
        
        for message in test_cases:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = [u["key"] for u in result.get("updates", [])]
            # Each message should update target_users
            assert "target_users" in updated, f"Failed to extract target_users from: {message}"
    
    def test_detects_repo_url(self):
        """Test detection of GitHub repo URL."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        test_cases = [
            "Here's my repo: https://github.com/user/project",
            "github.com/mycompany/myapp",
            "The code is at gitlab.com/team/repo",
        ]
        
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
        ]
        
        for message in test_cases:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = [u["key"] for u in result.get("updates", [])]
            assert "repo_exists" in updated, f"Failed to detect repo from: {message}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
