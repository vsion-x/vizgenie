# graphs/metrics_graph.py
"""
Deterministic Prometheus metrics workflow graph
Sequential execution: LLM suggestion → VectorDB → Labels → PromQL → Dashboard
"""

from langgraph.graph import StateGraph, END
from schemas.state import AgentState
from nodes.metric_nodes import (
    llm_metric_suggestion_node,
    vectordb_search_node,
    label_discovery_node,
    promql_generation_node
)
from nodes.dashboard_node import dashboard_creation_node


def create_metrics_graph():
    """
    Create deterministic metrics agent workflow
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes in sequence
    workflow.add_node("llm_metric_suggestion", llm_metric_suggestion_node)
    workflow.add_node("vectordb_search", vectordb_search_node)
    workflow.add_node("label_discovery", label_discovery_node)
    workflow.add_node("promql_generation", promql_generation_node)
    workflow.add_node("dashboard_creation", dashboard_creation_node)
    
    # Define linear workflow
    workflow.set_entry_point("llm_metric_suggestion")
    workflow.add_edge("llm_metric_suggestion", "vectordb_search")
    workflow.add_edge("vectordb_search", "label_discovery")
    workflow.add_edge("label_discovery", "promql_generation")
    workflow.add_edge("promql_generation", "dashboard_creation")
    workflow.add_edge("dashboard_creation", END)
    
    return workflow.compile()