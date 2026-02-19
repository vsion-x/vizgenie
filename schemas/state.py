"""
# schemas/state.py
Agent state schemas for LangGraph workflows
Focused on log monitoring + RCA only
"""

from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict


class AgentState(TypedDict, total=False):
    """
    Universal state for RCA agent
    Stripped to log monitoring + RCA concerns only
    """

    # ===== INPUT =====
    user_query: str
    intent: str  # always "rca" now

    # ===== DATASOURCE CONTEXT =====
    available_datasources: List[Dict[str, Any]]
    # [{'name': str, 'type': 'cloudwatch'|..., 'source_obj': LogSource}]

    datasource_uid: str
    datasource_type: str

    # ===== CONVERSATION CONTEXT =====
    conversation_history: List[Dict[str, str]]

    # ===== LOKI / GENERIC LOGS =====
    loki_logs: List[Dict[str, Any]]
    # kept as alias for "fetched logs" from any source

    log_patterns: List[Dict[str, Any]]
    # [{'error_type': str, 'regex': str, 'intent': str, 'extract': {...}}]

    categorized_data: Dict[str, Any]
    # {'errors': [...], 'warnings': [...], 'unknown': [...]}

    # ===== ERROR PATTERN (passed into RCA from monitor) =====
    error_pattern: Optional[Dict[str, Any]]
    # {
    #   'pattern_id': str,
    #   'error_type': str,
    #   'error_code': str | None,
    #   'error_message': str,
    #   'stack_trace': str | None,
    #   'affected_endpoints': [str],
    #   'affected_modules': [str],
    #   'occurrence_count': int,
    #   'first_seen': str (ISO),
    #   'sample_logs': [str],
    # }

    # ===== RCA WORKFLOW =====
    anomaly: Optional[Dict[str, Any]]
    # {
    #   'timestamp': datetime,
    #   'severity': 'critical'|'high'|'medium'|'low',
    #   'severity_level': int,
    #   'anomaly_type': str,
    #   'details': {...},
    #   'evidence': {...},
    # }

    evidence: Dict[str, Any]
    # {
    #   'error_logs': [...],
    #   'metrics': {},       # always empty now (no Prometheus)
    #   'patterns': [...],
    #   'error_pattern': {...},
    # }

    correlations: Dict[str, Any]
    # {'temporal': [...], 'causal': [...], 'affected_components': [...]}

    correlated_metrics: Dict[str, Any]  # kept for schema compat, always {}

    root_cause_analysis: str
    resolution_suggestions: List[Dict[str, str]]

    rca_result: Dict[str, Any]
    rca_report: str
    rca_report_structured: Dict[str, Any]

    # ===== OBSERVABILITY METRICS =====
    mttd: Optional[float]   # Mean Time To Detect (seconds)
    mttr: Optional[float]   # Mean Time To Resolve (seconds)
    incident_id: Optional[str]

    # ===== INVESTIGATION STEPS =====
    investigation_steps: List[Dict[str, Any]]
    tools_used: List[str]

    # ===== ERROR HANDLING =====
    error: Optional[str]
    llm_retry_count: int
    fallback_mode: bool

    # ===== GRAFANA (disabled — kept for schema compat) =====
    grafana_url: str
    grafana_api_key: str
    dashboard_url: str


@dataclass
class Anomaly:
    """Structured anomaly data"""
    timestamp: datetime
    severity: str
    severity_level: int
    anomaly_type: str
    datasource_uid: str
    datasource_type: str
    details: Dict[str, Any]
    evidence: Dict[str, Any]
    mttd: Optional[float] = None

    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data