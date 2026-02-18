"""
# ui/query_interface.py
Query interface — single input box + datasource selector
Loki screen is separate (sidebar nav)
Python 3.12 compatible
"""

import streamlit as st
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _run_async(coro):
    """
    Run async coroutine in Streamlit thread-safe way
    """
    try:
        # Try to get existing loop
        loop = asyncio.get_running_loop()
        # We're in an async context - use run_coroutine_threadsafe
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=60)
    except RuntimeError:
        # No running loop - create new one with asyncio.run()
        return asyncio.run(coro)


def render_query_interface() -> None:
    """Dashboard creation — Prometheus + PostgreSQL only"""

    st.header("✨ Create Dashboard")

    # Only non-Loki datasources
    datasources = [
        ds for ds in st.session_state.get("available_datasources", [])
        if ds.get("type") != "loki"
    ]

    if not datasources:
        st.warning("⚠️ No Prometheus or PostgreSQL datasources available. Add them in **Connections**.")
        return

    # ── Single input + single datasource selector ──────────────────────
    with st.form("query_form"):

        query = st.text_input(
            "Describe what you want to visualize",
            placeholder="e.g. Show CPU usage over the last hour",
        )

        ds_options = {f"{ds['name']} ({ds['type']})": ds for ds in datasources}
        ds_choice  = st.selectbox("Datasource", list(ds_options.keys()))

        submitted = st.form_submit_button("✨ Generate Dashboard", use_container_width=True)

        if submitted:
            if not query.strip():
                st.warning("Please enter a query")
                return

            selected_ds = ds_options[ds_choice]

            with st.spinner("🔍 Generating dashboard..."):
                result = _run_async(
                    _invoke_graph(query.strip(), selected_ds,
                                  st.session_state.get("available_datasources", []))
                )

            if result:
                _display_result(result)


async def _invoke_graph(
    user_query:            str,
    selected_datasource:   dict,
    available_datasources: list[dict],
) -> Optional[dict]:
    """Invoke supervisor graph to generate dashboard"""
    try:
        from graphs.supervisor_graph import create_supervisor_graph

        graph = create_supervisor_graph()
        state = {
            "user_query":            user_query,
            "selected_datasource":   selected_datasource,
            "available_datasources": available_datasources,
            "conversation_history":  [],
            "llm_retry_count":       0,
            "fallback_mode":         False,
            "investigation_steps":   [],
            "tools_used":            [],
        }
        
        result = await graph.ainvoke(state)
        return result

    except Exception as e:
        logger.error(f"Graph invocation failed: {e}", exc_info=True)
        st.error(f"❌ Dashboard generation failed: {e}")
        return None


def _display_result(result: dict) -> None:
    """Display dashboard generation result"""
    if result.get("error"):
        st.error(f"❌ {result['error']}")
        return

    url = result.get("dashboard_url", "")
    if url:
        st.success(f"✅ Dashboard created successfully!")
        st.markdown(f"### [📊 Open Dashboard in Grafana]({url})")
    else:
        st.warning("⚠️ Dashboard was generated but URL is missing")

    if result.get("fallback_mode"):
        st.info("ℹ️ Rule-based fallback was used (LLM temporarily unavailable)")
    
    # Show generated query for debugging
    if result.get("generated_query"):
        with st.expander("🔍 View Generated Query"):
            query_type = result.get("query_type", "unknown")
            st.code(result["generated_query"], language="sql" if query_type == "sql" else "promql")