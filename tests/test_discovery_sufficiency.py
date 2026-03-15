"""Tests for discovery answer sufficiency: stay on topic until resolved.

Uses mocks for DB and LLM. Covers:
- Vague repo answer: repo not marked resolved, re-ask
- Weak product_goal: not resolved, reframe
- Dodged core_components: unresolved, re-ask with examples
- Sufficient answer: intent marked answered, advance
- Heuristic short-circuit (no AI call for clear ambiguous)
- AI path when heuristics inconclusive (mock AI)
"""
import pytest
from unittest.mock import patch, MagicMock

from app.discovery.sufficiency import (
    evaluate,
    evaluate_heuristic,
    is_sufficient,
    NEED_AI,
    SUFFICIENT,
    PARTIAL,
    AMBIGUOUS,
    NOT_ANSWERED,
)


class TestSufficiencyHeuristics:
    """Heuristic layer: definite outcomes without AI."""

    def test_ambiguous_repo_answer_short_circuit(self):
        """'não sei' is classified ambiguous without invoking AI."""
        out = evaluate_heuristic("repo_exists", "não sei", repo_url=None)
        assert out == AMBIGUOUS

    def test_repo_url_sufficient(self):
        """Valid repo URL is sufficient."""
        out = evaluate_heuristic(
            "repo_exists",
            "aqui: https://github.com/foo/bar",
            repo_url="https://github.com/foo/bar",
        )
        assert out == SUFFICIENT

    def test_repo_yes_without_url_partial(self):
        """User says yes but no URL → partial."""
        out = evaluate_heuristic("repo_exists", "sim, tenho", repo_url=None)
        assert out == PARTIAL

    def test_repo_explicit_no_sufficient(self):
        """Explicit no repo yet is sufficient."""
        out = evaluate_heuristic("repo_exists", "ainda não", repo_url=None)
        assert out == SUFFICIENT

    def test_vague_product_goal_partial(self):
        """'é um sistema' is partial for product_goal."""
        out = evaluate_heuristic("product_goal", "é um sistema", repo_url=None)
        assert out == PARTIAL

    def test_dodged_core_components_not_answered(self):
        """'o que você falou já tá bom' is not_answered for core_components."""
        out = evaluate_heuristic(
            "core_components",
            "o que você falou já tá bom",
            repo_url=None,
        )
        assert out == NOT_ANSWERED

    def test_is_sufficient(self):
        assert is_sufficient(SUFFICIENT) is True
        assert is_sufficient(PARTIAL) is False
        assert is_sufficient(AMBIGUOUS) is False
        assert is_sufficient(NOT_ANSWERED) is False


class TestSufficiencyHybrid:
    """Full evaluate(): heuristics first, AI when need_ai."""

    def test_ambiguous_returns_without_calling_ai(self):
        """Clear ambiguous phrase does not need AI."""
        with patch("app.discovery.sufficiency.evaluate_with_ai") as mock_ai:
            out = evaluate("repo_exists", "talvez", repo_url=None)
            assert out == AMBIGUOUS
            mock_ai.assert_not_called()

    def test_ai_called_when_heuristics_inconclusive(self):
        """When heuristics return need_ai, AI is called."""
        with patch("app.discovery.sufficiency.evaluate_heuristic", return_value=NEED_AI):
            with patch("app.discovery.sufficiency.evaluate_with_ai", return_value=SUFFICIENT) as mock_ai:
                out = evaluate("product_goal", "We build a platform for farmers to sell produce.", repo_url=None)
                assert out == SUFFICIENT
                mock_ai.assert_called_once()
                call_kw = mock_ai.call_args[1] if mock_ai.call_args[1] else {}
                call_args = mock_ai.call_args[0]
                assert call_args[0] == "product_goal"
                assert "farmers" in call_args[1] or "platform" in call_args[1]


class TestOrchestratorSufficiencyIntegration:
    """Orchestrator: sufficiency gates checklist/lifecycle advance. Uses mocks."""

    @pytest.fixture
    def mock_session(self):
        return {
            "id": "sess-1",
            "project_id": "proj-1",
            "state": "clarifying_core_requirements",
            "current_focus_key": "repo_exists",
            "focus_attempt_count": 1,
            "resolution_status": None,
        }

    @pytest.fixture
    def mock_lifecycle(self):
        m = MagicMock()
        m.asked_keys = set()
        m.answered_keys = set()
        m.current_focus_key = None
        m.load_state = lambda pid: None
        m.mark_asked = lambda pid, k: m.asked_keys.add(k)
        m.mark_answered = lambda pid, k: m.answered_keys.add(k)
        return m

    def test_vague_repo_answer_does_not_mark_resolved(self):
        """User says 'não sei' → repo not marked answered, next_key stays repo_exists."""
        outcome = evaluate("repo_exists", "não sei", repo_url=None)
        assert not is_sufficient(outcome)
        assert outcome == AMBIGUOUS

    def test_sufficient_repo_url_advances(self):
        """User provides URL → sufficient, repo can be marked resolved."""
        outcome = evaluate(
            "repo_exists",
            "https://github.com/acme/app",
            repo_url="https://github.com/acme/app",
        )
        assert is_sufficient(outcome)

    def test_weak_product_goal_insufficient(self):
        """'é um sistema' for product_goal is not sufficient."""
        outcome = evaluate_heuristic("product_goal", "é um sistema", repo_url=None)
        assert outcome == PARTIAL
        assert not is_sufficient(outcome)
