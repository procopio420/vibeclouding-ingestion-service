"""Repository ingestion pipeline using hybrid local+LLM analysis.

This module provides the main entry point for repo analysis:
1. Clone repo (handled by worker)
2. Local deterministic extraction (repo_adapter)
3. Optional LLM enrichment (llm_enrichment)
4. Canonical context normalization (context_normalizer)
"""
from typing import Dict, Any

from app.repo_analysis.repo_adapter import analyze_repo
from app.repo_analysis.llm_enrichment import get_llm_analyzer
from app.repo_analysis.signals_model import signals_to_context_dict
from app.repo_analysis.context_normalizer import normalize_signals


def extract_repo_signals(repo_path: str, repo_url: str = "local") -> Dict[str, Any]:
    """Extract signals from a repository using hybrid local+LLM approach.
    
    This is the main entry point for repo analysis.
    
    Flow:
    1. Clone repo (worker responsibility)
    2. Local deterministic extraction via analyze_repo()
    3. Optional LLM enrichment (if configured)
    4. Canonical context normalization
    
    Args:
        repo_path: Path to cloned repository
        repo_url: Original repo URL (for metadata)
    
    Returns:
        Normalized context dict ready for artifact generation
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from app.repo_analysis.repo_adapter import parse_repo
    
    signals = parse_repo(repo_path, repo_url)
    logger.info(f"Parsed signals - project: {signals.project_name}, type: {signals.project_type}, languages: {[l.name for l in signals.languages]}")
    
    analyzer = get_llm_analyzer()
    if analyzer.is_available() and analyzer.__class__.__name__ != "NoOpAnalyzer":
        signals = analyzer.analyze(signals)
        context_dict = signals_to_context_dict(signals)
    else:
        context_dict = signals_to_context_dict(signals)
    
    logger.info(f"Context dict - project_name: {context_dict.get('project_name')}, stack: {context_dict.get('stack')}")
    
    context = normalize_signals([context_dict])
    logger.info(f"Normalized context - project_name: {context.get('project_name')}")
    
    return context


__all__ = ["extract_repo_signals"]
