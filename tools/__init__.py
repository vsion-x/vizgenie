"""
Tool registry and initialization
Provides centralized access to all tools
"""

from typing import Dict, List, Callable, Any
import logging

logger = logging.getLogger(__name__)


# Import all tools
from tools.vectordb_tools import (
    vector_similarity_search,
    store_metrics_in_vectordb,
    get_vectordb_client
)

from tools.prometheus_tools import (
    fetch_prometheus_metrics,
    query_prometheus_labels,
    execute_promql_query
)

from tools.postgres_tools import (
    load_postgres_metadata,
    introspect_postgres_schema,
    execute_postgres_query,
    validate_postgres_query
)

from tools.dashboard_tools import (
    deploy_to_grafana,
    fetch_grafana_datasources,
    build_dashboard_json
)


# ===== TOOL REGISTRY =====

TOOL_REGISTRY: Dict[str, Callable] = {
    # VectorDB tools
    'vector_similarity_search': vector_similarity_search,
    'store_metrics_in_vectordb': store_metrics_in_vectordb,
    
    # Prometheus tools
    'fetch_prometheus_metrics': fetch_prometheus_metrics,
    'query_prometheus_labels': query_prometheus_labels,
    'execute_promql_query': execute_promql_query,
    
    # PostgreSQL tools
    'load_postgres_metadata': load_postgres_metadata,
    'introspect_postgres_schema': introspect_postgres_schema,
    'execute_postgres_query': execute_postgres_query,
    'validate_postgres_query': validate_postgres_query,
    
    # Dashboard tools
    'deploy_to_grafana': deploy_to_grafana,
    'fetch_grafana_datasources': fetch_grafana_datasources,
    'build_dashboard_json': build_dashboard_json,
}


def get_tool(tool_name: str) -> Callable:
    """
    Get tool by name
    
    Args:
        tool_name: Name of the tool
    
    Returns:
        Tool function
    
    Raises:
        KeyError: If tool not found
    """
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"Tool '{tool_name}' not found in registry")
    
    return TOOL_REGISTRY[tool_name]


def list_tools() -> List[str]:
    """
    List all available tools
    
    Returns:
        List of tool names
    """
    return list(TOOL_REGISTRY.keys())


def get_tools_by_category() -> Dict[str, List[str]]:
    """
    Get tools organized by category
    
    Returns:
        Dictionary of category -> tool names
    """
    return {
        'vectordb': [
            'vector_similarity_search',
            'store_metrics_in_vectordb'
        ],
        'prometheus': [
            'fetch_prometheus_metrics',
            'query_prometheus_labels',
            'execute_promql_query'
        ],
        'postgresql': [
            'load_postgres_metadata',
            'introspect_postgres_schema',
            'execute_postgres_query',
            'validate_postgres_query'
        ],
        'dashboard': [
            'deploy_to_grafana',
            'fetch_grafana_datasources',
            'build_dashboard_json'
        ]
    }


async def initialize_tools(config: Dict[str, Any]):
    """
    Initialize all tools with configuration
    
    Args:
        config: Configuration dictionary
    """
    logger.info("Initializing tools...")
    
    # Initialize VectorDB
    try:
        vectordb_client = get_vectordb_client()
        logger.info("VectorDB client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize VectorDB: {e}")
    
    logger.info("All tools initialized")


__all__ = [
    # VectorDB
    'vector_similarity_search',
    'store_metrics_in_vectordb',
    'get_vectordb_client',
    
    # Prometheus
    'fetch_prometheus_metrics',
    'query_prometheus_labels',
    'execute_promql_query',
    
    # PostgreSQL
    'load_postgres_metadata',
    'introspect_postgres_schema',
    'execute_postgres_query',
    'validate_postgres_query',
    
    # Dashboard
    'deploy_to_grafana',
    'fetch_grafana_datasources',
    'build_dashboard_json',
    
    # Registry functions
    'get_tool',
    'list_tools',
    'get_tools_by_category',
    'initialize_tools',
    'TOOL_REGISTRY'
]