"""
# graphs/sql_graph.py
Deterministic PostgreSQL SQL workflow graph
Sequential execution: Schema loading → SQL generation → Dashboard
"""

from langgraph.graph import StateGraph, END
from schemas.state import AgentState
from nodes.sql_nodes import schema_loader_node, sql_generation_node
from nodes.dashboard_node import dashboard_creation_node


def create_sql_graph():
    """
    Create deterministic SQL agent workflow
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("schema_loader", schema_loader_node)
    workflow.add_node("sql_generation", sql_generation_node)
    workflow.add_node("dashboard_creation", dashboard_creation_node)
    
    # Define linear workflow
    workflow.set_entry_point("schema_loader")
    workflow.add_edge("schema_loader", "sql_generation")
    workflow.add_edge("sql_generation", "dashboard_creation")
    workflow.add_edge("dashboard_creation", END)
    
    return workflow.compile()