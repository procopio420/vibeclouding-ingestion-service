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
from datetime import datetime
from typing import Optional
from unittest.mock import patch, MagicMock


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
                                with patch('app.discovery.orchestrator.DiscoverySessionService') as MockSession:
                                    
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


class TestProjectNameExtraction:
    """Test suite for project name extraction."""
    
    def test_project_name_not_from_description(self):
        """Generic product description should NOT become project_name.
        
        "software de gestão de uma fábrica" is product_goal, NOT project_name.
        """
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        # These are product descriptions, NOT project names
        descriptions = [
            "software de gestão de uma fábrica de artefatos de cimento",
            "gestão de uma fábrica de concreto",
            "managing a concrete factory",
            "sistema para fabricar postes",
        ]
        
        checklist = [
            {"key": "project_name", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        
        for message in descriptions:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = {u["key"]: u["status"] for u in result.get("updates", [])}
            # project_name should NOT be updated from these
            if "project_name" in updated:
                assert updated["project_name"] != "confirmed", f"Description should not become project_name: {message}"
    
    def test_explicit_project_name_extraction(self):
        """Explicit project name should be extracted correctly."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        # These ARE explicit project names
        explicit_names = [
            "It's called Concreto Online",
            "My project name is SmartBuild",
            "O projeto se chama VendasPro",
            "chama-se FabricaTech",
        ]
        
        checklist = [
            {"key": "project_name", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        
        for message in explicit_names:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = {u["key"]: u["status"] for u in result.get("updates", [])}
            # project_name should be confirmed
            assert updated.get("project_name") == "confirmed", f"Should extract explicit name from: {message}"


class TestRepoExplicitHandling:
    """Test suite for explicit repo yes/no handling."""
    
    def test_repo_explicit_yes(self):
        """Explicit yes to repo question should mark confirmed."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        yes_responses = [
            "yes",
            "yeah",
            "yep",
            "sure",
            "sim",
            "tenho",
            "Yes, I have a repo",
            "yeah we have one",
        ]
        
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
        ]
        
        for message in yes_responses:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = {u["key"]: u["status"] for u in result.get("updates", [])}
            assert updated.get("repo_exists") == "confirmed", f"'yes' should mark repo confirmed: {message}"
    
    def test_repo_explicit_no(self):
        """Explicit no should mark as missing (not inferred)."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        no_responses = [
            "no",
            "nope",
            "não",
            "nao",
            "not yet",
            "ainda não",
            "don't have one",
            "I don't have a repo",
        ]
        
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
        ]
        
        for message in no_responses:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = {u["key"]: u["status"] for u in result.get("updates", [])}
            # Explicit no should mark as missing (not inferred)
            assert updated.get("repo_exists") == "missing", f"'no' should mark repo as missing: {message}"
    
    def test_repo_not_inferred_from_vague_text(self):
        """Repo should NOT be inferred from vague text like project description."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        # These should NOT trigger repo detection
        vague_messages = [
            "software de gestão de uma fábrica",
            "my project is about concrete",
            "we make postes de concreto",
            "gestão de estoque",
        ]
        
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        
        for message in vague_messages:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = {u["key"]: u["status"] for u in result.get("updates", [])}
            # repo should NOT be updated from these
            assert "repo_exists" not in updated, f"Vague text should not trigger repo: {message}"


class TestEntryChannelsExtraction:
    """Test suite for entry channels extraction."""
    
    def test_entry_channels_mobile(self):
        """Mobile app answer should update entry_channels."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        test_cases = [
            "seria por mobile app",
            "app móvil",
            "celular",
            "smartphone",
            "via mobile",
            "mobile application",
            "ios and android",
        ]
        
        checklist = [
            {"key": "entry_channels", "status": "missing", "priority": "high"},
        ]
        
        for message in test_cases:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = [u["key"] for u in result.get("updates", [])]
            assert "entry_channels" in updated, f"Should extract entry_channels from: {message}"
    
    def test_entry_channels_web(self):
        """Web answer should update entry_channels."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        test_cases = [
            "tudo web mesmo",
            "via navegador",
            "website",
            "via web",
            "web application",
            "navegador",
        ]
        
        checklist = [
            {"key": "entry_channels", "status": "missing", "priority": "high"},
        ]
        
        for message in test_cases:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = [u["key"] for u in result.get("updates", [])]
            assert "entry_channels" in updated, f"Should extract entry_channels from: {message}"


class TestReadinessMissingRepo:
    """Test suite for readiness missing_required_repo flag."""
    
    def test_readiness_missing_repo_flag(self):
        """Readiness should include missing_required_repo when repo is missing."""
        from app.discovery.readiness_service import DiscoveryReadinessService
        
        service = DiscoveryReadinessService()
        
        # Checklist with missing repo
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        
        result = service.quick_readiness_check("test-project", checklist, [])
        
        assert "missing_required_repo" in result
        assert result["missing_required_repo"] == True
    
    def test_readiness_repo_present_no_flag(self):
        """Readiness should NOT include missing_required_repo when repo is present."""
        from app.discovery.readiness_service import DiscoveryReadinessService
        
        service = DiscoveryReadinessService()
        
        # Checklist with confirmed repo
        checklist = [
            {"key": "repo_exists", "status": "confirmed", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        
        result = service.quick_readiness_check("test-project", checklist, [])
        
        assert "missing_required_repo" in result
        assert result["missing_required_repo"] == False


class TestIntentTypeDiscoveryPolicies:
    """Intent-type-specific discovery: project_name fallback, repo absent, repo URL required."""

    def _run_handle_user_message(
        self,
        project_id: str,
        message: str,
        current_focus_key: str,
        checklist: list,
        extraction: dict,
        repo_url: Optional[str] = None,
    ):
        """Run handle_user_message with full mocks; return mocks for assertion."""
        from app.discovery.orchestrator import (
            DiscoveryOrchestrator,
            REPO_ABSENT_VALUE,
            PROJECT_NAME_FALLBACK,
        )

        with patch("app.discovery.orchestrator.QuestionLifecycleService") as MockLifecycle:
            with patch("app.discovery.orchestrator.ChatService") as MockChat:
                with patch("app.discovery.orchestrator.ChecklistService") as MockChecklist:
                    with patch("app.discovery.orchestrator.AnswerExtractor") as MockExtractor:
                        with patch("app.discovery.orchestrator.DiscoveryReadinessService") as MockReadiness:
                            with patch("app.discovery.orchestrator.QuestionSelector") as MockSelector:
                                with patch("app.discovery.orchestrator.DiscoverySessionService") as MockSession:
                                    with patch("app.discovery.orchestrator.ProgressSummaryService") as MockProgress:
                                        with patch("app.discovery.orchestrator.NaturalLanguageMapper"):
                                            with patch.object(
                                                DiscoveryOrchestrator,
                                                "_trigger_repo_ingestion",
                                                return_value="job-123",
                                            ) as mock_trigger:
                                                with patch.object(
                                                    DiscoveryOrchestrator,
                                                    "_generate_response_with_gemini",
                                                    return_value="Ok.",
                                                ):
                                                    with patch.object(
                                                        DiscoveryOrchestrator,
                                                        "_update_meaningful_timestamp",
                                                    ):
                                                        mock_lifecycle = MagicMock()
                                                        mock_lifecycle.asked_keys = set()
                                                        mock_lifecycle.answered_keys = set()
                                                        mock_lifecycle.current_focus_key = current_focus_key
                                                        mock_lifecycle.load_state = lambda pid: None
                                                        mock_lifecycle.mark_asked = lambda pid, k: mock_lifecycle.asked_keys.add(k)
                                                        mock_lifecycle.mark_answered = lambda pid, k: mock_lifecycle.answered_keys.add(k)
                                                        MockLifecycle.return_value = mock_lifecycle

                                                        MockSession.return_value.get_session.return_value = {
                                                            "id": "sess-1",
                                                            "project_id": project_id,
                                                            "state": "clarifying_core_requirements",
                                                            "current_focus_key": current_focus_key,
                                                            "focus_attempt_count": 1,
                                                        }

                                                        MockChecklist.return_value.get_checklist.return_value = checklist
                                                        mock_update_item = MockChecklist.return_value.update_item

                                                        MockChat.return_value.save_message.return_value = {"id": "msg-1", "content": message}
                                                        MockChat.return_value.detect_repo_url.return_value = repo_url
                                                        MockChat.return_value.is_meaningful_message.return_value = True

                                                        MockExtractor.return_value.extract.return_value = extraction

                                                        MockReadiness.return_value.quick_readiness_check.return_value = {
                                                            "status": "not_ready",
                                                            "coverage": 0.2,
                                                        }
                                                        MockSelector.return_value.select.return_value = "product_goal"
                                                        MockProgress.return_value.compute_progress.return_value = {}

                                                        orch = DiscoveryOrchestrator()
                                                        orch.handle_user_message(project_id, message)

                                                        return {
                                                            "update_item": mock_update_item,
                                                            "lifecycle": mock_lifecycle,
                                                            "trigger_repo": mock_trigger,
                                                        }

    def test_no_project_name_advances_with_fallback(self):
        """User does not know project name ('não sei', 'ainda não definimos'); flow advances with fallback."""
        from app.discovery.orchestrator import PROJECT_NAME_FALLBACK

        project_id = "proj-no-name"
        checklist = [
            {"key": "project_name", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        extraction = {"updates": [], "answered_keys": []}  # no project_name in answer

        out = self._run_handle_user_message(
            project_id=project_id,
            message="não sei",
            current_focus_key="project_name",
            checklist=checklist,
            extraction=extraction,
            repo_url=None,
        )
        update_item = out["update_item"]
        lifecycle = out["lifecycle"]

        # Fallback applied
        calls = [c for c in update_item.call_args_list if c[1].get("key") == "project_name"]
        assert len(calls) >= 1, "project_name should be updated with fallback"
        fallback_call = next((c for c in calls if c[1].get("value") == PROJECT_NAME_FALLBACK), None)
        assert fallback_call is not None, f"expected project_name value={PROJECT_NAME_FALLBACK!r}"
        assert "project_name" in lifecycle.answered_keys

    def test_repo_absent_persisted_no_ingestion(self):
        """User says 'não tenho' repo; repo_exists → value=absent, lifecycle answered, no ingestion."""
        from app.discovery.orchestrator import REPO_ABSENT_VALUE

        project_id = "proj-no-repo"
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        extraction = {"updates": [], "answered_keys": []}

        out = self._run_handle_user_message(
            project_id=project_id,
            message="não tenho",
            current_focus_key="repo_exists",
            checklist=checklist,
            extraction=extraction,
            repo_url=None,
        )
        update_item = out["update_item"]
        lifecycle = out["lifecycle"]
        trigger_repo = out["trigger_repo"]

        calls = [c for c in update_item.call_args_list if c[1].get("key") == "repo_exists"]
        assert len(calls) >= 1
        repo_call = next((c for c in calls if c[1].get("value") == REPO_ABSENT_VALUE), None)
        assert repo_call is not None, f"expected repo_exists value={REPO_ABSENT_VALUE!r}"
        assert "repo_exists" in lifecycle.answered_keys
        trigger_repo.assert_not_called()

    def test_repo_present_but_url_missing_not_resolved(self):
        """User says 'sim, tenho'; repo not marked resolved; no ingestion; next stays repo_exists until URL."""
        project_id = "proj-repo-no-url"
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        extraction = {"updates": [{"key": "repo_exists", "status": "confirmed", "value": ""}], "answered_keys": ["repo_exists"]}

        out = self._run_handle_user_message(
            project_id=project_id,
            message="sim, tenho",
            current_focus_key="repo_exists",
            checklist=checklist,
            extraction=extraction,
            repo_url=None,
        )
        lifecycle = out["lifecycle"]
        trigger_repo = out["trigger_repo"]

        # Sufficiency is PARTIAL for "sim, tenho" without URL → we don't mark answered from extraction and don't set absent
        assert "repo_exists" not in lifecycle.answered_keys
        trigger_repo.assert_not_called()

    def test_valid_repo_url_resolved_and_ingestion_triggered(self):
        """User sends valid GitHub URL; repo_exists confirmed with URL; lifecycle answered; ingestion triggered."""
        project_id = "proj-with-repo"
        url = "https://github.com/user/myapp"
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        extraction = {"updates": [], "answered_keys": []}

        out = self._run_handle_user_message(
            project_id=project_id,
            message=f"aqui: {url}",
            current_focus_key="repo_exists",
            checklist=checklist,
            extraction=extraction,
            repo_url=url,
        )
        update_item = out["update_item"]
        lifecycle = out["lifecycle"]
        trigger_repo = out["trigger_repo"]

        calls = [c for c in update_item.call_args_list if c[1].get("key") == "repo_exists"]
        assert len(calls) >= 1
        url_call = next((c for c in calls if c[1].get("value") == url), None)
        assert url_call is not None, f"expected repo_exists value={url!r}"
        assert "repo_exists" in lifecycle.answered_keys
        trigger_repo.assert_called_once_with(project_id, url)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
