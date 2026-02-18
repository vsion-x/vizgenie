"""
# nodes/metric_nodes.py
Nodes for deterministic Prometheus metrics workflow
LLM suggestion → VectorDB search → Label discovery → PromQL generation → Dashboard
"""

import logging
from typing import Dict, List
from schemas.state import AgentState
from llm.prompts import METRIC_SUGGESTION_PROMPT
from llm.retry_handler import get_llm_handler

logger = logging.getLogger(__name__)


async def llm_metric_suggestion_node(state: AgentState) -> AgentState:
    """
    Step 1: Use LLM to suggest relevant Prometheus metrics
    """
    user_query = state['user_query']
    
    prompt = METRIC_SUGGESTION_PROMPT.format(user_query=user_query)
    
    try:
        llm_handler = get_llm_handler()
        result = await llm_handler.call_llm(
            prompt=prompt,
            temperature=0.2,
            max_tokens=500,
            response_format="json"
        )
        
        state['llm_suggested_metrics'] = result.get('suggested_metrics', [])
        logger.info(f"LLM suggested metrics: {state['llm_suggested_metrics']}")
    
    except Exception as e:
        logger.error(f"Metric suggestion failed: {e}")
        # Fallback: extract keywords from query
        state['llm_suggested_metrics'] = _extract_metric_keywords(user_query)
        state['fallback_mode'] = True
    
    return state


async def vectordb_search_node(state: AgentState) -> AgentState:
    """Step 2: VectorDB similarity search — fall back to LLM suggestions if empty"""
    from tools.vectordb_tools import vector_similarity_search

    llm_metrics = state.get("llm_suggested_metrics", [])
    ds_uid      = state.get("selected_datasource", {}).get("uid", "")

    similar = []

    if llm_metrics and ds_uid:
        similar = await vector_similarity_search(
            metric_names=llm_metrics,
            datasource_uid=ds_uid,
            n_results=5,
        )

    if not similar:
        logger.warning("VectorDB empty — using LLM suggested metrics directly")
        similar = llm_metrics

    state["vectordb_similar_metrics"] = similar
    logger.info(f"VectorDB found similar metrics: {similar}")

    return state


async def label_discovery_node(state: AgentState) -> AgentState:
    """
    Step 3: Discover available labels for selected metrics
    """
    from tools.prometheus_tools import query_prometheus_labels
    
    similar_metrics = state['vectordb_similar_metrics']
    prometheus_url = state['selected_datasource']['url']
    
    try:
        labels = await query_prometheus_labels(
            metrics=similar_metrics,
            prometheus_url=prometheus_url
        )
        
        state['discovered_labels'] = labels
        logger.info(f"Discovered labels: {labels}")
    
    except Exception as e:
        logger.error(f"Label discovery failed: {e}")
        state['discovered_labels'] = {}
        state['error'] = f"Label discovery failed: {str(e)}"
    
    return state

async def promql_generation_node(state: AgentState) -> AgentState:
    """Step 4: Generate PromQL query"""
    from llm.retry_handler import get_llm_handler
    import re

    similar_metrics   = state.get("vectordb_similar_metrics", [])
    discovered_labels = state.get("discovered_labels", {})
    user_query        = state.get("user_query", "")

    label_lines = []
    for metric, labels in discovered_labels.items():
        if labels:
            label_lines.append(f"  {metric}: {labels}")
    label_context = "\n".join(label_lines) if label_lines else "No labels discovered"
    metrics_str   = ", ".join(similar_metrics) if similar_metrics else "up"

    prompt = f"""You are a PromQL expert. Generate a single valid PromQL query.

        User Request: {user_query}

        Available metrics (use ONLY these):
        {metrics_str}

        Discovered labels:
        {label_context}

        STRICT PromQL syntax rules — violations will break the dashboard:
        1. Counters (_total suffix)  → rate(metric_name[5m])
        2. Gauges (bytes, percent)   → avg_over_time(metric_name[1h])  NOT "avg(...) over (1h)"
        3. Time ranges               → [5m] [15m] [1h] [6h] [24h]  — always inside square brackets
        4. NEVER use SQL syntax:     WRONG: avg(x) over (1h)   RIGHT: avg_over_time(x[1h])
        5. NEVER use datasource="..." label inside the query
        6. Aggregations              → sum(), avg(), max(), min() wrap the full expression
        7. Example for "memory over 1h": avg_over_time(memory_usage_bytes[1h])
        8. Example for "request rate": rate(http_requests_total[5m])

        Return JSON only — no explanation outside JSON:
        {{"query": "your_promql_here", "explanation": "one line reason"}}"""

    try:
        llm_handler = get_llm_handler()
        result = await llm_handler.call_llm(
            prompt=prompt,
            temperature=0.0,   # zero temp for deterministic syntax
            max_tokens=200,
            response_format="json",
        )

        query = result.get("query", "").strip()

        # ── Post-generation sanitisation ───────────────────────────────

        # Fix SQL-style OVER clause: avg(x) over (1h) → avg_over_time(x[1h])
        def fix_over_clause(q: str) -> str:
            # Pattern: func(metric) over (Nh) → func_over_time(metric[Nh])
            pattern = r'(\w+)\(([^)]+)\)\s+[Oo][Vv][Ee][Rr]\s+\((\d+[smhd])\)'
            def replacer(m):
                func   = m.group(1)
                metric = m.group(2).strip()
                window = m.group(3)
                # avg/sum/min/max → use _over_time variant
                if func in ("avg", "sum", "min", "max"):
                    return f"{func}_over_time({metric}[{window}])"
                return f"avg_over_time({metric}[{window}])"
            return re.sub(pattern, replacer, q)

        query = fix_over_clause(query)

        # Strip datasource label
        query = re.sub(r',?\s*datasource\s*=\s*["\'][^"\']*["\']', "", query)
        query = re.sub(r'\{\s*\}', "", query)

        if not query:
            raise ValueError("Empty query returned")

        state["generated_query"] = query
        state["query_type"]      = "promql"
        logger.info(f"Generated PromQL: {query}")

    except Exception as e:
        logger.error(f"PromQL generation failed: {e}")
        metric = similar_metrics[0] if similar_metrics else "up"
        if metric.endswith("_total"):
            state["generated_query"] = f"rate({metric}[5m])"
        elif any(x in metric for x in ("bytes", "percent", "usage", "memory")):
            state["generated_query"] = f"avg_over_time({metric}[1h])"
        else:
            state["generated_query"] = f"avg({metric})"
        state["query_type"]    = "promql"
        state["fallback_mode"] = True
        logger.info(f"Fallback PromQL: {state['generated_query']}")

    return state


def _extract_metric_keywords(query: str) -> List[str]:
    """
    Fallback: Extract potential metric names from query
    """
    import re
    
    # Common metric patterns
    patterns = [
        r'\b(cpu|memory|disk|network|http|request|error|latency)\b',
        r'\b(node_\w+)',
        r'\b(container_\w+)',
        r'\b(http_\w+)'
    ]
    
    metrics = []
    query_lower = query.lower()
    
    for pattern in patterns:
        matches = re.findall(pattern, query_lower)
        metrics.extend(matches)
    
    # Default fallback
    if not metrics:
        metrics = ['node_cpu_seconds_total', 'node_memory_Active_bytes']
    
    return list(set(metrics))[:5]