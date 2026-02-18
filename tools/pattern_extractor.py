"""
# tools/pattern_extractor.py
Pattern Extractor
Sends sampled logs to LLM to extract:
1. Regex patterns for each error type
2. Intent classification rules
3. Data extraction rules (endpoint, module, etc.)
"""

import logging
import json
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class PatternStore:
    """Manages learned patterns"""
    
    PATTERN_FILE = Path("config/patterns.json")
    
    def __init__(self):
        self.patterns: List[Dict] = []
        self._load()
    
    def _load(self):
        """Load patterns from disk"""
        if not self.PATTERN_FILE.exists():
            return
        
        try:
            data = json.loads(self.PATTERN_FILE.read_text())
            self.patterns = data.get("patterns", [])
            logger.info(f"Loaded {len(self.patterns)} patterns")
        except Exception as e:
            logger.error(f"Failed to load patterns: {e}")
    
    def _save(self):
        """Save patterns to disk"""
        self.PATTERN_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = {"patterns": self.patterns}
            self.PATTERN_FILE.write_text(json.dumps(data, indent=2))
            logger.info(f"Saved {len(self.patterns)} patterns to {self.PATTERN_FILE}")
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")
    
    async def learn_from_logs(self, sampled: Dict) -> List[Dict]:
        """
        Use LLM to extract patterns from logs
        
        Args:
            sampled: {
                "full_logs": [str, ...],  # 5 full logs
                "summaries": [{"error_type": str, "snippet": str}, ...]
            }
        
        Returns:
            List of patterns
        """
        from llm.retry_handler import get_llm_handler
        
        prompt = self._build_prompt(sampled)
        
        logger.info("Sending logs to LLM for pattern extraction...")
        
        llm = get_llm_handler()
        response_data = await llm.call_llm(
            prompt=prompt,
            temperature=0.0,
            max_tokens=2000,
            response_format="json"
        )
        
        logger.info(f"LLM response_data type: {type(response_data)}")
        logger.info(f"LLM response_data keys: {response_data.keys() if isinstance(response_data, dict) else 'not a dict'}")
        
        # Extract content from response - handle both dict and direct string
        if isinstance(response_data, dict):
            response = response_data.get("content", response_data)
            # If content is still a dict, try to get the actual text
            if isinstance(response, dict):
                response = json.dumps(response)
        else:
            response = str(response_data)
        
        logger.info(f"Extracted response (first 200 chars): {str(response)[:200]}")
        
        # Parse response
        try:
            # Remove markdown if present
            response = str(response).strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            data = json.loads(response)
            
            if isinstance(data, dict) and "patterns" in data:
                patterns = data["patterns"]
            elif isinstance(data, list):
                patterns = data
            else:
                logger.error(f"Invalid LLM response format. Data type: {type(data)}, Data keys: {data.keys() if isinstance(data, dict) else 'not a dict'}")
                logger.error(f"Full data: {json.dumps(data, indent=2)[:500]}")
                return []
            
            # Save patterns
            self.patterns = patterns
            self._save()
            
            logger.info(f"✅ Extracted {len(patterns)} patterns")
            return patterns
        
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Response: {response[:500]}")
            return []
    
    def _build_prompt(self, sampled: Dict) -> str:
        """Build LLM prompt for pattern extraction"""
        
        full_logs = sampled.get("full_logs", [])
        summaries = sampled.get("summaries", [])
        
        prompt = f"""You are analyzing application ERROR logs to extract monitoring patterns.

# FULL ERROR LOGS (5 examples):
{chr(10).join(f"{i+1}. {log}" for i, log in enumerate(full_logs))}

# ADDITIONAL ERRORS ({len(summaries)} more):
{chr(10).join(f"- {s['error_type']}: {s['snippet']}" for s in summaries[:30])}

# YOUR TASK:
Extract error patterns as JSON with these fields:

1. **error_type**: Error name (e.g., "NullPointerError", "ConnectionError")
2. **regex**: Python regex to match this error in logs
3. **intent**: What this error indicates (e.g., "null_reference", "network_failure", "database_timeout")
4. **extract**: Dict of extraction rules (regex to extract structured data)
   - endpoint: Extract API endpoint path
   - module: Extract module/function name
   - error_code: Extract error code if present
   - latency_ms: Extract latency if present

# EXAMPLE OUTPUT:
```json
{{
  "patterns": [
    {{
      "error_type": "NullPointerError",
      "regex": "NullPointerError.*'NoneType' object has no attribute",
      "intent": "null_reference",
      "extract": {{
        "endpoint": "path[\"\\s:]+([/\\\\w-]+)",
        "module": "module[\"\\s:]+(\\\\w+)",
        "error_code": "error_code[\"\\s:]+([A-Z0-9_]+)"
      }}
    }},
    {{
      "error_type": "ConnectionError",
      "regex": "ConnectionError.*(connection refused|reset|timeout)",
      "intent": "network_failure",
      "extract": {{
        "endpoint": "path[\"\\s:]+([/\\\\w-]+)"
      }}
    }},
    {{
      "error_type": "DatabaseError",
      "regex": "DatabaseError.*(timeout|deadlock|connection pool)",
      "intent": "database_failure",
      "extract": {{
        "query": "query[\"\\s:]+([^\"]+)",
        "latency_ms": "latency[\"\\s:]+(\\\\d+)"
      }}
    }}
  ]
}}
```

# RULES:
- Each error type should have ONE pattern
- Regex should be broad enough to catch variations
- Intent should be lowercase with underscores
- Extract rules are optional but helpful
- Respond ONLY with valid JSON
- NO markdown, NO explanations, JUST JSON

Output:"""
        
        return prompt
    
    def get_patterns(self) -> List[Dict]:
        """Get all learned patterns"""
        return self.patterns


# ── Global instance ────────────────────────────────────────────────────

_store = None

def get_pattern_store() -> PatternStore:
    global _store
    if _store is None:
        _store = PatternStore()
    return _store