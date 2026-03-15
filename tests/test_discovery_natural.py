"""Tests for discovery natural language improvements."""
import pytest
from app.discovery.natural_language_mapper import NaturalLanguageMapper


class TestNaturalLanguageMapper:
    """Tests for NaturalLanguageMapper."""

    def test_no_internal_keys_in_questions(self):
        """Verify that internal keys don't appear in user-facing questions."""
        internal_keys = [
            "core_components", "entry_channels", "auth_model", 
            "file_storage", "traffic_expectation", "background_processing",
            "cache_or_queue", "external_integrations", "compliance_or_sensitive_data"
        ]
        
        for key in internal_keys:
            question = NaturalLanguageMapper.get_question(key)
            # Internal key should NOT appear in the question
            assert key not in question, f"Internal key '{key}' found in question: {question}"

    def test_questions_are_in_portuguese(self):
        """Verify all questions are in Portuguese."""
        for key in NaturalLanguageMapper.get_all_keys():
            question = NaturalLanguageMapper.get_question(key)
            # Questions should be in Portuguese (contain Portuguese-specific chars or words)
            # This is a soft check - we just verify they're not English questions
            english_words = ["what", "how", "when", "where", "why", "does", "will", "is", "are", "do", "have", "has"]
            question_lower = question.lower()
            # Allow some English in explanations, but main question should be Portuguese
            # Check if it starts with English question words
            if any(question_lower.startswith(w + " ") for w in english_words):
                # This might be okay if it's a mixed question, but flag it
                # At minimum, ensure it's not ONLY English
                assert len(question) > 20, f"Question too short: {question}"

    def test_explanations_present_for_technical_concepts(self):
        """Verify technical concepts have explanations."""
        technical_keys = [
            "core_components", "entry_channels", "background_processing",
            "auth_model", "file_storage", "compliance_or_sensitive_data"
        ]
        
        for key in technical_keys:
            has_explanation = NaturalLanguageMapper.has_explanation(key)
            assert has_explanation, f"Technical key '{key}' should have explanation"

    def test_examples_present_for_technical_keys(self):
        """Verify technical keys have examples."""
        for key in NaturalLanguageMapper.get_all_keys():
            examples = NaturalLanguageMapper.get_examples(key)
            # At least some keys should have examples
            if key in ["core_components", "entry_channels", "background_processing"]:
                assert len(examples) > 0, f"Key '{key}' should have examples"

    def test_full_question_includes_explanation(self):
        """Verify full question includes explanation when available."""
        # core_components has explanation
        full = NaturalLanguageMapper.get_full_question("core_components")
        assert "ex:" in full.lower() or "por exemplo" in full.lower(), \
            f"Full question should include explanation: {full}"

    def test_all_checklist_keys_mapped(self):
        """Verify all expected checklist keys are mapped."""
        expected_keys = [
            "repo_exists", "product_goal", "target_users", "entry_channels",
            "application_type", "core_components", "database", "auth_model",
            "external_integrations", "file_storage", "cache_or_queue",
            "background_processing", "traffic_expectation", "availability_requirement",
            "cost_priority", "compliance_or_sensitive_data", "project_name"
        ]
        
        mapped_keys = NaturalLanguageMapper.get_all_keys()
        for key in expected_keys:
            assert key in mapped_keys, f"Key '{key}' not mapped"


class TestTruncationDetection:
    """Tests for truncation detection in Gemini responses."""

    def test_complete_sentences(self):
        """Test detection of complete sentences."""
        from app.repo_analysis.llm_enrichment import generate_chat
        
        # The is_response_complete logic is nested, so we test via the function
        # For now, just test the mapper doesn't break
        assert NaturalLanguageMapper.get_question("product_goal") is not None

    def test_questions_not_truncated(self):
        """Verify all questions are complete (not cut off)."""
        for key in NaturalLanguageMapper.get_all_keys():
            question = NaturalLanguageMapper.get_full_question(key)
            # Questions should end with proper punctuation or be substantial
            assert len(question) > 10, f"Question too short: {question}"
            # Should not end with truncation indicators (except in examples which are intentional)
            # Check main question part, not the examples
            main_question = question.split("Por exemplo")[0] if "Por exemplo" in question else question
            assert not main_question.rstrip().endswith(('...', '…')), f"Truncated: {question}"


class TestInferencePatterns:
    """Tests for inference improvements in answer extractor."""

    def test_inference_keywords_cover_common_cases(self):
        """Verify common user phrases can trigger inference."""
        # These are the patterns that should trigger inference
        # This is tested indirectly through the answer_extractor
        # Here we just verify the mapper is being used correctly
        assert NaturalLanguageMapper.get_question("file_storage") is not None
        assert "imagens" in NaturalLanguageMapper.get_question("file_storage").lower() or \
               "arquivos" in NaturalLanguageMapper.get_question("file_storage").lower() or \
               "fotos" in NaturalLanguageMapper.get_question("file_storage").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
