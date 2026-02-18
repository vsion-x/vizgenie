"""
# schemas/state.py
Agent state schemas for LangGraph workflows
Supports MTTD/MTTR tracking and multi-datasource contexts
"""

from typing import TypedDict, Literal, List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict


class AgentState(TypedDict, total=False):
    """
    Universal state for all agents
    Generic design - extensible for new datasources/agents
    """
    
    # ===== INPUT =====
    user_query: str
    intent: Literal["metrics", "sql", "troubleshoot", "learning", "rca"]
    
    # ===== DATASOURCE CONTEXT =====
    selected_datasource: Dict[str, Any]
    # {
    #   'uid': str,
    #   'name': str,
    #   'type': 'prometheus' | 'postgresql' | 'loki',
    #   'url': str,
    #   'config': {...}
    # }
    
    available_datasources: List[Dict[str, Any]]  # For cross-correlation in RCA
    
    # ===== CONVERSATION CONTEXT =====
    conversation_history: List[Dict[str, str]]
    # [{'role': 'user'|'assistant', 'content': str}]
    
    # ===== METRICS WORKFLOW =====
    llm_suggested_metrics: List[str]
    vectordb_similar_metrics: List[str]
    discovered_labels: Dict[str, List[str]]
    # {'metric_name': ['label1', 'label2']}
    
    # ===== SQL WORKFLOW =====
    postgres_metadata: Dict[str, Any]
    # {'tables': [...], 'columns': {...}}
    
    # ===== GENERATED QUERIES =====
    generated_query: str  # PromQL or SQL
    query_type: Literal["promql", "sql", "logql"]
    
    # ===== LOKI/LOGS =====
    loki_logs: List[Dict[str, Any]]
    # [{'timestamp': float, 'log': str, 'labels': {...}}]
    
    log_patterns: List[Dict[str, Any]]
    # From YAML: [{'category': str, 'regex': str, 'severity': str}]
    
    categorized_logs: Dict[str, List[Dict]]
    # {'error': [...], 'db': [...], 'unknown': [...]}
    
    # ===== RCA CONTEXT =====
    anomaly: Optional[Dict[str, Any]]
    # {
    #   'timestamp': datetime,
    #   'severity': 'critical'|'high'|'medium'|'low',
    #   'anomaly_type': str,
    #   'details': {...},
    #   'evidence': {...}
    # }
    
    correlated_metrics: Dict[str, Any]
    # Metrics from multiple datasources for RCA
    
    root_cause_analysis: str
    resolution_suggestions: List[Dict[str, str]]
    # [{'type': 'code'|'db'|'config', 'suggestion': str, 'implementation': str}]
    
    # ===== OBSERVABILITY METRICS =====
    mttd: Optional[float]  # Mean Time To Detect (seconds)
    mttr: Optional[float]  # Mean Time To Resolve (seconds)
    incident_id: Optional[str]
    
    # ===== DASHBOARD =====
    dashboard_json: Dict[str, Any]
    dashboard_url: str
    
    # ===== ERROR HANDLING =====
    error: Optional[str]
    llm_retry_count: int
    fallback_mode: bool
    
    # ===== INVESTIGATOR AGENT =====
    investigation_steps: List[Dict[str, Any]]
    # [{'step': int, 'action': str, 'result': {...}}]
    
    tools_used: List[str]
    # Track which tools were called
    
    # ===== LEARNING AGENT =====
    learned_patterns: List[Dict[str, Any]]
    pattern_confidence: Dict[str, float]
    # {'pattern_id': confidence_score}


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