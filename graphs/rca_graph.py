"""
# graphs/rca_graph.py
RCA (Root Cause Analysis) Agent
Triggered by SmartMonitor on new / recurring error patterns.
No Prometheus / Grafana dependency — evidence comes from
the log source registry only.
"""

import logging
from datetime import datetime
from typing import Dict

from langgraph.graph import END, StateGraph

from llm.prompts       import RCA_ANALYSIS_PROMPT
from llm.retry_handler import get_llm_handler
from schemas.state     import AgentState

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
#  Node 1 — Gather evidence
# ══════════════════════════════════════════════════════════════════════

async def gather_evidence_node(state: AgentState) -> AgentState:
    """
    Collect evidence from:
      • error_pattern already in state (always available)
      • recent logs from ALL registered log sources (optional)
    No Prometheus / Grafana calls.
    """
    from tools.log_source_manager import get_log_source_registry

    error_pattern_data = state.get("error_pattern", {})
    registry           = get_log_source_registry()

    evidence: Dict = {
        "error_logs":    [],
        "metrics":       {},   # always empty — Prometheus disabled
        "patterns":      [],
        "error_pattern": error_pattern_data,
    }

    # Fetch recent logs from every registered source
    try:
        recent_logs = await registry.fetch_all_logs(
            time_range="15m",
            filters=None,
            limit=50,
        )
        evidence["error_logs"] = [
            log for log in recent_logs
            if log.get("level", "").upper() in ("ERROR", "CRITICAL")
        ]
        logger.info(
            f"Gathered {len(evidence['error_logs'])} error logs "
            f"from {len(registry.list_sources())} source(s)"
        )
    except Exception as exc:
        logger.warning(f"Could not fetch logs from registry: {exc}")

    state["evidence"]           = evidence
    state["loki_logs"]          = evidence["error_logs"]
    state["correlated_metrics"] = {}

    return state


# ══════════════════════════════════════════════════════════════════════
#  Node 2 — Cross-correlate
# ══════════════════════════════════════════════════════════════════════

async def cross_correlate_node(state: AgentState) -> AgentState:
    """Identify affected components from error pattern."""
    evidence = state.get("evidence", {})
    pattern  = evidence.get("error_pattern", {})

    correlations = {
        "temporal":            [],
        "causal":              [],
        "affected_components": list(
            set(
                pattern.get("affected_endpoints", [])
                + pattern.get("affected_modules",  [])
            )
        ),
    }

    state["correlations"] = correlations
    logger.info(
        f"Cross-correlation: "
        f"{len(correlations['affected_components'])} affected components"
    )
    return state


# ══════════════════════════════════════════════════════════════════════
#  Node 3 — LLM RCA analysis
# ══════════════════════════════════════════════════════════════════════

async def llm_rca_analysis_node(state: AgentState) -> AgentState:
    """Send rich error context to LLM for root cause analysis."""
    anomaly      = state.get("anomaly",      {})
    evidence     = state.get("evidence",     {})
    correlations = state.get("correlations", {})

    pattern           = evidence.get("error_pattern", {})
    error_type        = pattern.get("error_type",       "Unknown")
    error_code        = pattern.get("error_code",       "N/A")
    error_message     = pattern.get("error_message",    "No message")
    stack_trace       = pattern.get("stack_trace",      "No stack trace available")
    affected_endpoints = pattern.get("affected_endpoints", [])
    affected_modules   = pattern.get("affected_modules",   [])
    sample_logs_data   = pattern.get("sample_logs",        [])
    occurrence_count   = pattern.get("occurrence_count",   1)

    # Build detailed error context string
    error_context = f"""
ERROR TYPE: {error_type}
ERROR CODE: {error_code}
OCCURRENCES: {occurrence_count} times

ERROR MESSAGE:
{error_message}

STACK TRACE:
{stack_trace}

AFFECTED ENDPOINTS:
{', '.join(affected_endpoints[:5]) if affected_endpoints else 'None identified'}

AFFECTED MODULES:
{', '.join(affected_modules[:5]) if affected_modules else 'None identified'}

SAMPLE LOGS (showing first 2):
"""
    for idx, log in enumerate(sample_logs_data[:2], 1):
        log_text      = log if isinstance(log, str) else str(log)
        error_context += f"\n--- Sample {idx} ---\n{log_text[:500]}\n"

    prompt = RCA_ANALYSIS_PROMPT.format(
        trigger_type=error_type,
        severity=anomaly.get("severity", "medium"),
        trigger_details=error_context,
        time_window="15 minutes",
        error_logs=error_context,
        metrics_data="No metrics available (Prometheus disabled)",
        pattern_analysis=f"Error pattern detected {occurrence_count} times",
        affected_components=(
            ", ".join(affected_modules[:5]) if affected_modules else "Unknown"
        ),
    )

    try:
        llm_handler = get_llm_handler()
        rca_result  = await llm_handler.call_llm(
            prompt=prompt,
            temperature=0.1,
            max_tokens=3000,
            response_format="json",
        )

        state["root_cause_analysis"]  = (
            rca_result.get("root_cause", {}).get("description", "")
        )
        state["resolution_suggestions"] = rca_result.get("resolution_suggestions", [])
        state["mttd"]       = rca_result.get("mttd_analysis",  {}).get("detection_time", 0)
        state["mttr"]       = rca_result.get("mttr_estimate",  {}).get("estimated_resolution_time", 0)
        state["rca_result"] = rca_result

        logger.info(
            f"RCA complete: "
            f"{rca_result.get('root_cause', {}).get('category', 'unknown')}"
        )

    except Exception as exc:
        logger.error(f"LLM RCA failed: {exc}")
        _fallback_rca_analysis(state)

    return state


# ══════════════════════════════════════════════════════════════════════
#  Fallback RCA (no LLM)
# ══════════════════════════════════════════════════════════════════════

def _fallback_rca_analysis(state: AgentState) -> None:
    """Heuristic RCA when LLM is unavailable."""
    import re

    evidence        = state.get("evidence", {})
    pattern         = evidence.get("error_pattern", {})
    error_type      = pattern.get("error_type",    "Unknown")
    error_message   = pattern.get("error_message", "")
    stack_trace     = pattern.get("stack_trace",   "") or ""
    affected_modules  = pattern.get("affected_modules",  [])
    affected_endpoints = pattern.get("affected_endpoints", [])

    t = error_type.lower()

    def _line(st: str) -> str:
        m = re.search(r"line (\d+)", st)
        return m.group(1) if m else "XXX"

    if "type" in t:
        category   = "code"
        component  = affected_modules[0] if affected_modules else "/app/main.py"
        description = f"Type mismatch in {component}. {error_message[:200]}"
        impl = f"""1. Open: {component}
2. Find string + integer concatenation
3. Fix: str(number) or int(string)
4. Add isinstance() validation
5. Test and deploy"""

    elif "null" in t or "none" in t:
        category   = "code"
        component  = affected_modules[0] if affected_modules else "/app/main.py"
        line       = _line(stack_trace)
        description = f"Null/None reference in {component} line {line}."
        impl = f"""1. Open: {component}  →  line {line}
2. Add null check before access:
   if obj is not None:
       result = obj.method()
3. Find why object is None
4. Test and deploy"""

    elif "division" in t or "zero" in t:
        category   = "code"
        component  = affected_modules[0] if affected_modules else "/app/main.py"
        line       = _line(stack_trace)
        description = f"Division by zero in {component} line {line}."
        impl = f"""1. Open: {component}  →  line {line}
2. Add zero check before division:
   if denominator != 0:
       result = numerator / denominator
3. Add input validation
4. Test and deploy"""

    elif "index" in t or "bound" in t:
        category   = "code"
        component  = affected_modules[0] if affected_modules else "Unknown"
        description = f"Array index out of bounds in {component}."
        impl = f"""1. Open file containing: {component}
2. Add bounds check:
   if 0 <= index < len(items):
       value = items[index]
3. Test with edge cases"""

    elif "connection" in t or "dns" in t or "timeout" in t:
        category   = "infrastructure"
        component  = "External service / Network"
        description = f"Network/connection failure: {error_message[:200]}"
        impl = """1. Verify external service is up
2. Check DNS resolution
3. Add retry with exponential backoff
4. Add circuit breaker
5. Contact: Network Team / External API Provider"""

    else:
        category   = "code"
        component  = affected_modules[0] if affected_modules else "Unknown"
        description = f"{error_type}: {error_message[:200]}"
        impl = f"""Review stack trace:\n{stack_trace[:300]}\n\n1. Locate exact line\n2. Review recent changes\n3. Add error handling"""

    state["rca_result"] = {
        "root_cause": {
            "category":         category,
            "component":        component,
            "description":      description,
            "confidence_score": 0.75,
            "contact_team":     f"{category.capitalize()} Team",
        },
        "resolution_suggestions": [{
            "type":           category,
            "priority":       "high",
            "suggestion":     f"Fix {error_type} in {component}",
            "implementation": impl,
            "estimated_time": "15-30 minutes",
            "risk_level":     "low",
            "rollback_plan":  "Revert to previous working commit",
            "contact":        f"{category.capitalize()} Team",
        }],
        "evidence": [
            f"Error: {error_message}",
            f"Stack trace points to: {component}",
            f"Occurred {pattern.get('occurrence_count', 1)} time(s)",
        ],
        "impact_analysis": {
            "affected_users":    "Unknown",
            "affected_requests": f"{pattern.get('occurrence_count', 1)} occurrences",
            "business_impact":   "Service degradation",
        },
        "preventive_measures": [
            f"Add input validation in {component}",
            f"Add unit tests for {error_type} scenarios",
            "Add monitoring alert for this error type",
            "Review codebase for similar patterns",
        ],
        "mttd_analysis": {
            "detection_time":   0,
            "detection_method": "Automated log monitoring",
        },
        "mttr_estimate": {
            "estimated_resolution_time": 1800,
            "assumptions": ["Fix requires code change", "No external dependencies"],
        },
    }

    state["root_cause_analysis"]  = description
    state["resolution_suggestions"] = state["rca_result"]["resolution_suggestions"]
    state["fallback_mode"]         = True

    logger.info("Fallback RCA complete")


# ══════════════════════════════════════════════════════════════════════
#  Node 4 — Format report
# ══════════════════════════════════════════════════════════════════════

async def format_rca_report_node(state: AgentState) -> AgentState:
    """Package the RCA output into a structured report."""
    anomaly    = state.get("anomaly",     {})
    rca_result = state.get("rca_result",  {})
    ts         = anomaly.get("timestamp", datetime.now())

    report = {
        "incident_id": f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "timestamp": (
            ts.isoformat() if isinstance(ts, datetime) else str(ts)
        ),
        "severity":               anomaly.get("severity",    "unknown"),
        "anomaly_type":           anomaly.get("anomaly_type","unknown"),
        "trigger_details":        anomaly.get("details",      {}),
        "root_cause":             rca_result.get("root_cause",             {}),
        "evidence":               rca_result.get("evidence",               []),
        "impact_analysis":        rca_result.get("impact_analysis",        {}),
        "resolution_suggestions": rca_result.get("resolution_suggestions", []),
        "preventive_measures":    rca_result.get("preventive_measures",    []),
        "mttd":  state.get("mttd",  0),
        "mttr":  state.get("mttr",  1800),
        "dashboard_url": "",  # disabled
    }

    state["rca_report"]            = "RCA report generated"
    state["rca_report_structured"] = report

    logger.info("RCA report formatted")
    return state


# ══════════════════════════════════════════════════════════════════════
#  Graph factory
# ══════════════════════════════════════════════════════════════════════

def create_rca_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("gather_evidence",  gather_evidence_node)
    workflow.add_node("cross_correlate",  cross_correlate_node)
    workflow.add_node("llm_rca_analysis", llm_rca_analysis_node)
    workflow.add_node("format_rca_report", format_rca_report_node)

    workflow.set_entry_point("gather_evidence")
    workflow.add_edge("gather_evidence",  "cross_correlate")
    workflow.add_edge("cross_correlate",  "llm_rca_analysis")
    workflow.add_edge("llm_rca_analysis", "format_rca_report")
    workflow.add_edge("format_rca_report", END)

    return workflow.compile()


# ══════════════════════════════════════════════════════════════════════
#  Public helper called by SmartMonitor
# ══════════════════════════════════════════════════════════════════════

async def invoke_rca_agent(context: Dict) -> Dict:
    """Build initial state and run the RCA graph."""
    initial_state: AgentState = {
        "intent":                "rca",
        "anomaly":               context.get("anomaly"),
        "available_datasources": context.get("available_datasources", []),
        "datasource_uid":        context.get("datasource_uid",  ""),
        "datasource_type":       context.get("datasource_type", ""),
        "error_pattern":         context.get("error_pattern",   {}),
        "log_patterns":          [],
        "categorized_data":      {},
        "user_query": (
            f"RCA for "
            f"{context.get('anomaly', {}).get('anomaly_type', 'unknown')} anomaly"
        ),
        "llm_retry_count": 0,
        "fallback_mode":   False,
        "conversation_history": [],
        "investigation_steps":  [],
        "tools_used":           [],
        # Grafana disabled — kept empty for schema compat
        "grafana_url":     "",
        "grafana_api_key": "",
    }

    graph  = create_rca_graph()
    result = await graph.ainvoke(initial_state)

    return {
        "rca_report":            result.get("rca_report",            ""),
        "rca_report_structured": result.get("rca_report_structured", {}),
        "dashboard_url":         "",
        "resolution_suggestions": result.get("resolution_suggestions", []),
        "resolved": False,
    }