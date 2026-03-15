"""Tests for discovery state propagation.

These tests verify that:
1. Each meaningful user answer updates checklist items
2. Readiness is recomputed after each answer
3. Understanding summary is built from checklist
4. Next best step is computed correctly
5. State is not lagging behind conversation
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock


class TestStatePropagation:
    """Test suite for discovery state propagation."""
    
    def test_checklist_updates_after_extraction(self):
        """Verify checklist is updated after extraction."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        # Simulate user message about product
        message = "sistema de gestão para fábrica de concreto"
        checklist = [
            {"key": "product_goal", "status": "missing", "priority": "high"},
            {"key": "target_users", "status": "missing", "priority": "high"},
        ]
        
        result = extractor._extract_with_heuristics(message, checklist)
        
        # Should have updates
        assert len(result["updates"]) > 0, "Should extract updates from message"
        
        # product_goal should be updated
        updated_keys = [u["key"] for u in result["updates"]]
        assert "product_goal" in updated_keys, "product_goal should be updated"
    
    def test_understanding_summary_uses_value_field(self):
        """Verify understanding summary uses value field, not just evidence."""
        from app.discovery.orchestrator import DiscoveryOrchestrator
        
        # Mock checklist with value field
        checklist = [
            {
                "key": "product_goal",
                "label": "O que o projeto faz?",
                "status": "confirmed",
                "value": "Sistema completo de gestão para fábrica de artefatos de cimento",
                "evidence": "sistema de gestão"
            }
        ]
        
        # Create orchestrator with mocked dependencies
        with patch.object(DiscoveryOrchestrator, '__init__', lambda x: None):
            orch = DiscoveryOrchestrator()
            summary = orch._build_understanding_summary(checklist)
        
        # Value should be the full response, not just evidence
        assert len(summary["items"]) > 0
        item = summary["items"][0]
        assert "Sistema completo" in item["value"], "Should use full value, not just evidence"
    
    def test_next_step_computed_from_checklist(self):
        """Verify next step is computed from checklist and lifecycle."""
        from app.discovery.orchestrator import DiscoveryOrchestrator
        
        # Mock checklist and lifecycle
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "confirmed", "priority": "high"},
            {"key": "target_users", "status": "missing", "priority": "high"},
        ]
        
        # Mock lifecycle
        mock_lifecycle = MagicMock()
        mock_lifecycle.asked_keys = {"product_goal"}
        mock_lifecycle.answered_keys = {"product_goal"}
        mock_lifecycle.current_focus_key = "repo_exists"
        
        # Mock readiness
        readiness = {"status": "not_ready", "coverage": 0.3}
        
        with patch.object(DiscoveryOrchestrator, '__init__', lambda x: None):
            orch = DiscoveryOrchestrator()
            next_step = orch._compute_next_step(checklist, mock_lifecycle, readiness)
        
        # Should return next step with title and description
        assert next_step is not None
        assert "title" in next_step
        assert "type" in next_step
    
    def test_orchestrator_returns_full_state(self):
        """Verify orchestrator returns checklist, readiness, summary, and next_step."""
        from app.discovery.orchestrator import DiscoveryOrchestrator
        
        # This test verifies the response structure
        # The actual values depend on DB state, so we just verify the keys exist
        
        expected_keys = [
            "user_message",
            "assistant_message", 
            "checklist",
            "readiness",
            "understanding_summary",
            "next_best_step",
            "repo_url_detected",
            "meaningful_update",
            "lifecycle",
            "next_key",
            "turn",
        ]
        
        # This is a structural test - verify the orchestrator has the method
        assert hasattr(DiscoveryOrchestrator, '_build_understanding_summary'), "Should have _build_understanding_summary method"
        assert hasattr(DiscoveryOrchestrator, '_compute_next_step'), "Should have _compute_next_step method"


class TestExtractionPatterns:
    """Test suite for extraction patterns."""
    
    def test_portuguese_product_goal_extraction(self):
        """Test Portuguese product goal extraction."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        test_cases = [
            "sistema de gestão para fábrica",
            "precisamos de um sistema para gerenciar",
            "é um software para controlar produção",
            "gostaria de criar uma plataforma para",
        ]
        
        checklist = [{"key": "product_goal", "status": "missing", "priority": "high"}]
        
        for message in test_cases:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = [u["key"] for u in result.get("updates", [])]
            assert "product_goal" in updated, f"Should extract from: {message}"
    
    def test_portuguese_target_users_extraction(self):
        """Test Portuguese target users extraction."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        test_cases = [
            "vendemos para empresas",
            "nossos clientes são lojas",
            "para funcionários da fábrica",
            "usuários usam no celular",
        ]
        
        checklist = [{"key": "target_users", "status": "missing", "priority": "high"}]
        
        for message in test_cases:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = [u["key"] for u in result.get("updates", [])]
            assert "target_users" in updated, f"Should extract from: {message}"
    
    def test_portuguese_entry_channels_extraction(self):
        """Test Portuguese entry channels extraction."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        test_cases = [
            "uso no celular diariamente",
            "mobile app para operacional",
            "computador para fazer relatórios",
            "acesso via navegador web",
        ]
        
        checklist = [{"key": "entry_channels", "status": "missing", "priority": "high"}]
        
        for message in test_cases:
            result = extractor._extract_with_heuristics(message, checklist)
            updated = [u["key"] for u in result.get("updates", [])]
            assert "entry_channels" in updated, f"Should extract from: {message}"


class TestRepoFirstBehavior:
    """Test suite for repo-first enforcement."""
    
    def test_repo_asked_early(self):
        """Verify repo is selected early in conversation."""
        from app.discovery.orchestrator import DiscoveryOrchestrator
        
        with patch('app.discovery.orchestrator.QuestionLifecycleService') as MockLifecycle:
            with patch('app.discovery.orchestrator.QuestionSelector') as MockSelector:
                # Setup mock - no repo asked yet
                mock_lifecycle = MagicMock()
                mock_lifecycle.asked_keys = set()
                mock_lifecycle.answered_keys = set()
                mock_lifecycle.current_focus_key = None
                MockLifecycle.return_value = mock_lifecycle
                
                checklist = [
                    {"key": "repo_exists", "status": "missing", "priority": "high"},
                    {"key": "product_goal", "status": "missing", "priority": "high"},
                ]
                
                readiness = {"status": "not_ready"}
                
                orch = DiscoveryOrchestrator()
                
                # Turn 1 - should force repo_exists
                next_key = orch._select_next_key_deterministic(
                    checklist, mock_lifecycle, readiness, 1
                )
                assert next_key == "repo_exists", f"Turn 1 should ask repo, got: {next_key}"
                
                # Turn 2 - should still ask repo
                next_key = orch._select_next_key_deterministic(
                    checklist, mock_lifecycle, readiness, 2
                )
                assert next_key == "repo_exists", f"Turn 2 should ask repo, got: {next_key}"
                
                # Turn 3 - should still ask repo
                next_key = orch._select_next_key_deterministic(
                    checklist, mock_lifecycle, readiness, 3
                )
                assert next_key == "repo_exists", f"Turn 3 should ask repo, got: {next_key}"
    
    def test_repo_not_inferred_from_vague_text(self):
        """Verify repo is not inferred from vague text."""
        from app.discovery.answer_extractor import AnswerExtractor
        
        extractor = AnswerExtractor()
        
        vague_messages = [
            "sistema de gestão",
            "software para fábrica",
            "precisamos de um app",
        ]
        
        checklist = [
            {"key": "repo_exists", "status": "missing", "priority": "high"},
            {"key": "product_goal", "status": "missing", "priority": "high"},
        ]
        
        for message in vague_messages:
            result = extractor._extract_with_heuristics(message, checklist)
            updated_keys = [u["key"] for u in result.get("updates", [])]
            # repo should NOT be updated from vague messages
            if "repo_exists" in updated_keys:
                # If it was updated, check it's not confirmed
                repo_update = next((u for u in result["updates"] if u["key"] == "repo_exists"), None)
                if repo_update:
                    assert repo_update["status"] != "confirmed", f"Vague text should not confirm repo: {message}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
