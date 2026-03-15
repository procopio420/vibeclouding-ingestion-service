"""LLM-powered structured answer extractor for discovery phase."""
import json
import logging
import re
from typing import Dict, Any, List, Optional

from app.discovery.question_intents import QUESTION_INTENTS

logger = logging.getLogger(__name__)


class AnswerExtractor:
    """Extract structured updates from a user message using Gemini.

    This extractor uses Gemini for intelligent extraction when available,
    with a robust heuristic fallback for offline/unavailable scenarios.
    """

    def extract(
        self, 
        user_message: str, 
        checklist: List[Dict[str, Any]], 
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Extract structured updates from user message.
        
        Tries Gemini first, falls back to heuristic matching.
        
        Returns:
            {
                "updates": [{"key", "status", "value", "confidence", "evidence"}, ...],
                "answered_keys": [...],
                "conflicts": [...],
                "remaining_gaps": [...],
                "next_best_question_key": ...
            }
        """
        # First try Gemini-based extraction
        try:
            result = self._extract_with_gemini(user_message, checklist, conversation_history)
            if result and result.get("updates"):
                logger.info(f"[AnswerExtractor] Gemini extracted {len(result['updates'])} updates")
                return result
        except Exception as e:
            logger.warning(f"[AnswerExtractor] Gemini extraction failed: {e}")
        
        # Fallback to heuristic extraction
        logger.info("[AnswerExtractor] Using heuristic fallback")
        return self._extract_with_heuristics(user_message, checklist)

    def _extract_with_gemini(
        self, 
        user_message: str, 
        checklist: List[Dict[str, Any]], 
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Extract using Gemini LLM."""
        try:
            from app.repo_analysis.llm_enrichment import get_llm_analyzer
            analyzer = get_llm_analyzer()
            
            if not analyzer.is_available() or analyzer.__class__.__name__ == "NoOpAnalyzer":
                return None
            
            # Build checklist summary for prompt
            checklist_summary = []
            for item in checklist:
                if item.get("status") == "missing":
                    checklist_summary.append(f"- {item.get('key')}: {item.get('label', '')}")
            
            if not checklist_summary:
                return {"updates": [], "answered_keys": [], "conflicts": [], "remaining_gaps": [], "next_best_question_key": None}
            
            checklist_text = "\n".join(checklist_summary)
            
            prompt = f"""Você é um extrator estruturado de respostas para uma conversa de descoberta de software.

IMPORTANTE: Responda SEMPRE em português brasileiro (pt-BR) para as instruções e contexto.

CURRENT CHECKLIST (itens ainda faltando):
{checklist_text}

MENSAGEM DO USUÁRIO:
"{user_message}"

Sua tarefa é extrair quais itens do checklist foram abordados pela mensagem do usuário.

Para cada item que o usuário forneceu informação, responda com JSON:
{{
  "updates": [
    {{
      "key": "checklist_key",
      "status": "confirmed" ou "inferred",
      "value": "resposta completa do usuário sobre este tópico (1-2 frases)",
      "confidence": 0.0-1.0,
      "evidence": "citação breve ou contexto da mensagem do usuário"
    }}
  ]
}}

Regras:
- status "confirmed" = usuário mencionou explicitamente este tópico
- status "inferred" = usuário暗示ou este tópico sem mencionar explicitamente
- Extraia project_name SOMENTE se o usuário nomeou explicitamente seu projeto (ex: "é chamado de X", "nome do projeto é X")
- NÃO infira project_name de descrições de produto como "software de gestão..."
- NÃO infira repo_exists de texto vago - apenas quando o usuário confirmar explicitamente ou fornecer URL
- Inclua apenas itens que foram realmente abordados na mensagem do usuário
- Se nada foi abordado, retorne array updates vazia
- Seja específico no value - capture o que o usuário realmente disse
- confidence: 0.9+ para menções explícitas, 0.6-0.8 para inferências fortes, 0.3-0.5 para inferências fracas

Responda ONLY com JSON válido, sem explicação."""

            response = analyzer.generate_chat_response(prompt)
            
            if not response:
                return None
            
            # Parse JSON from response
            try:
                response = response.strip()
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0]
                
                result = json.loads(response.strip())
                
                if not isinstance(result, dict):
                    return None
                    
                updates = result.get("updates", [])
                answered_keys = [u.get("key") for u in updates if u.get("key")]
                
                return {
                    "updates": updates,
                    "answered_keys": answered_keys,
                    "conflicts": [],
                    "remaining_gaps": [k for k in checklist if k.get("status") == "missing" and k.get("key") not in answered_keys],
                    "next_best_question_key": answered_keys[0] if answered_keys else None,
                }
                
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"[AnswerExtractor] Failed to parse Gemini response: {e}")
                return None
                
        except Exception as e:
            logger.warning(f"[AnswerExtractor] Gemini extraction error: {e}")
            return None

    def _extract_with_heuristics(
        self, 
        user_message: str, 
        checklist: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Heuristic-based extraction as fallback.
        
        Uses keyword patterns to detect which checklist items were addressed.
        """
        text = (user_message or "").strip().lower()
        original_text = user_message or ""
        
        updates = []
        answered_keys = []
        
        # Check for explicit project name FIRST (before generic patterns)
        # ONLY extract if explicitly named
        project_name_patterns = [
            r"(?:it's|called|name is|project name is|o projeto se chama|chama-se|nome do projeto)[:\s]+([A-Za-z][A-Za-z0-9\s]{2,30})",
            r"^([A-Z][a-zA-Z0-9\s]{2,30})$",  # Single capitalized word at start
        ]
        
        for pattern in project_name_patterns:
            match = re.search(pattern, original_text, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()
                # Verify it's NOT a generic description
                generic_terms = ["software", "sistema", "gestão", "management", "app", "application", "plataforma"]
                if not any(term in potential_name.lower() for term in generic_terms):
                    updates.append({
                        "key": "project_name",
                        "status": "confirmed",
                        "value": potential_name,
                        "confidence": 0.9,
                        "evidence": f"explicit name: {potential_name}"
                    })
                    answered_keys.append("project_name")
                    break
        
        # Check for repo URL first (before generic patterns)
        repo_url_patterns = [
            r'https?://github\.com/[\w-]+/[\w.-]+(?:\.git)?',
            r'https?://gitlab\.com/[\w-]+/[\w.-]+(?:\.git)?',
            r'https?://bitbucket\.org/[\w-]+/[\w.-]+(?:\.git)?',
            r'git@github\.com:[\w-]+/[\w.-]+\.git',
            r'git@gitlab\.com:[\w-]+/[\w.-]+\.git',
        ]
        
        for pattern in repo_url_patterns:
            match = re.search(pattern, original_text, re.IGNORECASE)
            if match:
                url = match.group(0)
                if url.endswith('.git'):
                    url = url[:-4]
                updates.append({
                    "key": "repo_exists",
                    "status": "confirmed",
                    "value": url,
                    "confidence": 0.95,
                    "evidence": "repo URL detected"
                })
                answered_keys.append("repo_exists")
                break
        
        # Check for explicit yes/no to repo question
        # This only triggers if NOT already detected a URL
        if "repo_exists" not in answered_keys:
            yes_patterns = [r'\byes\b', r'\byeah\b', r'\byep\b', r'\bsure\b', r'\bsim\b', r'\btenho\b', r'\btemos\b']
            no_patterns = [r'\bno\b', r'\bnope\b', r'\bnão\b', r'\bnao\b', r'\bnot yet\b', r'\bainda não\b', r"\bdon'?t have\b"]
            
            for pattern in yes_patterns:
                if re.search(pattern, text):
                    updates.append({
                        "key": "repo_exists",
                        "status": "confirmed",
                        "value": "user confirmed they have a repo",
                        "confidence": 0.8,
                        "evidence": "explicit yes response"
                    })
                    answered_keys.append("repo_exists")
                    break
            
            if "repo_exists" not in answered_keys:
                for pattern in no_patterns:
                    if re.search(pattern, text):
                        updates.append({
                            "key": "repo_exists",
                            "status": "missing",  # Explicit no = confirmed missing
                            "value": "user confirmed no repo yet",
                            "confidence": 0.9,
                            "evidence": "explicit no response"
                        })
                        answered_keys.append("repo_exists")
                        break
        
        # Keyword patterns for each checklist key
        # Format: key -> {confirmed: [...], inferred: [...]}
        patterns = {
            "product_goal": {
                "confirmed": [
                    # English
                    "software", "system", "platform", "application", "manage", "managing",
                    "build", "building", "create", "develop", "making",
                    # Portuguese
                    "software de", "sistema de", "gestão de", "plataforma", 
                    "fazemos", "produzimos", "vendemos", "gestão", "fábrica",
                    "postes", "manilhas", "concreto", "artefatos"
                ],
                "inferred": [
                    "project", "business", "company", "startup", "empresa"
                ],
            },
            "target_users": {
                "confirmed": [
                    # English
                    "customers", "clients", "users", "b2b", "b2c", "employees",
                    "selling to", "sell to", "stores", "businesses", "market",
                    # Portuguese
                    "clientes", "lojas", "empresas", "vendemos para", "para lojas",
                    "b2b", "b2c", "consumidores"
                ],
                "inferred": [
                    "people", "people who", "target"
                ],
            },
            "application_type": {
                "confirmed": [
                    # English
                    "web app", "mobile app", "api", "chatbot", "website", "web application",
                    "mobile application", "saas", "software as a service", "platform",
                    # Portuguese
                    "aplicativo", "app móvil", "app móvel", "sistema", "plataforma",
                    "loja virtual", "e-commerce", "site", "plataforma web"
                ],
                "inferred": [
                    "online", "digital", "computer", "desktop"
                ],
            },
            "entry_channels": {
                "confirmed": [
                    # English
                    "mobile", "cellphone", "smartphone", "whatsapp", "telegram",
                    "browser", "web browser", "website", "login", "access via",
                    "ios", "android", "app store", "play store",
                    # Portuguese
                    "mobile app", "app móvel", "celular", "whatsapp", "navegador",
                    "site", "web", "computador", "relatório", "relatorios"
                ],
                "inferred": [
                    "channel", "access", "through"
                ],
            },
            "core_components": {
                "confirmed": [
                    "components", "features", "modules", "main functions", "main features",
                    "parts", "funções principais", "módulos", "componentes"
                ],
                "inferred": [
                    "functions", "capabilities", "capabilities"
                ],
            },
            "database": {
                "confirmed": [
                    "database", "postgresql", "mysql", "mongodb", "sql", "store data",
                    "persist", "banco de dados", "sql", "mysql", "postgresql"
                ],
                "inferred": [
                    "data storage", "save data"
                ],
            },
            "auth_model": {
                "confirmed": [
                    "login", "log in", "authentication", "password", "oauth",
                    "sign in", "user account", "users need to log", "cadastro",
                    "autenticação", "login", "senha"
                ],
                "inferred": [
                    "require login", "must log in"
                ],
            },
            "external_integrations": {
                "confirmed": [
                    "integrations", "api integration", "whatsapp", "payment", "stripe",
                    "email", "maps", "integration", "integração", "whatsapp"
                ],
                "inferred": [
                    "connect to", "integrate with", "external"
                ],
            },
            "file_storage": {
                "confirmed": [
                    "file storage", "images", "documents", "upload", "s3", "storage",
                    "arquivos", "imagens", "upload", "armazenamento"
                ],
                "inferred": [
                    "store files", "upload files"
                ],
            },
            "traffic_expectation": {
                "confirmed": [
                    "users", "traffic", "scale", "scalability", "million", "thousand",
                    "many users", "high traffic", "users initially"
                ],
                "inferred": [
                    "grow", "growth"
                ],
            },
            "cost_priority": {
                "confirmed": [
                    "cost", "cheap", "expensive", "budget", "low cost", "high cost",
                    "custo", "preço", "barato", "orçamento"
                ],
                "inferred": [
                    "price", "affordable"
                ],
            },
        }
        
        for item in checklist:
            if item.get("status") != "missing":
                continue
                
            key = item.get("key")
            if not key:
                continue
            
            # Skip keys we've already handled
            if key in answered_keys:
                continue
            
            if key in patterns:
                pattern = patterns[key]
                
                # Check confirmed keywords first
                for kw in pattern.get("confirmed", []):
                    if kw.lower() in text:
                        updates.append({
                            "key": key,
                            "status": "confirmed",
                            "value": original_text[:300],
                            "confidence": 0.85,
                            "evidence": f"keyword: {kw}"
                        })
                        answered_keys.append(key)
                        break
                else:
                    # Check inferred keywords
                    for kw in pattern.get("inferred", []):
                        if kw.lower() in text:
                            updates.append({
                                "key": key,
                                "status": "inferred",
                                "value": original_text[:300],
                                "confidence": 0.6,
                                "evidence": f"inferred keyword: {kw}"
                            })
                            answered_keys.append(key)
                            break
        
        remaining_gaps = [
            k.get("key") for k in checklist 
            if k.get("status") == "missing" and k.get("key") not in answered_keys
        ]
        
        return {
            "updates": updates,
            "answered_keys": answered_keys,
            "conflicts": [],
            "remaining_gaps": remaining_gaps,
            "next_best_question_key": answered_keys[0] if answered_keys else (remaining_gaps[0] if remaining_gaps else None),
        }


__all__ = ["AnswerExtractor"]
