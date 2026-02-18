"""
# nodes/dashboard_node.py
Dashboard creation node
Generates Grafana dashboard JSON and deploys it
Python 3.12 compatible
"""

import logging
import hashlib
import json
import time
from typing import Optional
from schemas.state import AgentState

logger = logging.getLogger(__name__)


async def dashboard_creation_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Generate and deploy Grafana dashboard.
    Works for both PromQL and SQL query types.
    """
    try:
        # ✅ PRIORITY 1: Try to get from state (passed from RCA context)
        grafana_url = state.get("grafana_url")
        grafana_api_key = state.get("grafana_api_key")
        
        # ✅ PRIORITY 2: Fallback to session state if not in state
        if not grafana_url or not grafana_api_key:
            grafana_url = _get_session("grafana_url")
            grafana_api_key = _get_session("grafana_api_key")

        if not grafana_url or not grafana_api_key:
            state["error"] = "Grafana not configured"
            logger.error("Grafana URL or API key missing from both state and session")
            return state

        generated_query = state.get("generated_query", "")
        query_type      = state.get("query_type", "promql")
        datasource      = state.get("selected_datasource", {})
        user_query      = state.get("user_query", "Dashboard")

        # ✅ FOR RCA: Use dashboard_json if already generated
        dashboard_json = state.get("dashboard_json")
        
        if not dashboard_json:
            # Normal dashboard creation flow
            if not generated_query:
                state["error"] = "No query generated to create dashboard"
                logger.error("No query in state for dashboard creation")
                return state

            # Build dashboard JSON
            dashboard_json = _build_dashboard(
                query=generated_query,
                query_type=query_type,
                datasource=datasource,
                title=user_query[:60],
            )

        # Deploy to Grafana
        dashboard_url = await _deploy(dashboard_json, grafana_url, grafana_api_key)

        state["dashboard_json"] = dashboard_json
        state["dashboard_url"]  = dashboard_url

        logger.info(f"Dashboard deployed: {dashboard_url}")

    except Exception as e:
        logger.error(f"Dashboard creation failed: {e}", exc_info=True)
        state["error"] = f"Dashboard creation failed: {str(e)}"

    return state


# ── Helpers ────────────────────────────────────────────────────────────

def _get_session(key: str) -> str:
    """Safely read from Streamlit session state"""
    try:
        import streamlit as st
        return st.session_state.get(key, "")
    except Exception:
        return ""


def _build_dashboard(
    query:      str,
    query_type: str,
    datasource: dict,
    title:      str,
) -> dict:
    """Build Grafana dashboard JSON"""

    ds_uid  = datasource.get("uid",  "")
    ds_type = datasource.get("type", "prometheus")

    # Map our type names → Grafana plugin IDs
    grafana_type_map = {
        "prometheus": "prometheus",
        "postgresql": "postgres",
        "loki":       "loki",
    }
    grafana_ds_type = grafana_type_map.get(ds_type, ds_type)

    # Panel type based on query type
    panel_type = "table" if query_type == "sql" else "timeseries"

    # Build target (differs by datasource type)
    if query_type == "sql":
        target = {
            "rawSql":  query,
            "format":  "table",
            "refId":   "A",
        }
    else:
        # PromQL or LogQL — NO datasource label inside the query
        target = {
            "expr":    query,
            "refId":   "A",
            "legendFormat": "__auto",
        }

    panel = {
        "id":    1,
        "type":  panel_type,
        "title": title,
        "datasource": {
            "type": grafana_ds_type,
            "uid":  ds_uid,
        },
        "targets": [target],
        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 12},
        "options": {},
        "fieldConfig": {
            "defaults":   {"unit": "short"},
            "overrides":  [],
        },
    }

    # Generate unique UID
    uid = hashlib.md5(f"{query_type}:{query}:{time.time()}".encode()).hexdigest()[:8]

    return {
        "uid":               f"vizgenie-{uid}",
        "title":             f"VizGenie — {title}",
        "tags":              ["vizgenie", "auto-generated"],
        "timezone":          "browser",
        "schemaVersion":     39,
        "version":           0,
        "refresh":           "30s",
        "time":              {"from": "now-1h", "to": "now"},
        "timepicker":        {},
        "panels":            [panel],
        "editable":          True,
        "fiscalYearStartMonth": 0,
        "graphTooltip":      0,
        "links":             [],
        "liveNow":           False,
    }


async def _deploy(
    dashboard_json: dict,
    grafana_url:    str,
    api_key:        str,
) -> str:
    """POST dashboard to Grafana API"""
    import aiohttp

    url     = f"{grafana_url.rstrip('/')}/api/dashboards/db"
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "dashboard": dashboard_json,
        "folderId":  0,
        "overwrite": True,
        "message":   "Auto-generated by VizGenie",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status == 200:
                result = await response.json()
                return f"{grafana_url.rstrip('/')}{result.get('url', '')}"
            else:
                body = await response.text()
                raise RuntimeError(f"Grafana API {response.status}: {body[:200]}")