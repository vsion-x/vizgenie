"""
# ui/monitor_screen.py
Monitor Screen — Clean, Management-Ready Interface
"""

import asyncio
import logging
import re
from datetime import datetime

import streamlit as st

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════

def render_monitor_screen() -> None:
    st.header("Monitor & Root Cause Analysis")
    st.caption("Real-time error detection and automated RCA generation")

    from tools.log_source_manager import get_log_source_registry
    registry = get_log_source_registry()
    sources  = registry.list_sources()

    if not sources:
        st.warning("⚠️ No log sources configured. Add at least one source in the **Log Sources** page.")
        return

    st.caption(f"🟢 Monitoring {len(sources)} log source(s)")
    st.divider()

    tabs = st.tabs(["🔍 Monitor", "⚠️ Alerts", "📋 RCA Reports"])

    with tabs[0]:
        _render_monitor_tab()
    with tabs[1]:
        _render_alerts_tab()
    with tabs[2]:
        _render_rca_tab()


# ══════════════════════════════════════════════════════════════════════
#  Tab 1 — Monitor
# ══════════════════════════════════════════════════════════════════════

def _render_monitor_tab() -> None:
    st.subheader("Intelligent Log Monitoring")

    from jobs.smart_monitor        import get_monitor
    from tools.pattern_extractor   import get_pattern_store

    monitor    = get_monitor()
    is_running = monitor.is_running()
    store      = get_pattern_store()
    patterns   = store.get_patterns()

    col_status, col_interval = st.columns([1, 1])

    with col_status:
        if is_running:
            st.success("🟢 Monitor Running")
        else:
            st.info("⚪ Monitor Stopped")

    with col_interval:
        interval = st.selectbox("Check Interval", options=[15, 20, 30, 60], index=1, format_func=lambda x: f"{x}s")

    st.markdown("### Pattern Learning")

    if patterns:
        st.success(f"✅ {len(patterns)} patterns learned and ready")
        with st.expander("View Learned Patterns"):
            for p in patterns[:10]:
                st.markdown(f"**{p['error_type']}** → `{p['intent']}`")
                st.caption(f"Regex: `{p['regex'][:70]}…`")
    else:
        st.warning("⚠️ No patterns learned yet")

    col_learn, col_clear = st.columns([2, 1])

    with col_learn:
        if st.button("🧠 Learn Patterns from Logs", use_container_width=True):
            asyncio.run(_learn_patterns())

    with col_clear:
        if patterns and st.button("🗑️ Clear Patterns", use_container_width=True):
            store.patterns = []
            store._save()
            st.success("Patterns cleared")
            st.rerun()

    st.divider()
    st.markdown("### Monitor Control")

    if is_running:
        if st.button("⏹️ Stop Monitor", type="primary", use_container_width=True):
            monitor.stop()
            st.success("✅ Monitor stopped")
            st.rerun()
    else:
        start_disabled = not patterns
        if st.button("▶️ Start Monitor", type="primary", use_container_width=True, disabled=start_disabled):
            monitor.start(interval)
            st.success(f"✅ Monitor started")
            st.rerun()
        if start_disabled:
            st.caption("💡 Learn patterns first, then start the monitor.")

    if is_running:
        st.divider()
        st.markdown("### Stats")
        stats = monitor.get_stats()
        c1, c2, c3 = st.columns(3)
        c1.metric("Logs Checked", stats.get("total_logs", 0))
        c2.metric("Errors Found", stats.get("errors_found", 0))
        c3.metric("RCA Generated", stats.get("rca_count", 0))


# ══════════════════════════════════════════════════════════════════════
#  Tab 2 — ALERTS
# ══════════════════════════════════════════════════════════════════════

def _render_alerts_tab() -> None:
    st.subheader("Active Alerts")
    st.caption("Real-time error tracking grouped by type")

    from tools.error_analyzer import get_error_analyzer
    analyzer = get_error_analyzer()
    
    # Group patterns by error_type to avoid duplicates
    patterns_by_type = {}
    for pattern in analyzer.patterns.values():
        error_type = pattern.error_type
        if error_type not in patterns_by_type:
            patterns_by_type[error_type] = {
                "pattern": pattern,
                "total_count": 0,
                "instances": []
            }
        patterns_by_type[error_type]["total_count"] += pattern.occurrence_count
        patterns_by_type[error_type]["instances"].append(pattern)
    
    # Sort by total count
    sorted_errors = sorted(
        patterns_by_type.items(),
        key=lambda x: x[1]["total_count"],
        reverse=True
    )
    
    if not sorted_errors:
        st.info("✨ No active alerts — system healthy")
        return
    
    # Total errors metric
    total = sum(data["total_count"] for _, data in sorted_errors)
    st.metric("Total Error Occurrences", total)
    
    st.divider()
    
    # Display unique error types (no duplicates)
    for error_type, data in sorted_errors:
        # Pick the most recent instance as representative
        representative = max(data["instances"], key=lambda p: p.last_seen)
        
        with st.expander(f"{_severity_icon(representative)} **{error_type}** × {data['total_count']}", expanded=False):
            
            # Clean header
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Occurrences", data['total_count'])
            
            with col2:
                st.metric("First Seen", representative.first_seen.strftime("%Y-%m-%d %H:%M:%S"))
            
            with col3:
                st.metric("Last Seen", representative.last_seen.strftime("%Y-%m-%d %H:%M:%S"))
            
            st.divider()
            
            # Error details
            st.markdown("**Error Message:**")
            clean_message = _extract_clean_message(representative.error_message)
            st.code(clean_message, language="text")
            
            # Affected components
            if representative.affected_endpoints or representative.affected_modules:
                st.markdown("**Affected Components:**")
                if representative.affected_endpoints:
                    st.caption(f"Endpoints: {', '.join(representative.affected_endpoints[:3])}")
                if representative.affected_modules:
                    st.caption(f"Modules: {', '.join(representative.affected_modules[:3])}")
            
            st.divider()
            
            # Actions
            col_a, col_b = st.columns(2)
            
            with col_a:
                if st.button("🔬 Generate RCA", key=f"rca_{representative.pattern_id}", use_container_width=True):
                    asyncio.run(_trigger_manual_rca(representative))
            
            with col_b:
                if st.button("✖ Dismiss", key=f"dismiss_{representative.pattern_id}", use_container_width=True):
                    st.info("Pattern dismissed (feature coming soon)")


def _extract_clean_message(raw_message: str) -> str:
    """Extract clean error message from JSON log format"""
    try:
        import json
        if raw_message.startswith('{"log"'):
            parsed = json.loads(raw_message)
            inner_log = parsed.get("log", "")
            if inner_log.startswith("{"):
                inner_parsed = json.loads(inner_log)
                return inner_parsed.get("message", raw_message)
        return raw_message[:200]
    except:
        return raw_message[:200]


def _severity_icon(pattern) -> str:
    t = pattern.error_type.lower()
    if any(x in t for x in ["memory", "oom", "fatal", "critical", "deadlock"]):
        return "🔴"
    if any(x in t for x in ["database", "connection", "timeout", "null"]):
        return "🟠"
    if pattern.occurrence_count >= 10:
        return "🟠"
    return "🟡"


async def _trigger_manual_rca(error_pattern) -> None:
    from jobs.smart_monitor import get_monitor
    monitor = get_monitor()
    sig = f"{error_pattern.error_type}|{error_pattern.pattern_id}"
    monitor.seen_errors.discard(sig)

    with st.spinner(f"Generating RCA for {error_pattern.error_type}…"):
        await monitor._trigger_rca(error_pattern)

    st.success("✅ RCA generated — check the RCA Reports tab")
    st.rerun()


# ══════════════════════════════════════════════════════════════════════
#  Tab 3 — RCA REPORTS (Management-Ready Format)
# ══════════════════════════════════════════════════════════════════════

def _render_rca_tab() -> None:
    st.subheader("Root Cause Analysis Reports")
    st.caption("Executive summaries for management review")

    from utils.streamlit_notifier import get_rca_store
    from tools.error_analyzer     import get_error_analyzer

    rca_store = get_rca_store()
    reports   = rca_store.get_all()
    analyzer  = get_error_analyzer()

    if not reports:
        st.info("✨ No RCA reports yet — monitor is watching for errors")
        return

    st.metric("Total Incidents Analyzed", len(reports))
    st.divider()

    # ✅ FIX: Use index to create unique keys
    for report_idx, report in enumerate(reports[:20]):
        error_type = report.get("error_type", "Unknown")
        pattern_id = report.get("pattern_id", "")
        timestamp  = report.get("timestamp", "")[:16].replace("T", " ")

        pattern = analyzer.patterns.get(pattern_id) if pattern_id else None
        rca = report.get("rca", {})
        rca_structured = rca.get("rca_report_structured", {})
        root_cause = rca_structured.get("root_cause", {})

        with st.container(border=True):
            st.markdown(f"### {error_type} — {timestamp}")
            # ✅ Pass unique index to avoid duplicate keys
            _render_executive_rca(error_type, pattern, root_cause, rca_structured, report_idx)


def _render_executive_rca(error_type, pattern, root_cause, rca_structured, report_idx):
    """Render clean, management-ready RCA report"""
    
    # ✅ Create unique key using report_idx
    unique_key = f"rca_{report_idx}"
    
    # ══════════════════════════════════════════════════════════════════
    # 📊 KEY METRICS (Top)
    # ══════════════════════════════════════════════════════════════════
    
    st.markdown("#### 📊 Incident Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Error Type", error_type)
    
    with col2:
        if pattern:
            st.metric("Occurrences", pattern.occurrence_count)
        else:
            st.metric("Occurrences", 1)
    
    with col3:
        if pattern:
            duration = (pattern.last_seen - pattern.first_seen).total_seconds()
            if duration < 60:
                dur_str = f"{duration:.0f}s"
            elif duration < 3600:
                dur_str = f"{duration/60:.0f}m"
            else:
                dur_str = f"{duration/3600:.1f}h"
            st.metric("Duration", dur_str)
        else:
            st.metric("Duration", "N/A")
    
    with col4:
        severity = rca_structured.get("severity", "medium")
        st.metric("Severity", severity.upper())
    
    st.divider()
    
    # ══════════════════════════════════════════════════════════════════
    # ❓ WHAT HAPPENED
    # ══════════════════════════════════════════════════════════════════
    
    st.markdown("#### ❓ What Happened")
    
    if pattern:
        clean_msg = _extract_clean_message(pattern.error_message)
        st.write(clean_msg)
        
        if pattern.affected_endpoints:
            st.caption(f"**Affected Endpoints:** {', '.join(pattern.affected_endpoints[:3])}")
        
        if pattern.affected_modules:
            st.caption(f"**Affected Modules:** {', '.join(pattern.affected_modules[:3])}")
    else:
        st.write("Error details not available")
    
    st.divider()
    
    # ══════════════════════════════════════════════════════════════════
    # 🔍 WHY IT HAPPENED
    # ══════════════════════════════════════════════════════════════════
    
    st.markdown("#### 🔍 Why It Happened")
    
    description = root_cause.get("description", "")
    category = root_cause.get("category", "code")
    component = root_cause.get("component", "Unknown")
    
    if description:
        st.info(description)
    else:
        st.warning("Root cause analysis pending")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.caption(f"**Category:** {category.upper()}")
    with col_b:
        st.caption(f"**Component:** {component}")
    
    st.divider()
    
    # ══════════════════════════════════════════════════════════════════
    # 📍 WHERE TO LOOK
    # ══════════════════════════════════════════════════════════════════
    
    st.markdown("#### 📍 Where to Look")
    
    if pattern and pattern.stack_trace:
        file_match = re.search(r'File "([^"]+)", line (\d+)', pattern.stack_trace)
        func_match = re.search(r"in (\w+)", pattern.stack_trace)
        
        if file_match:
            file_path = file_match.group(1)
            line_num = file_match.group(2)
            function = func_match.group(1) if func_match else "unknown"
            
            st.code(f"""File: {file_path}
Line: {line_num}
Function: {function}()""", language="text")
        else:
            st.code(pattern.stack_trace[:300], language="python")
    else:
        st.caption("Stack trace not available")
    
    st.divider()
    
    # ══════════════════════════════════════════════════════════════════
    # ✅ HOW TO FIX
    # ══════════════════════════════════════════════════════════════════
    
    st.markdown("#### ✅ How to Fix")
    
    suggestions = rca_structured.get("resolution_suggestions", [])
    
    if suggestions:
        for idx, sug in enumerate(suggestions[:1], 1):
            st.markdown(f"**Fix #{idx}: {sug.get('suggestion', 'Fix error')}**")
            
            implementation = sug.get('implementation', '')
            if implementation:
                if isinstance(implementation, list):
                    implementation = "\n".join(implementation)
                st.code(implementation, language="text")
            
            col_x, col_y, col_z = st.columns(3)
            with col_x:
                st.caption(f"⏱️ Time: {sug.get('estimated_time', '30 min')}")
            with col_y:
                st.caption(f"⚠️ Risk: {sug.get('risk_level', 'low').upper()}")
            with col_z:
                st.caption(f"👤 Owner: {sug.get('contact', 'Engineering Team')}")
    else:
        st.caption("Fix instructions pending")
    
    st.divider()
    
    # ══════════════════════════════════════════════════════════════════
    # 📞 WHO TO CONTACT
    # ══════════════════════════════════════════════════════════════════
    
    st.markdown("#### 📞 Who to Contact")
    
    contact = root_cause.get("contact_team", "Engineering Team")
    st.success(f"**Responsible Team:** {contact}")
    
    st.divider()
    
    # ══════════════════════════════════════════════════════════════════
    # 📋 TECHNICAL DETAILS (Toggle with unique key)
    # ══════════════════════════════════════════════════════════════════
    
    # ✅ FIX: Use unique_key for buttons
    show_key = f"show_details_{unique_key}"
    hide_key = f"hide_details_{unique_key}"
    state_key = f"details_visible_{unique_key}"
    
    if not st.session_state.get(state_key, False):
        if st.button("📋 Show Full Technical Details", key=show_key, use_container_width=True):
            st.session_state[state_key] = True
            st.rerun()
    else:
        if pattern:
            st.markdown("##### Timeline")
            st.caption(f"**First Seen:** {pattern.first_seen.strftime('%Y-%m-%d %H:%M:%S')}")
            st.caption(f"**Last Seen:** {pattern.last_seen.strftime('%Y-%m-%d %H:%M:%S')}")
            st.caption(f"**Total Occurrences:** {pattern.occurrence_count}")
            
            st.divider()
            
            st.markdown("##### Full Error Message")
            st.code(pattern.error_message[:500], language="text")
            
            if pattern.stack_trace:
                st.divider()
                st.markdown("##### Complete Stack Trace")
                st.code(pattern.stack_trace, language="python")
            
            if pattern.sample_logs:
                st.divider()
                st.markdown("##### Sample Logs")
                for idx, sample in enumerate(pattern.sample_logs[:2], 1):
                    log_text = sample.get("log", "") if isinstance(sample, dict) else str(sample)
                    clean_log = _extract_clean_message(log_text)
                    st.caption(f"**Sample {idx}:**")
                    st.code(clean_log, language="json")
        
        if st.button("📋 Hide Technical Details", key=hide_key, use_container_width=True):
            st.session_state[state_key] = False
            st.rerun()


# ══════════════════════════════════════════════════════════════════════
#  Pattern Learning Helpers
# ══════════════════════════════════════════════════════════════════════

async def _learn_patterns() -> None:
    from tools.log_source_manager import get_log_source_registry
    from tools.pattern_extractor  import get_pattern_store
    
    registry = get_log_source_registry()
    store    = get_pattern_store()
    
    with st.spinner("Fetching logs..."):
        logs = await registry.fetch_all_logs(time_range="1h", filters=None, limit=100)
    
    if not logs:
        st.error("❌ No logs found")
        return
    
    st.info(f"📦 Fetched {len(logs)} logs")
    
    error_logs = [
        log for log in logs
        if any(kw in log.get("log", "").upper() for kw in ("ERROR", "CRITICAL", "EXCEPTION"))
    ]
    
    if not error_logs:
        st.warning("⚠️ No ERROR logs found")
        return
    
    st.info(f"🔍 Found {len(error_logs)} error logs")
    
    unique = _deduplicate_logs(error_logs)
    st.info(f"✨ Deduplicated to {len(unique)} unique errors")
    
    sampled = _sample_for_llm(unique)
    
    with st.spinner("Analyzing with LLM..."):
        patterns = await store.learn_from_logs(sampled)
    
    if patterns:
        st.success(f"✅ Learned {len(patterns)} patterns!")
    else:
        st.error("Failed to learn patterns")
    
    st.rerun()


def _deduplicate_logs(logs: list) -> list:
    import hashlib
    seen = set()
    unique = []
    for log in logs:
        text = log.get("log", "")
        norm = re.sub(r"\d+", "N", text)
        norm = re.sub(r"\b[a-f0-9]{8,}\b", "ID", norm, flags=re.IGNORECASE)
        sig = hashlib.md5(norm.encode()).hexdigest()
        if sig not in seen:
            seen.add(sig)
            unique.append(log)
    return unique


def _sample_for_llm(logs: list, full_count: int = 5) -> dict:
    return {
        "full_logs": [log.get("log", "")[:1000] for log in logs[:full_count]],
        "summaries": [
            {"error_type": _quick_error_type(log.get("log", "")), "snippet": log.get("log", "")[:200]}
            for log in logs[full_count:]
        ],
    }


def _quick_error_type(text: str) -> str:
    for err in [
        "TypeError", "ValueError", "NullPointerError", "AttributeError",
        "ConnectionError", "TimeoutError", "DatabaseError",
        "ServiceUnavailable", "InternalServerError", "DivisionByZero",
        "IndexError", "ZeroDivisionError", "BadGateway"
    ]:
        if err in text:
            return err
    return "UnknownError"