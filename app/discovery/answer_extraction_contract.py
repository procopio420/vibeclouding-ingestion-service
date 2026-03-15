"""Compact JSON contract for discovery extraction.

Minimizes token usage for free-tier Gemini models.
Uses short codes for field names to reduce output tokens.

Contract format:
{
    "u": [["code", "value"], ...],
    "n": "code"
}

Where:
- u = updates (list of [short_code, value] pairs)
- n = next best intent (short code)
"""

from typing import Dict, List, Any


COMPACT_KEY_U = "u"
COMPACT_KEY_N = "n"

# Short codes for discovery keys (reduces LLM output tokens)
KEY_TO_SHORT: Dict[str, str] = {
    "application_type": "at",
    "target_users": "tu",
    "product_goal": "pg",
    "repo_exists": "re",
    "entry_channels": "ec",
    "core_components": "cc",
    "database": "db",
    "auth_model": "am",
    "external_integrations": "ei",
    "file_storage": "fs",
    "cache_or_queue": "cq",
    "background_processing": "bp",
    "traffic_expectation": "te",
    "availability_requirement": "ar",
    "cost_priority": "cp",
    "compliance_or_sensitive_data": "cs",
    "project_name": "pn",
}
SHORT_TO_KEY: Dict[str, str] = {v: k for k, v in KEY_TO_SHORT.items()}


def build_compact_prompt(checklist_items: List[Dict[str, Any]], user_message: str) -> str:
    """Build a minimal prompt for Gemini extraction.
    Uses short codes for keys to minimize output tokens.
    """
    missing_keys = [item.get("key", "") for item in checklist_items if item.get("status") == "missing"]
    codes_str = ", ".join(f"{KEY_TO_SHORT.get(k, k)}={k}" for k in missing_keys[:10])

    prompt = f"""Extrator minimalista. Use APENAS os códigos curtos nas chaves.

Mensagem: "{user_message}"

Responda só JSON válido, sem markdown:
{{"u": [["codigo", "valor"], ...], "n": "codigo"}}

Códigos disponíveis: {codes_str}

Regras:
- u: lista de [código, valor] do que o usuário disse
- n: próxima pergunta (um dos códigos acima)
- Use só os códigos (pg, tu, re, at, ec, cc, db, etc), não o nome completo
- Se não detectou nada: "u": []
- valor: resumo curto

Exemplo: {{"u": [["pg", "Sistema para vendas"], ["tu", "Produtores"]], "n": "re"}}"""

    return prompt


def build_compact_prompt_for_chat(
    checklist_items: List[Dict[str, Any]], 
    user_message: str,
    next_key: str = None
) -> str:
    """Build prompt for chat response generation with compact format.
    
    Args:
        checklist_items: List of checklist items
        user_message: User's message
        next_key: Optional next key to focus on
    
    Returns:
        Compact prompt string
    """
    answered = [item for item in checklist_items if item.get("status") in ("confirmed", "inferred")]
    answered_summary = ", ".join([item.get("key", "?") for item in answered[:5]])
    
    missing = [item.get("key", "") for item in checklist_items if item.get("status") == "missing"]
    missing_str = ", ".join(missing[:5])
    
    next_focus = f", pergunte sobre: {next_key}" if next_key else ""
    
    prompt = f"""Assistente de descoberta em português brasileiro.

Contexto: {answered_summary}
Pendentes: {missing_str}{next_focus}

Usuário: "{user_message}"

Resposta (2-3 frases, conversacional):"""

    return prompt


__all__ = [
    "COMPACT_KEY_U",
    "COMPACT_KEY_N",
    "KEY_TO_SHORT",
    "SHORT_TO_KEY",
    "build_compact_prompt",
    "build_compact_prompt_for_chat",
]
