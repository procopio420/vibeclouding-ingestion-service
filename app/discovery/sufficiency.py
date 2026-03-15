"""Hybrid answer sufficiency evaluation: heuristics first, AI when inconclusive.

Output: sufficient | partial | ambiguous | not_answered.
Only advance discovery when the answer is at least sufficient for the current intent.
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Sentinel for "heuristics inconclusive, need AI"
NEED_AI = "need_ai"

# Outcomes
SUFFICIENT = "sufficient"
PARTIAL = "partial"
AMBIGUOUS = "ambiguous"
NOT_ANSWERED = "not_answered"

# --- Ambiguous phrases (PT-BR + EN): do not treat as resolved ---
AMBIGUOUS_PHRASES = [
    r"\bn[aã]o\s+sei\b",
    r"\btalvez\b",
    r"\bacho\s+que\s+sim\b",
    r"\bacho\s+que\s+n[aã]o\b",
    r"\bdepois\s+vejo\b",
    r"\bdepois\s+eu\s+vejo\b",
    r"\btenho\s+mas\s+depois\b",
    r"\bdon'?t\s+know\b",
    r"\bmaybe\b",
    r"\bnot\s+sure\b",
    r"\bkind\s+of\b",
    r"\bsei\s+l[aá]\b",
]

# --- Vague / generic (per intent or global) ---
VAGUE_PRODUCT = [
    r"\b[eé]\s+um\s+sistema\b",
    r"\balgo\s+pra\s+ajudar\b",
    r"\balgo\s+para\s+ajudar\b",
    r"\bquero\s+algo\s+bom\b",
    r"\b[eé]\s+um\s+app\b",
    r"\b[eé]\s+uma\s+aplica[cç][aã]o\b",
]
VAGUE_TARGET_USERS = [
    r"\btodo\s+mundo\b",
    r"\bquem\s+precisar\b",
    r"\bqualquer\s+um\b",
]
VAGUE_CORE_COMPONENTS = [
    r"\bo\s+que\s+voc[eê]\s+falou\s+j[aá]\s+t[aá]\s+bom\b",
    r"\bt[aá]\s+bom\s+assim\b",
    r"\bj[aá]\s+est[aá]\s+bom\b",
]

# --- Explicit no (repo) ---
REPO_NO_PATTERNS = [
    r"\bn[aã]o\b",
    r"\bnao\b",
    r"\bainda\s+n[aã]o\b",
    r"\bnot\s+yet\b",
    r"\bdon'?t\s+have\b",
    r"\bn[aã]o\s+tenho\b",
]
# --- Explicit yes without URL (repo) ---
REPO_YES_PATTERNS = [
    r"\bsim\b",
    r"\btenho\b",
    r"\btemos\b",
    r"\byes\b",
    r"\byeah\b",
]
# --- URL patterns (same as chat_service) ---
GITHUB_URL_PATTERNS = [
    r'https?://github\.com/[\w.-]+/[\w.-]+(?:\.git)?',
    r'https?://gitlab\.com/[\w.-]+/[\w.-]+(?:\.git)?',
    r'git@github\.com:[\w.-]+/[\w.-]+\.git',
]


def _match_any(text: str, patterns: List[str]) -> bool:
    t = (text or "").strip().lower()
    for p in patterns:
        if re.search(p, t, re.IGNORECASE):
            return True
    return False


def _detect_repo_url(message: str) -> Optional[str]:
    for pattern in GITHUB_URL_PATTERNS:
        match = re.search(pattern, message or "", re.IGNORECASE)
        if match:
            url = match.group(0)
            if url.endswith(".git"):
                return url[:-4]
            return url
    return None


def evaluate_heuristic(
    intent_key: str,
    user_message: str,
    repo_url: Optional[str] = None,
    extraction: Optional[Dict[str, Any]] = None,
) -> str:
    """First pass: heuristics only. Returns outcome or NEED_AI if inconclusive."""
    msg = (user_message or "").strip()
    if not msg:
        return NOT_ANSWERED

    # project_name: optional and non-blocking — always sufficient so we never get stuck (before ambiguous)
    if intent_key == "project_name":
        return SUFFICIENT

    # Global ambiguous → never sufficient
    if _match_any(msg, AMBIGUOUS_PHRASES):
        return AMBIGUOUS

    if intent_key == "repo_exists":
        if repo_url:
            return SUFFICIENT
        if _match_any(msg, REPO_NO_PATTERNS):
            return SUFFICIENT  # explicit no repo yet
        if _match_any(msg, REPO_YES_PATTERNS):
            return PARTIAL  # said yes but no URL
        return NEED_AI

    if intent_key == "product_goal":
        if _match_any(msg, VAGUE_PRODUCT):
            return PARTIAL
        if len(msg) < 20:
            return NEED_AI
        return NEED_AI

    if intent_key == "target_users":
        if _match_any(msg, VAGUE_TARGET_USERS):
            return PARTIAL
        return NEED_AI

    if intent_key == "core_components":
        if _match_any(msg, VAGUE_CORE_COMPONENTS):
            return NOT_ANSWERED
        return NEED_AI

    if intent_key == "entry_channels":
        return NEED_AI

    # Default: let AI decide
    return NEED_AI


def evaluate_with_ai(
    intent_key: str,
    user_message: str,
    extraction: Optional[Dict[str, Any]] = None,
) -> str:
    """Call LLM to classify when heuristics returned NEED_AI. Fallback: not_answered."""
    try:
        from app.repo_analysis.llm_enrichment import get_llm_analyzer
        analyzer = get_llm_analyzer()
        if not analyzer.is_available() or getattr(analyzer, "__class__", None).__name__ == "NoOpAnalyzer":
            logger.debug("[Sufficiency] LLM not available, treating as not_answered")
            return NOT_ANSWERED
        intent_question = {
            "repo_exists": "Does the user clearly confirm they have a repo (with URL) or clearly say they don't have one yet?",
            "product_goal": "Does the user describe what the project does or what problem it solves in a concrete way?",
            "target_users": "Does the user identify who will use the system in practice?",
            "entry_channels": "Does the user indicate how people will access the system (mobile, web, WhatsApp, etc.)?",
            "core_components": "Does the user name or confirm essential functional areas of the system?",
        }.get(intent_key, "Is the user's answer concrete and sufficient for this topic?")
        prompt = f"""You are evaluating a discovery chat answer. Current topic (intent): {intent_key}.
User message: "{user_message[:500]}"
Question: {intent_question}
Respond with exactly one word: sufficient, partial, ambiguous, or not_answered.
No explanation, only that word."""
        response = (analyzer.generate_chat_response(prompt) or "").strip().lower()
        for out in (SUFFICIENT, PARTIAL, AMBIGUOUS, NOT_ANSWERED):
            if out in response:
                return out
        return NOT_ANSWERED
    except Exception as e:
        logger.warning(f"[Sufficiency] AI evaluation failed: {e}, treating as not_answered")
        return NOT_ANSWERED


def evaluate(
    intent_key: str,
    user_message: str,
    repo_url: Optional[str] = None,
    extraction: Optional[Dict[str, Any]] = None,
) -> str:
    """Hybrid: heuristics first, then AI when inconclusive. Returns sufficient | partial | ambiguous | not_answered."""
    h = evaluate_heuristic(intent_key, user_message, repo_url=repo_url, extraction=extraction)
    if h != NEED_AI:
        return h
    return evaluate_with_ai(intent_key, user_message, extraction=extraction)


def is_sufficient(outcome: str) -> bool:
    return outcome == SUFFICIENT
