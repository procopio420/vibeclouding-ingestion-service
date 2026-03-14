"""LLM-powered structured answer extractor for discovery phase."""
import json
import logging
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
                "updates": [{"key", "status", "value_summary", "confidence", "evidence"}, ...],
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
            
            prompt = f"""You are a structured answer extractor for a software discovery conversation.

CURRENT CHECKLIST (items still missing):
{checklist_text}

USER'S MESSAGE:
"{user_message}"

Your task is to extract which checklist items were addressed by the user's message.

For each item the user provided information about, respond with JSON:
{{
  "updates": [
    {{
      "key": "checklist_key",
      "status": "confirmed" or "inferred",
      "value_summary": "1-2 sentence summary of what user said about this topic",
      "confidence": 0.0-1.0,
      "evidence": "direct quote or brief context from user message"
    }}
  ]
}}

Rules:
- status "confirmed" = user explicitly mentioned this topic
- status "inferred" = user implied this topic without explicitly mentioning it
- Only include items that were actually addressed in the user's message
- If nothing was addressed, return empty updates array
- Be specific in value_summary - capture what the user actually said
- confidence: 0.9+ for explicit mentions, 0.6-0.8 for strong inferences, 0.3-0.5 for weak inferences

Respond ONLY with valid JSON, no explanation."""

            response = analyzer.generate_chat_response(prompt)
            
            if not response:
                return None
            
            # Parse JSON from response
            try:
                # Try to extract JSON from response
                response = response.strip()
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0]
                
                result = json.loads(response.strip())
                
                # Validate structure
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
        
        # Keyword patterns for each checklist key
        # Format: key -> (keywords_for_confirmed, keywords_for_inferred, status_if_found)
        patterns = {
            "repo_exists": {
                "confirmed": ["github.com", "gitlab.com", "bitbucket", "repository", "repo url", "git repo"],
                "inferred": ["repo", "repository", "github", "gitlab", "bitbucket"],
            },
            "product_goal": {
                "confirmed": ["software", "system", "platform", "application", "app for", "manage", "manageing", " gestão ", "sistema de", "software de"],
                "inferred": ["build", "building", "create", "develop", "make", "we make", "we build", "we sell", "selling"],
            },
            "target_users": {
                "confirmed": ["users", "customers", "clients", "b2b", "b2c", "employees", "sell to", "selling to", "target audience"],
                "inferred": ["people", "stores", "companies", "business", "market"],
            },
            "application_type": {
                "confirmed": ["web app", "mobile app", "api", "chatbot", "website", "web application", "mobile application"],
                "inferred": ["web", "mobile", "online", "digital"],
            },
            "entry_channels": {
                "confirmed": ["web", "mobile", "whatsapp", "telegram", "api", "website", "login", "access via"],
                "inferred": ["access", "channel", "through"],
            },
            "core_components": {
                "confirmed": ["components", "features", "modules", "main functions", "main features"],
                "inferred": ["parts", "functions", "capabilities"],
            },
            "database": {
                "confirmed": ["database", "postgresql", "mysql", "mongodb", "sql", "store data", "persist"],
                "inferred": ["data storage", "save data"],
            },
            "auth_model": {
                "confirmed": ["login", "log in", "authentication", "password", "oauth", "sign in", "user account"],
                "inferred": ["users need to", "require login", "must log"],
            },
            "external_integrations": {
                "confirmed": ["integrations", "api integration", "whatsapp", "payment", "stripe", "email", "maps"],
                "inferred": ["connect to", "integrate with", "external"],
            },
            "file_storage": {
                "confirmed": ["file storage", "images", "documents", "upload", "s3", "storage"],
                "inferred": ["store files", "upload files"],
            },
            "traffic_expectation": {
                "confirmed": ["users", "traffic", "scale", "scalability", "million", "thousand"],
                "inferred": ["grow", "growh", "many users"],
            },
            "cost_priority": {
                "confirmed": ["cost", "cheap", "expensive", "budget", "low cost", "high cost"],
                "inferred": ["price", "affordable"],
            },
        }
        
        for item in checklist:
            if item.get("status") != "missing":
                continue
                
            key = item.get("key")
            if not key:
                continue
            
            # Check for repo URL pattern (special case)
            if "github.com" in text or "gitlab.com" in text or "bitbucket.org" in text:
                if key == "repo_exists":
                    updates.append({
                        "key": key,
                        "status": "confirmed",
                        "value_summary": "Repository URL detected in message",
                        "confidence": 0.95,
                        "evidence": "URL pattern found"
                    })
                    answered_keys.append(key)
                    continue
            
            # Check patterns
            if key in patterns:
                pattern = patterns[key]
                
                # Check confirmed keywords first
                for kw in pattern.get("confirmed", []):
                    if kw.lower() in text:
                        updates.append({
                            "key": key,
                            "status": "confirmed",
                            "value_summary": original_text[:150],
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
                                "value_summary": original_text[:150],
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
