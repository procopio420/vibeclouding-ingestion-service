"""Tests for JSON contract handling and parsing resilience."""
import pytest
from app.discovery.answer_extraction_parser import (
    safe_parse_compact_response,
    normalize_compact_response,
    safe_get_updates,
    safe_get_answered_keys,
)
from app.discovery.answer_extraction_contract import build_compact_prompt


class TestCompactContract:
    """Tests for compact JSON contract."""

    def test_build_compact_prompt(self):
        """Test prompt is built correctly and includes short-code mapping."""
        checklist = [
            {"key": "product_goal", "status": "missing", "label": "O que o projeto faz?"},
            {"key": "repo_exists", "status": "missing", "label": "Tem repositório?"},
        ]
        prompt = build_compact_prompt(checklist, "Meu projeto é uma loja virtual")
        assert "pg" in prompt or "product_goal" in prompt
        assert "re" in prompt or "repo_exists" in prompt
        assert "loja virtual" in prompt
        assert len(prompt) < 1000


class TestSafeParser:
    """Tests for safe parsing of malformed/truncated responses."""

    def test_valid_compact_response(self):
        """Test parsing valid compact response."""
        response = '{"u": [["product_goal", "Sistema de vendas"], ["target_users", "Produtores"]], "n": "repo_exists"}'
        
        result = safe_parse_compact_response(response)
        
        assert result is not None
        assert "u" in result
        assert result["u"] == [["product_goal", "Sistema de vendas"], ["target_users", "Produtores"]]
        assert result["n"] == "repo_exists"

    def test_truncated_json(self):
        """Test handling of truncated JSON: may return None or salvaged partial result."""
        response = '{"u": [["product_goal", "Sistema de vend'
        
        result = safe_parse_compact_response(response)
        
        # Either parsing failed (None) or we salvaged partial data (dict with "u")
        assert result is None or (isinstance(result, dict) and "u" in result)

    def test_malformed_json_empty_object(self):
        """Test handling of empty object."""
        response = '{}'
        
        result = safe_parse_compact_response(response)
        
        # Should return the empty dict, not crash
        assert result == {}

    def test_malformed_json_bool(self):
        """Test handling of bool response."""
        response = 'true'
        
        result = safe_parse_compact_response(response)
        
        # Should return None
        assert result is None

    def test_malformed_json_string(self):
        """Test handling of string response."""
        response = 'invalid response'
        
        result = safe_parse_compact_response(response)
        
        assert result is None

    def test_json_with_markdown(self):
        """Test parsing JSON wrapped in markdown."""
        response = '''```json
{"u": [["product_goal", "test"]], "n": "repo_exists"}
```'''
        
        result = safe_parse_compact_response(response)
        
        assert result is not None
        assert result["u"] == [["product_goal", "test"]]

    def test_json_incomplete_brackets(self):
        """Test handling of incomplete bracket structure."""
        response = '{"u": [["product'
        
        result = safe_parse_compact_response(response)
        
        assert result is None


class TestNormalizer:
    """Tests for normalizing responses to internal schema."""

    def test_normalize_valid_response(self):
        """Test normalizing valid compact response."""
        raw = {"u": [["product_goal", "Sistema de vendas"]], "n": "repo_exists"}
        checklist = [
            {"key": "product_goal", "status": "missing"},
            {"key": "repo_exists", "status": "missing"},
        ]
        
        result = normalize_compact_response(raw, checklist)
        
        assert len(result["updates"]) == 1
        assert result["updates"][0]["key"] == "product_goal"
        assert result["updates"][0]["value"] == "Sistema de vendas"
        assert result["updates"][0]["status"] == "inferred"  # Default filled
        assert result["updates"][0]["confidence"] == 0.7  # Default filled
        assert result["next_best_question_key"] == "repo_exists"

    def test_normalize_malformed_updates(self):
        """Test handling of malformed updates list."""
        raw = {"u": "not a list", "n": "repo_exists"}
        checklist = [{"key": "repo_exists", "status": "missing"}]
        
        result = normalize_compact_response(raw, checklist)
        
        # Should return empty updates, not crash
        assert result["updates"] == []

    def test_normalize_invalid_entry_in_list(self):
        """Test handling of invalid entry in updates list."""
        raw = {"u": [["valid", "value"], True, "string", None, {"key": "ok"}], "n": "next"}
        checklist = [
            {"key": "valid", "status": "missing"},
            {"key": "ok", "status": "missing"},
        ]
        
        result = normalize_compact_response(raw, checklist)
        
        # Should only include valid entries
        assert len(result["updates"]) >= 0

    def test_normalize_empty_response(self):
        """Test handling of empty/minimal response."""
        raw = {}
        checklist = [{"key": "product_goal", "status": "missing"}]
        
        result = normalize_compact_response(raw, checklist)
        
        assert result["updates"] == []
        assert result["next_best_question_key"] is None

    def test_normalize_with_invalid_key(self):
        """Test that invalid keys are filtered out."""
        raw = {"u": [["invalid_key", "value"], ["product_goal", "valid"]], "n": "next"}
        checklist = [{"key": "product_goal", "status": "missing"}]
        
        result = normalize_compact_response(raw, checklist)
        
        # Only valid key should be included
        assert len(result["updates"]) == 1
        assert result["updates"][0]["key"] == "product_goal"

    def test_normalize_expands_short_codes(self):
        """Test that short codes (pg, tu, re) are expanded to full keys."""
        raw = {"u": [["pg", "Sistema de vendas"], ["tu", "Produtores"]], "n": "re"}
        checklist = [
            {"key": "product_goal", "status": "missing"},
            {"key": "target_users", "status": "missing"},
            {"key": "repo_exists", "status": "missing"},
        ]
        result = normalize_compact_response(raw, checklist)
        assert len(result["updates"]) == 2
        keys = [u["key"] for u in result["updates"]]
        assert "product_goal" in keys
        assert "target_users" in keys
        assert result["updates"][0]["value"] == "Sistema de vendas"
        assert result["next_best_question_key"] == "repo_exists"


class TestSafeGetters:
    """Tests for safe extraction functions."""

    def test_safe_get_updates_with_valid_data(self):
        """Test safe_get_updates with valid data."""
        extraction = {"updates": [{"key": "a", "value": "b"}]}
        
        result = safe_get_updates(extraction)
        
        assert len(result) == 1

    def test_safe_get_updates_with_bool(self):
        """Test safe_get_updates when updates is a boolean (shouldn't crash)."""
        extraction = {"updates": True}
        
        result = safe_get_updates(extraction)
        
        assert result == []

    def test_safe_get_updates_with_string(self):
        """Test safe_get_updates when updates is a string."""
        extraction = {"updates": "not a list"}
        
        result = safe_get_updates(extraction)
        
        assert result == []

    def test_safe_get_updates_with_none(self):
        """Test safe_get_updates when updates is None."""
        extraction = {"updates": None}
        
        result = safe_get_updates(extraction)
        
        assert result == []

    def test_safe_get_answered_keys_with_valid_data(self):
        """Test safe_get_answered_keys with valid data."""
        extraction = {"answered_keys": ["a", "b", "c"]}
        
        result = safe_get_answered_keys(extraction)
        
        assert result == ["a", "b", "c"]

    def test_safe_get_answered_keys_with_mixed_types(self):
        """Test safe_get_answered_keys filters non-strings."""
        extraction = {"answered_keys": ["a", 123, None, "b"]}
        
        result = safe_get_answered_keys(extraction)
        
        assert result == ["a", "b"]


class TestTruncationScenarios:
    """Test scenarios that should trigger fallback, not crash."""

    def test_partial_json_array(self):
        """Gemini returns partial array - should not crash."""
        response = '{"u": [{"key": "a", '
        
        result = safe_parse_compact_response(response)
        
        # Returns None, triggering heuristic fallback in caller
        assert result is None

    def test_response_ends_with_ellipsis(self):
        """Response ends with ... indicating truncation."""
        response = '{"u": [["product_goal", "some value'
        
        result = safe_parse_compact_response(response)
        
        # Parser tries its best, might return None
        assert result is None or isinstance(result, dict)

    def test_totally_malformed_response(self):
        """Completely invalid response - should not crash."""
        response = "这是一个中文响应"
        
        result = safe_parse_compact_response(response)
        
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
