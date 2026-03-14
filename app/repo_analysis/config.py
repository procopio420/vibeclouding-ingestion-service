"""Configuration for repo analysis pipeline."""
import os

ANALYSIS_MODE = os.environ.get("ANALYSIS_MODE", "local_only")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "none")

ANALYSIS_MODES = ["local_only", "local_plus_llm"]
LLM_PROVIDERS = ["none", "gemini", "openai"]


def get_analysis_config() -> dict:
    """Get current analysis configuration."""
    return {
        "mode": ANALYSIS_MODE,
        "llm_provider": LLM_PROVIDER,
        "llm_available": LLM_PROVIDER != "none" and ANALYSIS_MODE == "local_plus_llm",
    }
