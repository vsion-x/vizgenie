"""
# graphs/supervisor_graph.py
Supervisor agent - Routes queries to appropriate specialized agents
Uses LLM classification with rule-based fallback
"""

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from schemas.state import AgentState
from llm.prompts import SUPERVISOR_CLASSIFICATION_PROMPT, get_fallback_classification
from llm.retry_handler import get_llm_handler

logger = logging.getLogger(__name__)


async def supervisor_node(state: AgentState) -> AgentState:
    """
    Classify user intent using LLM with fallback
    """
    user_query = state['user_query']
    available_datasources = state.get('available_datasources', [])
    
    # Format datasources for prompt
    ds_info = [
        f"- {ds['name']} ({ds['type']}): {ds['uid']}"
        for ds in available_datasources
    ]
    ds_text = "\n".join(ds_info) if ds_info else "No datasources configured"
    
    # Prepare prompt
    prompt = SUPERVISOR_CLASSIFICATION_PROMPT.format(
        user_query=user_query,
        datasources=ds_text
    )
    
    # Call LLM with retry and fallback
    try:
        llm_handler = get_llm_handler()
        result = await llm_handler.call_llm(
            prompt=prompt,
            temperature=0.1,
            max_tokens=500,
            response_format="json"
        )
        
        state['intent'] = result['intent']
        state['fallback_mode'] = False
        
        # Auto-select datasource if suggested
        if result.get('suggested_datasource'):
            for ds in available_datasources:
                if ds['uid'] == result['suggested_datasource']:
                    state['selected_datasource'] = ds
                    break
        
        logger.info(f"Classified intent: {result['intent']} | Reasoning: {result['reasoning']}")
    
    except Exception as e:
        logger.warning(f"LLM classification failed, using fallback: {e}")
        
        # Rule-based fallback
        result = get_fallback_classification(user_query)
        state['intent'] = result['intent']
        state['fallback_mode'] = True
        state['llm_retry_count'] = state.get('llm_retry_count', 0) + 1
        
        logger.info(f"Fallback classification: {result['intent']} | Reasoning: {result['reasoning']}")
    
    return state


def route_after_supervisor(state: AgentState) -> str:
    """
    Route to appropriate agent based on intent
    """
    intent = state.get('intent', 'metrics')
    
    routing_map = {
        'metrics': 'metrics_agent',
        'sql': 'sql_agent',
    }
    
    destination = routing_map.get(intent, 'metrics_agent')
    logger.info(f"Routing to: {destination}")
    
    return destination


def create_supervisor_graph():
    """
    Create supervisor graph that routes to specialized agents
    """
    from graphs.metrics_graph import create_metrics_graph
    from graphs.sql_graph import create_sql_graph
    
    workflow = StateGraph(AgentState)
    
    # Add supervisor node
    workflow.add_node("supervisor", supervisor_node)
    
    # Add specialized agent subgraphs
    workflow.add_node("metrics_agent", create_metrics_graph())
    workflow.add_node("sql_agent", create_sql_graph())
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Conditional routing from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "metrics_agent": "metrics_agent",
            "sql_agent": "sql_agent",
        }
    )
    
    # All agents terminate the workflow
    for agent in ["metrics_agent", "sql_agent"]:
        workflow.add_edge(agent, END)
    
    return workflow.compile()