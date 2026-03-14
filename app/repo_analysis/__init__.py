"""Repo analysis package - deterministic local extraction + optional LLM enrichment.

Architecture:
- Layer A: Raw source (repo URL)
- Layer B: Source-specific extraction (repo_adapter.py)
- Layer C: Source-agnostic ExtractedSignals (signals_model.py)
- Layer D: Canonical ProjectContext (context_normalizer.py)

Usage:
    from app.pipelines.repo_pipeline import extract_repo_signals
    
    context = extract_repo_signals("/path/to/cloned/repo", "https://github.com/...")
    
The pipeline:
1. Clone repo (worker responsibility)
2. Local deterministic extraction via repo_adapter.parse_repo()
3. Optional LLM enrichment (if configured via ANALYSIS_MODE=local_plus_llm)
4. Canonical context normalization

Configuration:
    ANALYSIS_MODE=local_only      # No LLM (default, cheapest)
    ANALYSIS_MODE=local_plus_llm  # Use LLM for enrichment
    
    LLM_PROVIDER=none   # No LLM provider
    LLM_PROVIDER=gemini # Use Gemini (free tier friendly)

Future input types:
    - image: Will produce ExtractedSignals via vision/OCR
    - text: Will produce ExtractedSignals via text parsing
    - audio: Will produce ExtractedSignals via transcription + analysis
"""
from app.repo_analysis.repo_adapter import analyze_repo, parse_repo
from app.repo_analysis.signals_model import ExtractedSignals
from app.repo_analysis.llm_enrichment import get_llm_analyzer, NoOpAnalyzer, GeminiAnalyzer
from app.repo_analysis.config import get_analysis_config, ANALYSIS_MODE, LLM_PROVIDER

__all__ = [
    "analyze_repo",
    "parse_repo", 
    "ExtractedSignals",
    "get_llm_analyzer",
    "NoOpAnalyzer",
    "GeminiAnalyzer",
    "get_analysis_config",
    "ANALYSIS_MODE",
    "LLM_PROVIDER",
]
