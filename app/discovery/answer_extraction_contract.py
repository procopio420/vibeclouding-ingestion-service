"""Compact JSON contract for discovery extraction.

Minimizes token usage for free-tier Gemini models.

Contract format:
{
    "u": [["key1", "value1"], ["key2", "value2"], ...],
    "n": "next_intent_key"
}

Where:
- u = updates (list of [key, value] pairs)
- n = next best intent key to ask about
"""

from typing import Dict, List, Any


COMPACT_KEY_U = "u"
COMPACT_KEY_N = "n"


def build_compact_prompt(checklist_items: List[Dict[str, Any]], user_message: str) -> str:
    """Build a minimal prompt for Gemini extraction.
    
    Args:
        checklist_items: List of checklist items with keys and labels
        user_message: The user's message to extract from
    
    Returns:
        Compact prompt string in Portuguese
    """
    # Build minimal checklist - only keys
    missing_keys = [item.get("key", "") for item in checklist_items if item.get("status") == "missing"]
    keys_str = ", ".join(missing_keys[:8])  # Limit to 8 items to reduce prompt size
    
    prompt = f"""Extrator minimalista.

Responda APENAS com JSON válido, sem markdown, sem explicações.

Mensagem: "{user_message}"

Responda:
{{"u": [["chave", "valor"], ...], "n": "proxima_pergunta"}}

chaves disponíveis: {keys_str}

Regras:
- u: lista de [chave, valor] das informações nuevas
- n: próxima pergunta (uma das chaves disponíveis)
- se não detectou nada, use u vazio: "u": []
- só inclua o que o usuário abordar
- valor: resumo curto do que disse

Exemplo: {{"u": [["product_goal", "Sistema para vendas"], ["target_users", "Produtores"]], "n": "repo_exists"}}"""

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
    "build_compact_prompt",
    "build_compact_prompt_for_chat"
]
