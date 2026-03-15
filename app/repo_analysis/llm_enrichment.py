"""LLM enrichment abstraction for optional context improvement.

Layer D extension — optional LLM enrichment after deterministic extraction.
"""
import os
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from app.repo_analysis.signals_model import ExtractedSignals

logger = logging.getLogger(__name__)

MODEL_CACHE_TTL = 10 * 60  # 10 minutes in seconds

_model_cache = {
    "models": None,
    "cached_at": 0,
}

_dead_models = set()  # Models that returned 404, won't be retried this session


class LLMAnalyzer(ABC):
    """Abstract base class for LLM-based analysis enrichment."""
    
    @abstractmethod
    def analyze(self, signals: ExtractedSignals) -> ExtractedSignals:
        """Analyze and enrich extracted signals with LLM insights."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this LLM provider is available/configured."""
        pass
    
    def generate_chat_response(self, prompt: str) -> str:
        """Generate a chat response using the LLM."""
        return ""


class NoOpAnalyzer(LLMAnalyzer):
    """No-op analyzer for local-only mode (no LLM)."""
    
    def analyze(self, signals: ExtractedSignals) -> ExtractedSignals:
        return signals
    
    def is_available(self) -> bool:
        return True
    
    def generate_chat_response(self, prompt: str) -> str:
        return ""


def list_models(api_key: str) -> List[Dict[str, Any]]:
    """Fetch available models from Gemini API with caching.
    
    Returns only models that support generateContent method.
    """
    global _model_cache
    
    current_time = time.time()
    
    if _model_cache["models"] and (current_time - _model_cache["cached_at"]) < MODEL_CACHE_TTL:
        logger.info(f"Using cached model list (age: {current_time - _model_cache['cached_at']:.0f}s)")
        return _model_cache["models"]
    
    url = "https://generativelanguage.googleapis.com/v1/models"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    
    logger.info(f"Fetching model list from: {url}")
    
    req = Request(url, headers=headers, method='GET')
    
    try:
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
    except HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        logger.error(f"Failed to fetch models: HTTP {e.code} - {error_body}")
        raise Exception(f"Failed to fetch Gemini models: {e.code} - {error_body}")
    except URLError as e:
        logger.error(f"Network error fetching models: {e.reason}")
        raise Exception(f"Network error fetching Gemini models: {e.reason}")
    
    all_models = result.get("models", [])
    
    valid_models = []
    for model in all_models:
        methods = model.get("supportedGenerationMethods", [])
        model_name = model.get("name", "").replace("models/", "")
        
        if "generateContent" in methods:
            valid_models.append({
                "name": model_name,
                "supportedGenerationMethods": methods,
                "description": model.get("description", ""),
                "version": model.get("version", ""),
            })
            logger.debug(f"Model {model_name}: supports {methods}")
        else:
            logger.debug(f"Model {model_name}: NO generateContent support, skipping")
    
    logger.info(f"Discovered {len(valid_models)} models with generateContent support")
    
    _model_cache["models"] = valid_models
    _model_cache["cached_at"] = current_time
    
    return valid_models


def choose_model(models: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Choose the best model from the available list.
    
    Priority:
    1. gemini-2.5-flash (latest stable)
    2. gemini-2.0-flash (stable)
    3. stable flash-lite (if available and not deprecated)
    4. stable pro
    5. preview flash-lite
    6. preview flash
    7. preview pro
    
    Deprecated models (gemini-2.0-flash-lite*) are excluded as they return 404.
    """
    if not models:
        return None
    
    DEPRECATED_PATTERNS = ["gemini-2.0-flash-lite", "gemini-1.5-flash-lite"]
    
    def is_deprecated(model: Dict) -> bool:
        name = model["name"].lower()
        return any(pattern in name for pattern in DEPRECATED_PATTERNS)
    
    def model_priority(model: Dict) -> tuple:
        name = model["name"].lower()
        
        if is_deprecated(model):
            return (100, name)
        
        is_preview = "preview" in name or "latest" in name
        
        if "gemini-2.5-flash" in name:
            return (0, name)
        elif "gemini-2.0-flash" in name and "lite" not in name:
            return (1, name)
        elif "flash-lite" in name and not is_preview:
            return (2, name)
        elif "flash" in name and not is_preview:
            return (3, name)
        elif "pro" in name and not is_preview:
            return (4, name)
        elif "flash-lite" in name:
            return (5, name)
        elif "flash" in name:
            return (6, name)
        elif "pro" in name:
            return (7, name)
        else:
            return (10, name)
    
    # Filter out dead models
    alive_models = [m for m in models if m["name"] not in _dead_models]
    
    if not alive_models:
        logger.warning("All discovered models are marked as dead, clearing dead model cache")
        _dead_models.clear()
        alive_models = models
    
    alive_models.sort(key=model_priority)
    
    selected = alive_models[0]
    is_preview = "preview" in selected["name"].lower() or "latest" in selected["name"].lower()
    
    logger.info(f"Selected model: {selected['name']}")
    logger.info(f"  - supportedGenerationMethods: {selected['supportedGenerationMethods']}")
    logger.info(f"  - is_preview: {is_preview}")
    
    return selected


def _call_gemini_generate_content(
    api_key: str,
    model: str,
    contents: List[Dict],
    generation_config: Dict = None
) -> Dict[str, Any]:
    """Call Gemini generateContent API.
    
    Returns the full response dict.
    Raises Exception on HTTP errors.
    """
    url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
    
    logger.info(f"Calling Gemini API: {url}")
    
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    
    data = {
        "contents": contents,
    }
    
    if generation_config:
        data["generationConfig"] = generation_config
    
    req = Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    try:
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
    except HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        logger.error(f"Gemini API HTTP {e.code}: {e.reason}")
        logger.error(f"Error response: {error_body}")
        
        error_json = None
        try:
            error_json = json.loads(error_body)
        except:
            pass
        
        # Check for specific error types
        if error_json and error_json.get("error", {}).get("status") == "NOT_FOUND":
            logger.warning(f"Model {model} returned 404 NOT_FOUND, marking as dead")
            _dead_models.add(model)
        
        raise Exception(f"Gemini API error {e.code}: {e.reason} - {error_body}")
    except URLError as e:
        logger.error(f"Gemini API URL error: {e.reason}")
        raise Exception(f"Network error calling Gemini: {e.reason}")
    
    return result


def generate_chat(api_key: str, prompt: str, system_instruction: str = None) -> str:
    """Generate a chat response using dynamic model selection.
    
    This is the main entry point for chat generation.
    """
    logger.info("Starting dynamic model selection for chat")
    logger.debug(f"generate_chat called with prompt length: {len(prompt)} chars")
    
    try:
        models = list_models(api_key)
        logger.debug(f"Discovered {len(models)} models with generateContent support")
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return ""
    
    selected = choose_model(models)
    if not selected:
        logger.error("No valid model found")
        return ""
    
    model_name = selected["name"]
    logger.info(f"Selected model for chat: {model_name}")
    contents = [{"parts": [{"text": prompt}]}]
    
    generation_config = {
        "temperature": 0.7,
    }
    
    def is_response_complete(text: str) -> bool:
        """Check if response appears complete (not truncated)."""
        if not text:
            return False
        text = text.strip()
        # Check for incomplete patterns
        if text.rstrip().endswith(('...', '…', ',', '-', '–')):
            return False
        # Check if ends without proper sentence ending
        end_chars = set('.!?')
        if len(text) > 30 and text[-1] not in end_chars:
            # Allow if it's a short fragment
            if len(text.split()) > 10:
                return False
        return True
    
    try:
        logger.debug(f"Calling Gemini API with model: {model_name}")
        result = _call_gemini_generate_content(
            api_key=api_key,
            model=model_name,
            contents=contents,
            generation_config=generation_config
        )
        
        # Log full response for debugging
        logger.debug(f"Gemini API response: {result}")
        
        # Extract text from response
        if "candidates" not in result or not result["candidates"]:
            logger.error(f"Gemini response has no candidates: {result}")
            return ""
        
        candidate = result["candidates"][0]
        
        # Log finish reason for debugging truncation
        finish_reason = candidate.get("finishReason", "UNKNOWN")
        logger.info(f"Gemini finish reason: {finish_reason}")
        
        # Log token usage if available
        if "usageMetadata" in result:
            usage = result.get("usageMetadata", {})
            logger.info(f"Token usage - prompt: {usage.get('promptTokenCount', '?')}, completion: {usage.get('candidatesTokenCount', '?')}")
        
        if finish_reason == "MAX_TOKENS":
            logger.warning(f"Response truncated due to max tokens for model {model_name}")
        
        if "content" not in candidate:
            logger.error(f"Gemini response has no content: {result}")
            return ""
        
        content = candidate["content"]
        if "parts" not in content or not content["parts"]:
            logger.error(f"Gemini response has no parts: {result}")
            return ""
        
        text = content["parts"][0]["text"]
        logger.info(f"Gemini chat response received: length={len(text)}, preview: {text[:100]}...")
        
        # Check for truncation
        if not is_response_complete(text):
            logger.warning(f"Response may be incomplete/truncated: {text[-100:] if len(text) > 100 else text}")
        
        logger.debug(f"Full Gemini response text: {text}")
        
        return text.strip()
        
    except Exception as e:
        error_str = str(e)
        logger.error(f"generate_chat exception: {error_str}")
        
        if "404" in error_str or "NOT_FOUND" in error_str:
            logger.warning(f"Model {model_name} failed with 404, trying next model...")
            # Try next model
            remaining_models = [m for m in models if m["name"] not in _dead_models and m["name"] != model_name]
            if remaining_models:
                # Update cache to try next model
                _model_cache["models"] = remaining_models
                return generate_chat(api_key, prompt)  # Recursive retry
        
        if "429" in error_str:
            logger.error(f"Rate limited (429) on model {model_name}: {error_str}")
        
        logger.error(f"All models failed: {error_str}")
        return ""


class GeminiAnalyzer(LLMAnalyzer):
    """Gemini-based analyzer with dynamic model selection."""
    
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.api_base_url = "https://generativelanguage.googleapis.com/v1/models"
    
    def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.api_key)
    
    def analyze(self, signals: ExtractedSignals) -> ExtractedSignals:
        """Enrich signals with Gemini insights."""
        if not self.is_available():
            logger.warning("Gemini not available: no API key configured")
            return signals
        
        try:
            models = list_models(self.api_key)
            selected = choose_model(models)
            if not selected:
                logger.warning("No valid model found for enrichment")
                return signals
            
            model_name = selected["name"]
            logger.info(f"Starting Gemini enrichment with model: {model_name}")
            
            payload = self._build_compact_payload(signals)
            prompt = self._build_enrichment_prompt(payload)
            
            result = _call_gemini_generate_content(
                api_key=self.api_key,
                model=model_name,
                contents=[{"parts": [{"text": prompt}]}],
                generation_config={
                    "temperature": 0.3,
                }
            )
            
            return self._apply_enrichment(signals, result)
            
        except Exception as e:
            logger.warning(f"Gemini enrichment failed: {e}")
            return signals
    
    def _build_compact_payload(self, signals: ExtractedSignals) -> Dict[str, Any]:
        """Build a compact payload for the LLM."""
        return {
            "project_name": signals.project_name,
            "project_type": signals.project_type,
            "summary": signals.summary[:500] if signals.summary else "",
            "languages": [l.name for l in signals.languages],
            "frameworks": [f.name for f in signals.frameworks],
            "databases": [d.name for d in signals.databases],
            "infrastructure": [i.name for i in signals.infrastructure],
            "external_services": [e.name for e in signals.external_services],
            "components": [
                {
                    "name": c.name,
                    "type": c.component_type,
                    "tech": c.technologies,
                }
                for c in signals.components
            ],
            "flows": [
                {"source": f.source, "target": f.target, "type": f.flow_type}
                for f in signals.flows
            ],
            "assumptions": signals.assumptions,
            "open_questions": signals.open_questions,
            "uncertainties": signals.uncertainties,
        }
    
    def _build_enrichment_prompt(self, payload: Dict[str, Any]) -> str:
        """Build a compact prompt for enrichment."""
        return f"""You are a software architect analyzing a project. 
Given this extracted project data:

{payload}

Improve the analysis by:
1. Refining the summary if needed
2. Adding any missing obvious components or flows
3. Generating reasonable assumptions about the architecture
4. Listing open questions that need investigation
5. Noting uncertainties

Respond with JSON containing keys: summary, assumptions (array), open_questions (array), uncertainties (array).
Keep it brief - max 50 words per array item.
"""
    
    def _apply_enrichment(self, signals: ExtractedSignals, result: Dict[str, Any]) -> ExtractedSignals:
        """Apply enrichment response to signals."""
        try:
            if "candidates" not in result or not result["candidates"]:
                logger.warning("Gemini enrichment response has no candidates")
                return signals
            
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            response = json.loads(text.strip())
            
            if response.get("summary"):
                signals.summary = response["summary"]
            
            if response.get("assumptions"):
                signals.assumptions.extend(response["assumptions"])
            
            if response.get("open_questions"):
                signals.open_questions.extend(response["open_questions"])
            
            if response.get("uncertainties"):
                signals.uncertainties.extend(response["uncertainties"])
                
        except Exception as e:
            logger.warning(f"Failed to parse enrichment response: {e}")
        
        return signals
    
    def generate_chat_response(self, prompt: str) -> str:
        """Generate a chat response using dynamic model selection."""
        if not self.is_available():
            logger.warning("Gemini not available: no API key configured")
            return ""
        
        return generate_chat(self.api_key, prompt)


def get_llm_analyzer() -> LLMAnalyzer:
    """Factory to get the configured LLM analyzer."""
    mode = os.environ.get("ANALYSIS_MODE", "local_only")
    provider = os.environ.get("LLM_PROVIDER", "none")
    
    logger.info(f"LLM Analyzer factory: mode={mode}, provider={provider}")
    logger.debug(f"Environment variables: ANALYSIS_MODE={mode}, LLM_PROVIDER={provider}")
    logger.debug(f"GEMINI_API_KEY present: {bool(os.environ.get('GEMINI_API_KEY'))}")
    
    if mode == "local_only" or provider == "none":
        logger.info("Using NoOpAnalyzer (local_only mode or no provider)")
        return NoOpAnalyzer()
    
    if provider == "gemini":
        analyzer = GeminiAnalyzer()
        if analyzer.is_available():
            logger.info("Using GeminiAnalyzer with dynamic model selection")
            return analyzer
        else:
            logger.warning("Gemini API key not configured, using NoOpAnalyzer")
            return NoOpAnalyzer()
    
    logger.warning(f"Unknown provider '{provider}', using NoOpAnalyzer")
    return NoOpAnalyzer()
