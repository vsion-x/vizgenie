"""
# utils/rca_deduplicator.py
RCA Deduplication Engine
Groups similar incidents by root cause pattern
Python 3.12 compatible
"""

import logging
import hashlib
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RCAPattern:
    """Represents a unique RCA pattern"""
    pattern_id:       str
    category:         str
    component:        str
    first_seen:       datetime
    last_seen:        datetime
    occurrence_count: int
    total_duration:   float  # seconds
    avg_interval:     float  # seconds between occurrences
    severity_counts:  Dict[str, int] = field(default_factory=dict)
    anomaly_types:    List[str]      = field(default_factory=list)
    sample_evidence:  List[str]      = field(default_factory=list)
    resolution:       Dict           = field(default_factory=dict)


class RCADeduplicator:
    """Deduplicates RCA reports by root cause pattern"""
    
    STORAGE_FILE = Path("data/rca_patterns.json")
    
    def __init__(self):
        self.patterns: Dict[str, RCAPattern] = {}
        self._load_patterns()
    
    def _load_patterns(self) -> None:
        """Load existing patterns from disk"""
        if not self.STORAGE_FILE.exists():
            return
        
        try:
            data = json.loads(self.STORAGE_FILE.read_text(encoding="utf-8"))
            
            for pattern_data in data.get("patterns", []):
                pattern = RCAPattern(
                    pattern_id=pattern_data["pattern_id"],
                    category=pattern_data["category"],
                    component=pattern_data["component"],
                    first_seen=datetime.fromisoformat(pattern_data["first_seen"]),
                    last_seen=datetime.fromisoformat(pattern_data["last_seen"]),
                    occurrence_count=pattern_data["occurrence_count"],
                    total_duration=pattern_data["total_duration"],
                    avg_interval=pattern_data["avg_interval"],
                    severity_counts=pattern_data.get("severity_counts", {}),
                    anomaly_types=pattern_data.get("anomaly_types", []),
                    sample_evidence=pattern_data.get("sample_evidence", []),
                    resolution=pattern_data.get("resolution", {}),
                )
                self.patterns[pattern.pattern_id] = pattern
            
            logger.info(f"Loaded {len(self.patterns)} RCA patterns")
        
        except Exception as e:
            logger.error(f"Failed to load RCA patterns: {e}")
    
    def _save_patterns(self) -> None:
        """Persist patterns to disk"""
        self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = {
                "patterns": [
                    {
                        "pattern_id": p.pattern_id,
                        "category": p.category,
                        "component": p.component,
                        "first_seen": p.first_seen.isoformat(),
                        "last_seen": p.last_seen.isoformat(),
                        "occurrence_count": p.occurrence_count,
                        "total_duration": p.total_duration,
                        "avg_interval": p.avg_interval,
                        "severity_counts": p.severity_counts,
                        "anomaly_types": p.anomaly_types,
                        "sample_evidence": p.sample_evidence,
                        "resolution": p.resolution,
                    }
                    for p in self.patterns.values()
                ]
            }
            
            self.STORAGE_FILE.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        
        except Exception as e:
            logger.error(f"Failed to save RCA patterns: {e}")
    
    def _generate_pattern_id(self, category: str, component: str) -> str:
        """Generate unique pattern ID from root cause"""
        key = f"{category}_{component}".lower()
        return hashlib.md5(key.encode()).hexdigest()[:12]
    
    def add_or_update(
        self,
        rca_result: Dict,
        anomaly: Dict,
        timestamp: datetime,
    ) -> tuple[str, bool]:
        """
        Add new RCA or update existing pattern.
        
        Returns:
            (pattern_id, is_new)
        """
        root_cause = rca_result.get("root_cause", {})
        category   = root_cause.get("category", "Unknown")
        component  = root_cause.get("component", "Unknown")
        
        pattern_id = self._generate_pattern_id(category, component)
        is_new     = pattern_id not in self.patterns
        
        if is_new:
            # Create new pattern
            pattern = RCAPattern(
                pattern_id=pattern_id,
                category=category,
                component=component,
                first_seen=timestamp,
                last_seen=timestamp,
                occurrence_count=1,
                total_duration=0.0,
                avg_interval=0.0,
                severity_counts={anomaly.get("severity", "unknown"): 1},
                anomaly_types=[anomaly.get("anomaly_type", "unknown")],
                sample_evidence=rca_result.get("evidence", [])[:3],
                resolution=rca_result.get("resolution_suggestions", [{}])[0],
            )
            self.patterns[pattern_id] = pattern
        
        else:
            # Update existing pattern
            pattern = self.patterns[pattern_id]
            
            # Update counts
            pattern.occurrence_count += 1
            severity = anomaly.get("severity", "unknown")
            pattern.severity_counts[severity] = pattern.severity_counts.get(severity, 0) + 1
            
            # Update anomaly types
            atype = anomaly.get("anomaly_type", "unknown")
            if atype not in pattern.anomaly_types:
                pattern.anomaly_types.append(atype)
            
            # Calculate interval
            interval = (timestamp - pattern.last_seen).total_seconds()
            pattern.total_duration += interval
            pattern.avg_interval = pattern.total_duration / (pattern.occurrence_count - 1) if pattern.occurrence_count > 1 else 0.0
            
            # Update timestamps
            pattern.last_seen = timestamp
        
        self._save_patterns()
        
        return pattern_id, is_new
    
    def get_pattern(self, pattern_id: str) -> Optional[RCAPattern]:
        """Get pattern by ID"""
        return self.patterns.get(pattern_id)
    
    def get_all_patterns(self) -> List[RCAPattern]:
        """Get all patterns sorted by occurrence count"""
        return sorted(
            self.patterns.values(),
            key=lambda p: p.occurrence_count,
            reverse=True,
        )


# ── Global instance ────────────────────────────────────────────────────

_deduplicator: Optional[RCADeduplicator] = None


def get_deduplicator() -> RCADeduplicator:
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = RCADeduplicator()
    return _deduplicator