"""Safe parser and normalizer for discovery extraction responses.

Handles malformed, truncated, and invalid Gemini outputs gracefully.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.discovery.answer_extraction_contract import COMPACT_KEY_U, COMPACT_KEY_N, SHORT_TO_KEY

logger = logging.getLogger(__name__)


def safe_parse_compact_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse Gemini response with multiple fallback strategies.
    
    Handles:
    - Truncated JSON
    - Markdown code blocks
    - Extra whitespace
    - Malformed structures
    
    Args:
        response: Raw Gemini response string
        
    Returns:
        Parsed dict or None if all parsing fails
    """
    if not response or not response.strip():
        logger.warning("[Parser] Empty response received")
        return None
    
    # Strategy 1: Direct parse
    try:
        result = json.loads(response.strip())
        if isinstance(result, dict):
            logger.info("[Parser] Parsed successfully via direct parse")
            return result
    except (json.JSONDecodeError, AttributeError) as e:
        logger.debug(f"[Parser] Direct parse failed: {e}")
    
    # Strategy 2: Extract from markdown code blocks
    try:
        cleaned = response
        if "```json" in response:
            cleaned = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            parts = response.split("```")
            if len(parts) >= 3:
                cleaned = parts[1]
        
        result = json.loads(cleaned.strip())
        if isinstance(result, dict):
            logger.info("[Parser] Parsed successfully via code block extraction")
            return result
    except (json.JSONDecodeError, IndexError, AttributeError) as e:
        logger.debug(f"[Parser] Code block extraction failed: {e}")
    
    # Strategy 3: Find JSON object with regex
    try:
        json_match = re.search(r'\{[^{}]*"u"[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            if isinstance(result, dict):
                logger.info("[Parser] Parsed successfully via regex")
                return result
    except (json.JSONDecodeError, AttributeError) as e:
        logger.debug(f"[Parser] Regex extraction failed: {e}")
    
    # Strategy 4: Find first { and last } and try to parse
    try:
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = response[start:end+1]
            result = json.loads(json_str)
            if isinstance(result, dict):
                logger.info("[Parser] Parsed successfully via bracket matching")
                return result
    except (json.JSONDecodeError, AttributeError) as e:
        logger.debug(f"[Parser] Bracket matching failed: {e}")

    # Strategy 5: Repair truncated-at-end (append missing ] and })
    try:
        text = response.strip()
        if text and text[-1] not in (']', '}', '"'):
            open_square = text.count('[') - text.count(']')
            open_curly = text.count('{') - text.count('}')
            if open_square > 0 or open_curly > 0:
                repaired = text + (']' * open_square) + ('}' * open_curly)
                result = json.loads(repaired)
                if isinstance(result, dict):
                    logger.info("[Parser] Parsed successfully via truncation repair (end)")
                    return result
    except (json.JSONDecodeError, AttributeError) as e:
        logger.debug(f"[Parser] Truncation repair failed: {e}")

    # Strategy 6: Salvage from fragment (extract complete ["k","v"] pairs and "n":"key")
    salvaged = _salvage_compact_from_fragment(response)
    if salvaged is not None:
        logger.info("[Parser] Parsed successfully via fragment salvage")
        return salvaged

    # All strategies failed
    logger.warning(f"[Parser] All parsing strategies failed. Response: {response[:200]}...")
    return None


def _salvage_compact_from_fragment(response: str) -> Optional[Dict[str, Any]]:
    """Extract a minimal compact object from truncated/malformed response.
    Looks for ["key", "value"] or ["short_code", "value"] and "n": "key" or "n": "code".
    """
    if not response or not response.strip():
        return None
    text = response.strip()
    # Find all ["key_or_code", "value"] pairs (value may contain escaped " or be truncated)
    pairs: List[Tuple[str, str]] = []
    # Match ["xxx", "yyy"] with yyy possibly empty or containing text
    for m in re.finditer(r'\[\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\]', text):
        key_or_code, value = m.group(1).strip(), m.group(2).strip()
        if key_or_code:
            pairs.append((key_or_code, value))
    # Also match ["xxx", " with no closing so value is truncated - skip or take empty
    for m in re.finditer(r'\[\s*"([^"]+)"\s*,\s*"', text):
        key_or_code = m.group(1).strip()
        if key_or_code and not any(p[0] == key_or_code for p in pairs):
            pairs.append((key_or_code, ""))
    # Find "n": "next_key_or_code"
    next_match = re.search(r'"n"\s*:\s*"([^"]+)"', text)
    next_key = next_match.group(1).strip() if next_match else None
    if not pairs and not next_key:
        return None
    return {
        COMPACT_KEY_U: [[k, v] for k, v in pairs],
        COMPACT_KEY_N: next_key or "",
    }


def normalize_compact_response(
    raw: Any, 
    checklist: List[Dict[str, Any]],
    valid_keys: set = None
) -> Dict[str, Any]:
    """Normalize compact response to internal schema with safe defaults.
    
    Handles malformed inputs:
    - Wrong types (bool, string, None instead of list/dict)
    - Missing fields
    - Invalid update entries
    
    Fills defaults in backend:
    - status: "inferred"
    - confidence: 0.7
    - evidence: ""
    
    Args:
        raw: Raw parsed response (may be malformed)
        checklist: Current checklist items
        valid_keys: Set of valid checklist keys (optional)
        
    Returns:
        Normalized extraction result dict
    """
    # Build valid keys from checklist if not provided
    if valid_keys is None:
        valid_keys = {item.get("key", "") for item in checklist if item.get("key")}
    
    updates = []
    answered_keys = []
    
    # Safely extract "u" field (updates)
    raw_u = None
    try:
        if isinstance(raw, dict):
            raw_u = raw.get(COMPACT_KEY_U)
        elif isinstance(raw, list):
            raw_u = raw
    except Exception as e:
        logger.warning(f"[Normalizer] Failed to extract 'u' field: {e}")
    
    # Process updates - handle any list-like structure
    update_list = []
    if isinstance(raw_u, list):
        update_list = raw_u
    elif raw_u is not None:
        logger.warning(f"[Normalizer] 'u' field is not a list: {type(raw_u)}")
    
    for entry in update_list:
        # Validate and extract key-value pair
        key, value = _extract_key_value(entry)
        if not key:
            continue
        # Expand short code to full key (e.g. pg -> product_goal)
        key = SHORT_TO_KEY.get(key, key)

        # Validate key is in checklist
        if key not in valid_keys:
            logger.debug(f"[Normalizer] Skipping invalid key: {key}")
            continue
        
        # Build normalized update with defaults
        update = {
            "key": key,
            "value": str(value) if value is not None else "",
            "status": "inferred",  # Default - backend fills this
            "confidence": 0.7,       # Default - backend fills this
            "evidence": "",          # Default - backend fills this
        }
        updates.append(update)
        answered_keys.append(key)
    
    # Extract next key (may be missing or malformed); expand short code to full key
    next_key = None
    try:
        if isinstance(raw, dict):
            next_key = raw.get(COMPACT_KEY_N)
            if next_key and isinstance(next_key, str):
                next_key = next_key.strip()
            elif next_key:
                next_key = str(next_key)
            if next_key:
                next_key = SHORT_TO_KEY.get(next_key, next_key)
    except Exception as e:
        logger.warning(f"[Normalizer] Failed to extract 'n' field: {e}")
    
    # Build remaining gaps
    answered_set = set(answered_keys)
    remaining_gaps = [
        item.get("key") 
        for item in checklist 
        if item.get("status") == "missing" and item.get("key") not in answered_set
    ]
    
    return {
        "updates": updates,
        "answered_keys": answered_keys,
        "conflicts": [],
        "remaining_gaps": remaining_gaps,
        "next_best_question_key": next_key,
    }


def _extract_key_value(entry: Any) -> Tuple[Optional[str], Optional[str]]:
    """Extract key-value from entry, handling multiple formats.
    
    Handles:
    - ["key", "value"] - list/tuple
    - {"k": "key", "v": "value"} - object with short keys
    - {"key": "key", "value": "value"} - object with full keys
    
    Args:
        entry: Entry to parse (may be any type)
        
    Returns:
        Tuple of (key, value) or (None, None) if invalid
    """
    if entry is None:
        return None, None
    
    # Handle list/tuple: ["key", "value"]
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        key = entry[0]
        value = entry[1]
        if isinstance(key, str) and key.strip():
            return key.strip(), str(value) if value is not None else ""
        return None, None
    
    # Handle dict: {"k": "key", "v": "value"} or {"key": "key", "value": "value"}
    if isinstance(entry, dict):
        # Try short keys first
        key = entry.get("k") or entry.get("key")
        value = entry.get("v") or entry.get("value")
        
        if key and isinstance(key, str):
            return key.strip(), str(value) if value is not None else ""
        
        # Try alternative keys
        for k in entry.keys():
            if isinstance(k, str) and len(k) <= 3:  # Short key like "k"
                key = entry.get(k)
                # Find corresponding value key
                for vk in entry.keys():
                    if vk != k and isinstance(vk, str):
                        value = entry.get(vk)
                        if key:
                            return key.strip(), str(value) if value is not None else ""
        
        return None, None
    
    # Handle string: "key:value" or just "key"
    if isinstance(entry, str):
        if ":" in entry:
            parts = entry.split(":", 1)
            return parts[0].strip(), parts[1].strip()
        return entry.strip(), ""
    
    # Any other type - not valid
    logger.warning(f"[Normalizer] Invalid entry type: {type(entry)}")
    return None, None


def safe_get_updates(extraction: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Safely extract updates list from extraction result.
    
    Prevents crashes like 'bool' object is not subscriptable.
    
    Args:
        extraction: Raw extraction dict
        
    Returns:
        List of update dicts (safe, never crashes)
    """
    try:
        updates = extraction.get("updates", [])
        if not isinstance(updates, list):
            logger.warning(f"[SafeUpdates] 'updates' is not a list: {type(updates)}")
            return []
        return updates
    except Exception as e:
        logger.warning(f"[SafeUpdates] Failed to get updates: {e}")
        return []


def safe_get_answered_keys(extraction: Dict[str, Any]) -> List[str]:
    """Safely extract answered_keys from extraction result.
    
    Args:
        extraction: Raw extraction dict
        
    Returns:
        List of answered keys (safe, never crashes)
    """
    try:
        keys = extraction.get("answered_keys", [])
        if not isinstance(keys, list):
            logger.warning(f"[SafeKeys] 'answered_keys' is not a list: {type(keys)}")
            return []
        # Filter to only strings
        return [k for k in keys if isinstance(k, str)]
    except Exception as e:
        logger.warning(f"[SafeKeys] Failed to get answered_keys: {e}")
        return []


__all__ = [
    "safe_parse_compact_response",
    "normalize_compact_response",
    "safe_get_updates",
    "safe_get_answered_keys",
]
