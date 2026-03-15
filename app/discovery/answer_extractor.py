"""LLM-powered structured answer extractor for discovery phase."""
import json
import logging
import re
from typing import Dict, Any, List, Optional

from app.discovery.question_intents import QUESTION_INTENTS
from app.discovery.answer_extraction_contract import build_compact_prompt
from app.discovery.answer_extraction_parser import (
    safe_parse_compact_response, 
    normalize_compact_response,
)

logger = logging.getLogger(__name__)


class _Heuristics:
    """Heuristic extraction methods."""
    
    @staticmethod
    def extract_with_heuristics(
        user_message: str, 
        checklist: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Heuristic-based extraction as fallback."""
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
                if potential_name.lower() not in generic_terms and len(potential_name) > 2:
                    updates.append({
                        "key": "project_name",
                        "status": "confirmed",
                        "value": potential_name,
                        "confidence": 0.9,
                        "evidence": f"explicit name: {potential_name}"
                    })
                    answered_keys.append("project_name")
                    break
        
        # Check for repo URL
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
        if "repo_exists" not in answered_keys:
            yes_patterns = [r'\byes\b', r'\byeah\b', r'\byep\b', r'\bsure\b', r'\bsim\b', r'\btenho\b', r'\btemos\b']
            no_patterns = [r'\bno\b', r'\bnope\b', r'\bnão\b', r'\bnao\b', r'\bnot yet\b', r'\bainda não\b', r"\bdon'?t have\b"]
            for p in yes_patterns:
                if re.search(p, text):
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
                for p in no_patterns:
                    if re.search(p, text):
                        updates.append({
                            "key": "repo_exists",
                            "status": "missing",
                            "value": "user confirmed no repo yet",
                            "confidence": 0.9,
                            "evidence": "explicit no response"
                        })
                        answered_keys.append("repo_exists")
                        break
        
        # Build keyword -> checklist key mapping
        keyword_mappings = {
            "product_goal": {
                "keywords": ["projeto", "sistema", "software", "app", "plataforma", "desenvolver", "criar", "construir", "ideia", "problema", "resolve", "automatizar", "gestão", "management"],
                "inferred": ["plataforma", "sistema"]
            },
            "target_users": {
                "keywords": ["usuários", "users", "clientes", "pessoas", "profissionais", "empresa", "negócio", "loja", "comerciantes", "produtores", "consumidores", "alvos"],
                "inferred": ["b2b", "b2c"]
            },
            "entry_channels": {
                "keywords": ["celular", "mobile", "app", "navegador", "browser", "web", "whatsapp", "chatbot", "api", "acesso"],
                "inferred": ["mobile-first", "web app"]
            },
            "application_type": {
                "keywords": ["site", "website", "aplicativo", "app", "mobile", "web", "sistema web", "plataforma", "chatbot", "api", "backend"],
                "inferred": ["web app", "pwa"]
            },
            "core_components": {
                "keywords": ["cadastro", "login", "painel", "admin", "dashboard", "pedidos", "produtos", "catálogo", "pagamento", "checkout", "relatórios"],
                "inferred": ["crud", "admin panel"]
            },
            "database": {
                "keywords": ["banco", "database", "postgres", "mysql", "sql", "dados", "armazenar", "persistir"],
                "inferred": ["postgresql"]
            },
            "auth_model": {
                "keywords": ["login", "autenticação", "auth", "senha", "usuário", "conta", "oauth", "jwt", "sessão"],
                "inferred": ["user auth"]
            },
            "external_integrations": {
                "keywords": ["whatsapp", "stripe", "pagamento", "payment", "email", "sendgrid", "api", "integração", "webhook", "zapier"],
                "inferred": ["payment gateway"]
            },
            "file_storage": {
                "keywords": ["arquivo", "imagem", "foto", "upload", "storage", "s3", "armazenamento", "documento", "pdf"],
                "inferred": ["s3", "file upload"]
            },
            "background_processing": {
                "keywords": ["background", "fila", "queue", "worker", "cron", "agendado", "automático", "processamento", "notificação", "email"],
                "inferred": ["async", "queue"]
            },
            "traffic_expectation": {
                "keywords": ["tráfego", "traffic", "usuários", "Users", "escala", "scale", "muitos", "poucos", "grande", "pequeno"],
                "inferred": ["high traffic", "low traffic"]
            },
            "availability_requirement": {
                "keywords": ["disponibilidade", "availability", "uptime", "24/7", "sempre", "fora do ar", "queda"],
                "inferred": ["high availability"]
            },
            "cost_priority": {
                "keywords": ["custo", "cost", "barato", "econômico", "orçamento", "investimento", "caro"],
                "inferred": ["low cost"]
            },
            "compliance_or_sensitive_data": {
                "keywords": ["lgpd", "dados pessoais", "sensível", "cpf", "cnpj", "cartão", "payment", "financeiro", "documento", "privacidade", "criptografia"],
                "inferred": ["pii", "gdpr"]
            },
        }
        
        for key, pattern in keyword_mappings.items():
            keywords = pattern.get("keywords", [])
            inferred = pattern.get("inferred", [])
            
            # Check explicit keywords first
            for kw in keywords:
                if kw.lower() in text:
                    updates.append({
                        "key": key,
                        "status": "inferred",
                        "value": original_text[:300],
                        "confidence": 0.7,
                        "evidence": f"keyword: {kw}"
                    })
                    answered_keys.append(key)
                    break
            else:
                # Check inferred keywords
                for kw in inferred:
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
        """Extract using Gemini LLM with compact contract."""
        try:
            from app.repo_analysis.llm_enrichment import get_llm_analyzer
            from app.discovery.answer_extraction_contract import build_compact_prompt
            from app.discovery.answer_extraction_parser import safe_parse_compact_response, normalize_compact_response
            
            analyzer = get_llm_analyzer()
            
            logger.info(f"[AnswerExtractor] Analyzer class: {analyzer.__class__.__name__}")
            logger.info(f"[AnswerExtractor] Analyzer is_available: {analyzer.is_available()}")
            
            if not analyzer.is_available() or analyzer.__class__.__name__ == "NoOpAnalyzer":
                logger.info("[AnswerExtractor] Analyzer not available, skipping Gemini")
                return None
            
            # Filter to missing items only
            missing_items = [item for item in checklist if item.get("status") == "missing"]
            
            if not missing_items:
                return {"updates": [], "answered_keys": [], "conflicts": [], "remaining_gaps": [], "next_best_question_key": None}
            
            # Use compact prompt
            prompt = build_compact_prompt(missing_items, user_message)
            
            logger.info(f"[AnswerExtractor] Calling Gemini with compact prompt, length: {len(prompt)}")
            response = analyzer.generate_chat_response(prompt)
            logger.info(f"[AnswerExtractor] Gemini response length: {len(response) if response else 0} chars")
            logger.info(f"[AnswerExtractor] Gemini response preview: {response[:200] if response else 'EMPTY'}...")
            
            if not response:
                logger.warning("[AnswerExtractor] Gemini returned empty response")
                return None
            
            # Use safe parser
            raw = safe_parse_compact_response(response)
            if not raw:
                logger.warning("[AnswerExtractor] Gemini parsing failed, using heuristic fallback")
                logger.warning(f"[AnswerExtractor] Raw response: {response[:300]}")
                return None
            
            # Normalize to internal schema (fills defaults in backend)
            valid_keys = {item.get("key", "") for item in checklist if item.get("key")}
            result = normalize_compact_response(raw, checklist, valid_keys)
            
            if result.get("updates"):
                logger.info(f"[AnswerExtractor] Gemini extracted {len(result['updates'])} updates")
            
            return result
            
        except Exception as e:
            logger.warning(f"[AnswerExtractor] Gemini extraction error: {e}")
            return None

    def _extract_with_heuristics(
        self,
        user_message: str,
        checklist: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Heuristic-based extraction as fallback."""
        return _Heuristics.extract_with_heuristics(user_message, checklist)


__all__ = ["AnswerExtractor"]
