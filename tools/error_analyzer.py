"""
# tools/error_analyzer.py
Intelligent Error Analyzer
Extracts real error details from logs, groups by pattern, tracks occurrences
"""

import hashlib
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class ErrorPattern:
    """Represents a unique error pattern"""
    pattern_id: str
    error_type: str
    error_code: Optional[str]
    error_message: str
    stack_trace: Optional[str]
    
    # Occurrence tracking
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int = 1
    
    # Context
    affected_endpoints: List[str] = field(default_factory=list)
    affected_modules: List[str] = field(default_factory=list)
    sample_logs: List[Dict] = field(default_factory=list)
    
    # RCA status
    rca_generated: bool = False
    rca_result: Optional[Dict] = None


class ErrorAnalyzer:
    """
    Analyzes logs to extract real errors, groups by pattern,
    and tracks occurrences intelligently
    """
    
    STORAGE_FILE = Path("data/error_patterns.json")
    
    def __init__(self):
        self.patterns: Dict[str, ErrorPattern] = {}
        self._load_patterns()
    
    def _load_patterns(self) -> None:
        """Load existing patterns from disk"""
        if not self.STORAGE_FILE.exists():
            return
        
        try:
            data = json.loads(self.STORAGE_FILE.read_text(encoding="utf-8"))
            
            for pattern_data in data.get("patterns", []):
                pattern = ErrorPattern(
                    pattern_id=pattern_data["pattern_id"],
                    error_type=pattern_data["error_type"],
                    error_code=pattern_data.get("error_code"),
                    error_message=pattern_data["error_message"],
                    stack_trace=pattern_data.get("stack_trace"),
                    first_seen=datetime.fromisoformat(pattern_data["first_seen"]),
                    last_seen=datetime.fromisoformat(pattern_data["last_seen"]),
                    occurrence_count=pattern_data["occurrence_count"],
                    affected_endpoints=pattern_data.get("affected_endpoints", []),
                    affected_modules=pattern_data.get("affected_modules", []),
                    sample_logs=pattern_data.get("sample_logs", []),
                    rca_generated=pattern_data.get("rca_generated", False),
                    rca_result=pattern_data.get("rca_result"),
                )
                self.patterns[pattern.pattern_id] = pattern
            
            logger.info(f"Loaded {len(self.patterns)} error patterns")
        
        except Exception as e:
            logger.error(f"Failed to load error patterns: {e}")
    
    def _save_patterns(self) -> None:
        """Persist patterns to disk"""
        self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = {
                "patterns": [
                    {
                        "pattern_id": p.pattern_id,
                        "error_type": p.error_type,
                        "error_code": p.error_code,
                        "error_message": p.error_message,
                        "stack_trace": p.stack_trace,
                        "first_seen": p.first_seen.isoformat(),
                        "last_seen": p.last_seen.isoformat(),
                        "occurrence_count": p.occurrence_count,
                        "affected_endpoints": p.affected_endpoints,
                        "affected_modules": p.affected_modules,
                        "sample_logs": p.sample_logs[:5],  # Keep max 5 samples
                        "rca_generated": p.rca_generated,
                        "rca_result": p.rca_result,
                    }
                    for p in self.patterns.values()
                ]
            }
            
            self.STORAGE_FILE.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        
        except Exception as e:
            logger.error(f"Failed to save error patterns: {e}")
    
    def analyze_logs(self, logs: List[Dict]) -> Tuple[List[ErrorPattern], List[ErrorPattern]]:
        """
        Analyze logs to extract errors and group by pattern.
        
        Returns:
            (new_errors, updated_errors)
            - new_errors: Errors seen for first time (need RCA)
            - updated_errors: Existing errors with incremented count (no RCA needed)
        """
        new_errors = []
        updated_errors = []
        
        for log_entry in logs:
            # Only process ERROR and CRITICAL level logs
            if not self._is_error_log(log_entry):
                continue
            
            # Extract error details
            error_details = self._extract_error_details(log_entry)
            if not error_details:
                continue
            
            # Generate pattern ID
            pattern_id = self._generate_pattern_id(error_details)
            
            # Check if pattern exists
            if pattern_id in self.patterns:
                # Existing error - increment count
                pattern = self.patterns[pattern_id]
                pattern.occurrence_count += 1
                pattern.last_seen = datetime.now()
                
                # Update context
                self._update_context(pattern, log_entry)
                
                updated_errors.append(pattern)
                logger.debug(f"Incremented error pattern {pattern_id} → count={pattern.occurrence_count}")
            
            else:
                # New error - create pattern
                pattern = ErrorPattern(
                    pattern_id=pattern_id,
                    error_type=error_details["type"],
                    error_code=error_details.get("code"),
                    error_message=error_details["message"],
                    stack_trace=error_details.get("stack_trace"),
                    first_seen=datetime.now(),
                    last_seen=datetime.now(),
                    occurrence_count=1,
                    sample_logs=[self._sanitize_log(log_entry)],
                )
                
                self._update_context(pattern, log_entry)
                
                self.patterns[pattern_id] = pattern
                new_errors.append(pattern)
                logger.info(f"New error pattern detected: {pattern_id} — {error_details['type']}")
        
        # Save patterns
        if new_errors or updated_errors:
            self._save_patterns()
        
        return new_errors, updated_errors
    
    def _is_error_log(self, log_entry: Dict) -> bool:
        """Check if log is ERROR or CRITICAL level"""
        log_text = log_entry.get("log", "")
        
        # Check JSON structure
        if "level" in log_entry:
            level = log_entry["level"].upper()
            return level in ["ERROR", "CRITICAL"]
        
        # Check log text for level indicators
        level_patterns = [
            r'"level":\s*"(ERROR|CRITICAL)"',
            r'\bERROR\b',
            r'\bCRITICAL\b',
            r'\bFATAL\b',
            r'\bException\b',
            r'\bTraceback\b',
        ]
        
        for pattern in level_patterns:
            if re.search(pattern, log_text, re.IGNORECASE):
                return True
        
        return False

    def _extract_error_details(self, log_entry: Dict) -> Optional[Dict]:
        """Extract structured error details from log entry"""
        log_text = log_entry.get("log", "")
        
        # Parse JSON log first
        try:
            if log_text.strip().startswith("{"):
                log_json = json.loads(log_text)
                
                # Direct fields
                if "error_type" in log_json:
                    return {
                        "type": log_json["error_type"],
                        "code": log_json.get("error_code"),
                        "message": log_json.get("message", ""),
                        "stack_trace": log_json.get("stack_trace"),
                    }
                
                # Look in message field
                msg = log_json.get("message", "")
                for exc in ["TypeError", "ValueError", "IndexError", "NullPointerError",
                        "ConnectionError", "TimeoutError", "DNSError", "ServiceUnavailable",
                        "InternalServerError", "BadGateway", "DivisionByZero"]:
                    if exc in msg:
                        return {
                            "type": exc,
                            "code": log_json.get("error_code"),
                            "message": msg,
                            "stack_trace": log_json.get("stack_trace"),
                        }
        except:
            pass
        
        # Fallback: text pattern matching
        for exc_type in ["BadGateway", "ConnectionError", "DNSError", "DivisionByZero",
                        "InternalServerError", "NullPointerError", "ServiceUnavailable",
                        "TypeError", "IndexError", "ValueError", "AttributeError"]:
            if exc_type in log_text:
                msg_match = re.search(r'message["\s:]+([^"]+)', log_text)
                return {
                    "type": exc_type,
                    "code": None,
                    "message": msg_match.group(1) if msg_match else log_text[:200],
                    "stack_trace": None,
                }
        
        return None  # Skip if can't extract    

    def _generate_pattern_id(self, error_details: Dict) -> str:
        """Generate unique pattern ID from error signature"""
        # Normalize message (remove dynamic values)
        normalized_msg = self._normalize_error_message(error_details["message"])
        
        # Create signature
        signature = f"{error_details['type']}|{error_details.get('code', '')}|{normalized_msg}"
        
        return hashlib.md5(signature.encode()).hexdigest()[:16]
    
    def _normalize_error_message(self, message: str) -> str:
        """Normalize error message to group similar errors"""
        # Remove dynamic values: numbers, timestamps, IDs, paths
        normalized = re.sub(r'\b\d+\b', 'N', message)
        normalized = re.sub(r'\b[a-f0-9]{8,}\b', 'ID', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'/[\w/]+/', '/PATH/', normalized)
        normalized = re.sub(r'user_\w+', 'user_ID', normalized)
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}', 'DATE', normalized)
        
        return normalized[:200]
    
    def _update_context(self, pattern: ErrorPattern, log_entry: Dict) -> None:
        """Update pattern context with log entry details"""
        log_text = log_entry.get("log", "")
        
        # Extract endpoint
        endpoint_match = re.search(r'(?:path|endpoint)[":\s]+([/\w-]+)', log_text)
        if endpoint_match:
            endpoint = endpoint_match.group(1)
            if endpoint not in pattern.affected_endpoints:
                pattern.affected_endpoints.append(endpoint)
        
        # Extract module
        module_match = re.search(r'(?:module|function)[":\s]+([A-Za-z_][A-Za-z0-9_.]*)', log_text)
        if module_match:
            module = module_match.group(1)
            if module not in pattern.affected_modules:
                pattern.affected_modules.append(module)
        
        # Add sample log (keep max 5)
        if len(pattern.sample_logs) < 5:
            pattern.sample_logs.append(self._sanitize_log(log_entry))
    
    def _sanitize_log(self, log_entry: Dict) -> Dict:
        """Sanitize log entry for storage"""
        return {
            "timestamp": log_entry.get("timestamp", ""),
            "log": log_entry.get("log", "")[:500],  # Truncate
        }
    
    def mark_rca_generated(self, pattern_id: str, rca_result: Dict) -> None:
        """Mark pattern as RCA generated"""
        if pattern_id in self.patterns:
            self.patterns[pattern_id].rca_generated = True
            self.patterns[pattern_id].rca_result = rca_result
            self._save_patterns()
            logger.info(f"RCA marked as generated for pattern {pattern_id}")


# ── Global instance ────────────────────────────────────────────────────

_error_analyzer: Optional[ErrorAnalyzer] = None


def get_error_analyzer() -> ErrorAnalyzer:
    global _error_analyzer
    if _error_analyzer is None:
        _error_analyzer = ErrorAnalyzer()
    return _error_analyzer