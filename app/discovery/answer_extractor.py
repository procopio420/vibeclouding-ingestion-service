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
            
            # Simplified prompt - less complex to reduce JSON errors
            prompt = f"""Extrator de respostas para descoberta de software.

Responda APENAS com JSON válido.

Checklist: {checklist_text}

Mensagem: "{user_message}"

Resposta:
{{
  "updates": [
    {{"key": "...", "status": "confirmed|inferred", "value": "...", "confidence": 0.0, "evidence": "..."}}
  ]
}}

Regras:
- confirmed: mencionou explicitamente
- inferred:暗示ou
- Só extraia se o usuário abordar o tema
- confidence: 0.9+ explícito, 0.6-0.8 inferência
- JSON apenas, sem texto adicional."""

            response = analyzer.generate_chat_response(prompt)
            
            if not response:
                return None
            
            # Robust JSON parsing with multiple fallbacks
            result = self._parse_json_response(response, checklist)
            if result:
                return result
            
            # If all parsing fails, return None to trigger heuristic fallback
            logger.warning("[AnswerExtractor] Gemini parsing failed, using heuristic fallback")
            return None
        
        except Exception as e:
            logger.warning(f"[AnswerExtractor] Gemini extraction error: {e}")
            return None

    def _parse_json_response(self, response: str, checklist: List[Dict]) -> Optional[Dict[str, Any]]:
        """Parse JSON from Gemini response with robust fallbacks."""
        import re
        
        # Try 1: Direct parse
        try:
            result = json.loads(response.strip())
            if isinstance(result, dict) and "updates" in result:
                return self._normalize_extraction_result(result, checklist)
        except json.JSONDecodeError:
            pass
        
        # Try 2: Extract from ```json blocks
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            result = json.loads(response.strip())
            if isinstance(result, dict) and "updates" in result:
                return self._normalize_extraction_result(result, checklist)
        except (json.JSONDecodeError, IndexError):
            pass
        
        # Try 3: Extract JSON object using regex
        try:
            json_match = re.search(r'\{[^{}]*"updates"[^{}]*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                if isinstance(result, dict) and "updates" in result:
                    return self._normalize_extraction_result(result, checklist)
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # Try 4: Find first { and last } and try to parse
        try:
            start = response.find('{')
            end = response.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = response[start:end+1]
                result = json.loads(json_str)
                if isinstance(result, dict) and "updates" in result:
                    return self._normalize_extraction_result(result, checklist)
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # All attempts failed
        return None
    
    def _normalize_extraction_result(self, result: Dict, checklist: List[Dict]) -> Dict[str, Any]:
        """Normalize extraction result to standard format."""
        updates = result.get("updates", [])
        answered_keys = [u.get("key") for u in updates if u.get("key")]
        
        return {
            "updates": updates,
            "answered_keys": answered_keys,
            "conflicts": [],
            "remaining_gaps": [k.get("key") for k in checklist if k.get("status") == "missing" and k.get("key") not in answered_keys],
            "next_best_question_key": answered_keys[0] if answered_keys else None,
        }

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
                    # Portuguese - extended
                    "software de", "sistema de", "gestão de", "plataforma", 
                    "fazemos", "produzimos", "vendemos", "gestão", "fábrica",
                    "postes", "manilhas", "concreto", "artefatos",
                    "é um", "são", "gostaria de criar", "preciso de", "precisamos de",
                    "para gerenciar", "para controlar", "para automatizar",
                    "sistema interno", "sistema para", "plataforma para",
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
                    # Portuguese - extended
                    "clientes", "lojas", "empresas", "vendemos para", "para lojas",
                    "b2b", "b2c", "consumidores",
                    "para empresa", "para clientes", "para funcionários", "nossos clientes",
                    "vendido para", "卖给", "funcionários", "colaboradores",
                    "usuários usam", "usuários utilizam", "pessoas usam",
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
                    # Portuguese - extended
                    "aplicativo", "app móvil", "app móvel", "sistema", "plataforma",
                    "loja virtual", "e-commerce", "site", "plataforma web",
                    "sistema interno", "sistema web", "sistema mobile",
                    "plataforma online", "app web", "aplicação web",
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
                    # Portuguese - extended
                    "mobile app", "app móvel", "celular", "whatsapp", "navegador",
                    "site", "web", "computador", "relatório", "relatorios",
                    "pelos funcionários", "pelos usuários", "acesso via",
                    "utilizado por", "via mobile", "via web",
                    "computador para relatório", "mobile no dia a dia",
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
