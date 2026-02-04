# state/graph_state.py
# Core state management for VizGenie LangGraph

from typing import TypedDict, List, Dict, Optional, Annotated, Any
from enum import Enum
import operator


class QueryType(str, Enum):
    """Type of query/datasource"""
    PROMETHEUS = "prometheus"
    POSTGRES = "postgres"
    MIXED = "mixed"


class ProcessingStage(str, Enum):
    """Current stage of workflow processing"""
    INITIALIZED = "initialized"
    INTENT_EXTRACTED = "intent_extracted"
    METRICS_EXTRACTED = "metrics_extracted"
    SIMILARITY_SEARCHED = "similarity_searched"
    QUERY_GENERATED = "query_generated"
    QUERY_VALIDATED = "query_validated"
    DASHBOARD_GENERATED = "dashboard_generated"
    DEPLOYED = "deployed"
    FAILED = "failed"


class QueryContext(TypedDict):
    """Context for a single query"""
    query_text: str
    datasource_name: str
    datasource_uid: str
    datasource_type: str
    query_type: QueryType


class MetricsContext(TypedDict):
    """Extracted metrics and labels"""
    suggested_metrics: List[str]
    suggested_labels: List[str]
    similar_metrics: List[str]
    metric_labels: Dict[str, List[str]]


class GeneratedQuery(TypedDict):
    """Generated PromQL or SQL query"""
    datasource_uid: str
    original_query: str
    generated_query: str
    query_type: str
    is_valid: bool
    validation_errors: Optional[List[str]]


class DashboardSpec(TypedDict):
    """Dashboard specification"""
    title: str
    panels: List[Dict[str, Any]]
    uid: str
    deployed_url: Optional[str]


class VizGenieState(TypedDict):
    """Main state for VizGenie LangGraph workflow"""
    
    # Input
    user_queries: List[QueryContext]
    
    # Configuration
    grafana_url: str
    grafana_api_key: str
    prometheus_url: str
    postgres_url: str
    available_datasources: List[Dict[str, Any]]
    
    # Processing state
    current_stage: ProcessingStage
    current_query_index: int
    
    # Intermediate results (use operator.add to merge lists)
    metrics_contexts: Annotated[List[MetricsContext], operator.add]
    generated_queries: Annotated[List[GeneratedQuery], operator.add]
    
    # Final results
    dashboard_spec: Optional[DashboardSpec]
    deployment_result: Optional[Dict[str, Any]]
    
    # Error handling (use operator.add to accumulate errors)
    errors: Annotated[List[Dict[str, Any]], operator.add]
    retry_count: int
    max_retries: int
    
    # Metadata (use operator.add to accumulate logs)
    execution_log: Annotated[List[Dict[str, Any]], operator.add]
    start_time: Optional[str]
    end_time: Optional[str]


class AgentMessage(TypedDict):
    """Message format for agent communication"""
    agent: str
    stage: ProcessingStage
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]]