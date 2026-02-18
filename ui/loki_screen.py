"""
# ui/loki_screen.py
Unified Loki Screen
Single interface: Monitor | Query | Alerts | RCA
"""

import streamlit as st
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def render_loki() -> None:
    """Main Loki screen with 4 tabs"""
    
    st.header("📜 Loki — Intelligent Log Monitoring")
    
    # Check connection
    loki_url = st.session_state.get("loki_url", "")
    if not loki_url:
        st.warning("⚠️ No Loki datasource. Add in **Connections** → **Loki**")
        return
    
    st.caption(f"🟢 Connected: `{loki_url}`")
    st.divider()
    
    # 4 Tabs
    tabs = st.tabs(["🔍 Monitor", "🔎 Query", "⚠️ Alerts", "📋 RCA"])
    
    with tabs[0]:
        render_monitor_tab(loki_url)
    
    with tabs[1]:
        render_query_tab(loki_url)
    
    with tabs[2]:
        render_alerts_tab()
    
    with tabs[3]:
        render_rca_tab()


# ══════════════════════════════════════════════════════════════════════
#  TAB 1: MONITOR
# ══════════════════════════════════════════════════════════════════════

def render_monitor_tab(loki_url: str):
    """Monitor tab: Configure and start monitoring (does pattern learning automatically)"""
    
    st.subheader("🔍 Intelligent Monitoring")
    
    from jobs.smart_monitor import get_monitor
    monitor = get_monitor()
    is_running = monitor.is_running()
    
    # Monitor Configuration
    st.markdown("### ⚙️ Configuration")
    
    col_status, col_interval = st.columns([1, 1])
    
    with col_status:
        if is_running:
            st.success("🟢 Monitor Running")
        else:
            st.info("⚪ Monitor Stopped")
    
    with col_interval:
        interval = st.selectbox("Check Interval", [15, 30, 60], format_func=lambda x: f"{x}s")
    
    st.caption("ℹ️ When you start monitor, it will automatically:")
    st.caption("1. Fetch 50 logs from Loki")
    st.caption("2. Clean and deduplicate")
    st.caption("3. Send to LLM to extract patterns")
    st.caption("4. Save patterns to file")
    st.caption("5. Start monitoring using patterns")
    
    # Start/Stop buttons
    if is_running:
        if st.button("⏹️ Stop Monitor", type="primary", use_container_width=True):
            monitor.stop()
            st.success("✅ Stopped")
            st.rerun()
    else:
        if st.button("▶️ Start Monitor", type="primary", use_container_width=True):
            asyncio.run(start_monitor_with_learning(loki_url, interval))
    
    # Show patterns if learned
    from tools.pattern_extractor import get_pattern_store
    store = get_pattern_store()
    patterns = store.get_patterns()
    
    if patterns:
        st.divider()
        st.markdown("### 📋 Learned Patterns")
        st.caption(f"{len(patterns)} patterns ready")
        
        with st.expander("View Patterns"):
            for p in patterns[:5]:
                st.markdown(f"**{p['error_type']}** → `{p['intent']}`")
                st.caption(f"Regex: `{p['regex'][:60]}...`")
    
    # Monitor stats
    if is_running:
        st.divider()
        st.markdown("### 📊 Monitor Stats")
        stats = monitor.get_stats()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Logs Checked", stats.get("total_logs", 0))
        c2.metric("Errors Found", stats.get("errors_found", 0))
        c3.metric("RCA Generated", stats.get("rca_count", 0))

async def start_monitor_with_learning(loki_url: str, interval: int):
    """Start monitor - does pattern learning first if needed"""
    
    from tools.pattern_extractor import get_pattern_store
    from jobs.smart_monitor import get_monitor
    
    store = get_pattern_store()
    patterns = store.get_patterns()
    
    # Step 1: Try to learn patterns if not already learned
    if not patterns:
        with st.spinner("🧠 Learning patterns from logs..."):
            try:
                success = await learn_patterns_automatically(loki_url, sample_size=50)
                
                if success:
                    st.success(f"✅ Learned {len(store.get_patterns())} error patterns")
                else:
                    st.warning("⚠️ Pattern learning failed - using basic patterns")
                    # Create minimal fallback patterns
                    _create_basic_patterns(store)
            
            except Exception as e:
                logger.error(f"Pattern learning failed: {e}")
                st.warning("⚠️ LLM unavailable - using basic error detection")
                # Create minimal fallback patterns
                _create_basic_patterns(store)
    else:
        st.info(f"✅ Using {len(patterns)} existing patterns")
    
    # Step 2: Start monitor (always works, even without patterns)
    with st.spinner("▶️ Starting monitor..."):
        monitor = get_monitor()
        monitor.start(loki_url, interval)
    
    st.success(f"✅ Monitor started — checking every {interval}s")
    st.rerun()

def _create_basic_patterns(store):
    """Create basic fallback patterns when LLM is unavailable"""
    
    basic_patterns = [
        {
            "error_type": "TypeError",
            "regex": r"TypeError.*",
            "intent": "type_error",
            "extract": {
                "module": r'module["\s:]+(\w+)',
                "function": r'function["\s:]+(\w+)',
            }
        },
        {
            "error_type": "NullPointerError",
            "regex": r"(NullPointer|AttributeError|NoneType).*",
            "intent": "null_reference",
            "extract": {
                "module": r'module["\s:]+(\w+)',
                "function": r'function["\s:]+(\w+)',
            }
        },
        {
            "error_type": "DivisionByZero",
            "regex": r"(ZeroDivision|division by zero).*",
            "intent": "division_error",
            "extract": {
                "module": r'module["\s:]+(\w+)',
            }
        },
        {
            "error_type": "IndexOutOfBounds",
            "regex": r"(IndexError|list index out of range).*",
            "intent": "index_error",
            "extract": {
                "module": r'module["\s:]+(\w+)',
            }
        },
        {
            "error_type": "ConnectionError",
            "regex": r"(Connection|Timeout|DNS).*",
            "intent": "network_failure",
            "extract": {
                "endpoint": r'(https?://[^\s]+)',
            }
        },
        {
            "error_type": "InternalServerError",
            "regex": r"(500|Internal Server|Server Error).*",
            "intent": "server_error",
            "extract": {
                "status_code": r'(\d{3})',
            }
        },
    ]
    
    store.patterns = basic_patterns
    store._save()
    
    logger.info(f"Created {len(basic_patterns)} basic fallback patterns")

async def learn_patterns_automatically(loki_url: str, sample_size: int) -> bool:
    """Learn patterns from logs using LLM"""
    
    from tools.loki_tools import query_loki_logs
    from tools.pattern_extractor import get_pattern_store
    
    with st.spinner(f"Fetching {sample_size} logs..."):
        # Fetch logs
        logs = await query_loki_logs(
            loki_url=loki_url,
            filter='{container=~".+"}',
            time_range="1h",
            limit=sample_size
        )
        
        if not logs:
            st.error("No logs found")
            return False
        
        st.info(f"📦 Fetched {len(logs)} logs")
    
    with st.spinner("Analyzing with LLM..."):
        # Filter errors only
        error_logs = [
            log for log in logs
            if any(kw in log.get("log", "").upper() for kw in ["ERROR", "CRITICAL", "EXCEPTION", "TRACEBACK"])
        ]
        
        if not error_logs:
            st.warning("No ERROR logs found in sample")
            return False
        
        st.info(f"🔍 Found {len(error_logs)} error logs")
        
        # Deduplicate
        unique = deduplicate_logs(error_logs)
        st.info(f"✨ Deduplicated to {len(unique)} unique errors")
        
        # Sample for LLM: 5 full + rest as summary
        sampled = sample_for_llm(unique)
        
        # Extract patterns
        store = get_pattern_store()
        patterns = await store.learn_from_logs(sampled)
        
        if patterns:
            st.success(f"✅ Learned {len(patterns)} error patterns!")
            return True
        else:
            st.error("Failed to learn patterns")
            return False


def deduplicate_logs(logs: list) -> list:
    """Remove duplicates based on normalized signature"""
    import hashlib
    import re
    
    seen = set()
    unique = []
    
    for log in logs:
        text = log.get("log", "")
        
        # Normalize: remove numbers, IDs, timestamps
        norm = re.sub(r'\d+', 'N', text)
        norm = re.sub(r'\b[a-f0-9]{8,}\b', 'ID', norm)
        
        sig = hashlib.md5(norm.encode()).hexdigest()
        
        if sig not in seen:
            seen.add(sig)
            unique.append(log)
    
    return unique


def sample_for_llm(logs: list, full_count: int = 5) -> dict:
    """Prepare logs for LLM: 5 full + rest as summaries"""
    return {
        "full_logs": [log.get("log", "")[:1000] for log in logs[:full_count]],
        "summaries": [
            {
                "error_type": extract_error_type(log.get("log", "")),
                "snippet": log.get("log", "")[:200]
            }
            for log in logs[full_count:]
        ]
    }


def extract_error_type(text: str) -> str:
    """Quick error type extraction"""
    for err in ["TypeError", "ValueError", "NullPointerError", "ConnectionError",
                "TimeoutError", "DatabaseError", "ServiceUnavailable", "InternalServerError"]:
        if err in text:
            return err
    return "UnknownError"


# ══════════════════════════════════════════════════════════════════════
#  TAB 2: QUERY
# ══════════════════════════════════════════════════════════════════════

def render_query_tab(loki_url: str):
    """Manual log query"""
    
    st.subheader("🔎 Manual Query")
    
    with st.form("query_form"):
        logql = st.text_input("LogQL Filter", '{container=~".+"}')
        
        col1, col2 = st.columns(2)
        time_range = col1.selectbox("Time Range", ["5m", "15m", "1h", "6h"], index=2)
        limit = col2.slider("Limit", 10, 200, 50)
        
        if st.form_submit_button("🔍 Query", use_container_width=True):
            asyncio.run(execute_query(loki_url, logql, time_range, limit))


async def execute_query(loki_url: str, logql: str, time_range: str, limit: int):
    """Execute and display query results"""
    
    from tools.loki_tools import query_loki_logs
    
    with st.spinner("Querying..."):
        logs = await query_loki_logs(loki_url, logql, time_range, limit)
    
    if not logs:
        st.warning("No logs found")
        return
    
    st.success(f"✅ Found {len(logs)} logs")
    
    for i, log in enumerate(logs[:30]):
        # Format timestamp properly
        timestamp = log.get('timestamp', 'N/A')
        if isinstance(timestamp, (int, float)):
            from datetime import datetime
            timestamp_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp_str = str(timestamp)[:19]
        
        with st.expander(f"Log {i+1} — {timestamp_str}"):
            st.code(log.get("log", ""), language="text")


# ══════════════════════════════════════════════════════════════════════
#  TAB 3: ALERTS - FIXED
# ══════════════════════════════════════════════════════════════════════

def render_alerts_tab():
    """Show active alerts grouped by error type"""
    
    st.subheader("⚠️ Active Alerts")
    
    from tools.error_analyzer import get_error_analyzer
    analyzer = get_error_analyzer()
    error_patterns = sorted(analyzer.patterns.values(), key=lambda p: p.occurrence_count, reverse=True)
    
    if not error_patterns:
        st.info("✨ No active alerts")
        return
    
    total = sum(p.occurrence_count for p in error_patterns)
    st.metric("Total Errors", total)
    
    # Display grouped alerts
    for pattern in error_patterns:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.markdown(f"### {pattern.error_type} ×{pattern.occurrence_count}")
                st.caption(f"Error Code: `{pattern.error_code or 'N/A'}`")
                st.caption(f"Message: {pattern.error_message[:100]}...")
                
                # Show affected endpoints
                if pattern.affected_endpoints:
                    st.caption(f"Endpoints: `{', '.join(pattern.affected_endpoints[:3])}`")
            
            with col2:
                st.write("")  # spacing
                
                # ✅ ADD: Manual RCA trigger button
                if st.button("🔬 Generate RCA", key=f"rca_{pattern.pattern_id}"):
                    asyncio.run(trigger_manual_rca(pattern))
                
                if st.button("View Details", key=f"alert_{pattern.pattern_id}"):
                    st.session_state["view_alert_pattern"] = pattern.pattern_id
                    st.rerun()
    
    # Show details if clicked
    if "view_alert_pattern" in st.session_state:
        show_alert_details(st.session_state["view_alert_pattern"], analyzer)


async def trigger_manual_rca(error_pattern):
    """Manually trigger RCA for an error pattern"""
    
    st.info(f"🔬 Generating RCA for {error_pattern.error_type}...")
    
    from jobs.smart_monitor import get_monitor
    monitor = get_monitor()
    
    # Use monitor's RCA trigger function
    await monitor._trigger_rca(error_pattern)
    
    st.success(f"✅ RCA generated! Check RCA Reports tab.")
    st.rerun()

def show_alert_details(pattern_id: str, analyzer):
    """Show all occurrences of an error pattern"""
    
    pattern = analyzer.patterns.get(pattern_id)
    if not pattern:
        return
    
    st.divider()
    st.markdown(f"### 📋 {pattern.error_type} — All Details")
    
    st.markdown(f"**First Seen:** {pattern.first_seen.strftime('%Y-%m-%d %H:%M:%S')}")
    st.markdown(f"**Last Seen:** {pattern.last_seen.strftime('%Y-%m-%d %H:%M:%S')}")
    st.markdown(f"**Total Occurrences:** {pattern.occurrence_count}")
    
    st.markdown("**Error Message:**")
    st.code(pattern.error_message, language="text")
    
    if pattern.stack_trace:
        st.markdown("**Stack Trace:**")
        st.code(pattern.stack_trace, language="python")
    
    st.markdown("**Affected Endpoints:**")
    for endpoint in pattern.affected_endpoints[:10]:
        st.caption(f"- {endpoint}")
    
    st.markdown("**Sample Logs:**")
    for i, sample in enumerate(pattern.sample_logs[:5], 1):
        with st.expander(f"Sample {i}"):
            st.code(sample.get("log", ""), language="text")

def render_rca_tab():
    """Show RCA reports - Executive Summary Format"""
    
    st.subheader("📋 Root Cause Analysis Reports")
    st.caption("🎯 Single-pane executive view: What happened → Why → How to fix → Who to contact")
    
    from utils.streamlit_notifier import get_rca_store
    from tools.error_analyzer import get_error_analyzer
    
    rca_store = get_rca_store()
    reports = rca_store.get_all()
    
    if not reports:
        st.info("✨ No RCA reports yet - monitoring active")
        return
    
    st.metric("Total Incidents Analyzed", len(reports))
    
    # Get error analyzer for pattern details
    analyzer = get_error_analyzer()
    
    # Show reports in executive format
    for i, report in enumerate(reports[:20]):
        error_type = report.get("error_type", "Unknown")
        error_code = report.get("error_code", "N/A")
        pattern_id = report.get("pattern_id", "")
        timestamp = report.get("timestamp", "")[:16].replace("T", " ")
        
        # Get pattern from analyzer
        pattern = analyzer.patterns.get(pattern_id) if pattern_id else None
        
        rca = report.get("rca", {})
        rca_structured = rca.get("rca_report_structured", {})
        root_cause = rca_structured.get("root_cause", {})
        
        # Determine severity
        severity = rca_structured.get("severity", "medium")
        severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        icon = severity_icons.get(severity, "🟡")
        
        # Get essential data
        category = root_cause.get('category', 'code')
        component = root_cause.get('component', 'Unknown')
        description = root_cause.get('description', '')
        
        # ✅ FALLBACK: If description is empty, generate from pattern data
        if not description and pattern:
            description, category, component = _generate_executive_summary(pattern, error_type)
        
        with st.expander(f"{icon} **{error_type}** — {timestamp}", expanded=(i == 0)):
            
            # ══════════════════════════════════════════════════════════
            # 🎯 EXECUTIVE SUMMARY (Single Pane of Glass)
            # ══════════════════════════════════════════════════════════
            
            st.markdown("## 🎯 Executive Summary")
            
            with st.container(border=True):
                # What Happened
                st.markdown("### ❓ What Happened")
                st.error(f"**{error_type}** error occurred {pattern.occurrence_count if pattern else 1} time(s)")
                st.markdown(f"**Error Code:** `{error_code}`")
                st.markdown(f"**First Detected:** {pattern.first_seen.strftime('%Y-%m-%d %H:%M:%S') if pattern else 'Unknown'}")
                
                if pattern and pattern.affected_endpoints:
                    st.markdown(f"**Impact:** {len(pattern.affected_endpoints)} endpoint(s) affected")
                    st.caption(f"Affected: {', '.join(pattern.affected_endpoints[:3])}")
                
                st.divider()
                
                # Why It Happened
                st.markdown("### 🔍 Why It Happened")
                st.info(description if description else "Analyzing root cause...")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Category", category.upper())
                with col2:
                    st.metric("Component", component)
                with col3:
                    confidence = root_cause.get('confidence_score', 0.8)
                    st.metric("Confidence", f"{float(confidence)*100:.0f}%")
                
                st.divider()
                
                # Where to Look
                st.markdown("### 📍 Where to Look")
                
                if pattern and pattern.stack_trace:
                    # Extract file and line number from stack trace
                    import re
                    file_match = re.search(r'File "([^"]+)", line (\d+)', pattern.stack_trace)
                    if file_match:
                        file_path = file_match.group(1)
                        line_num = file_match.group(2)
                        function_match = re.search(r'in (\w+)', pattern.stack_trace)
                        function = function_match.group(1) if function_match else 'unknown'
                        
                        st.code(f"""
📂 File: {file_path}
📍 Line: {line_num}
⚙️  Function: {function}()
                        """, language="text")
                    else:
                        st.code(pattern.stack_trace[:300], language="python")
                else:
                    st.warning("Stack trace not available")
                
                st.divider()
                
                # How to Fix
                st.markdown("### ✅ How to Fix")
                
                suggestions = rca_structured.get('resolution_suggestions', [])
                
                if suggestions:
                    for idx, sug in enumerate(suggestions[:1], 1):  # Show first suggestion prominently
                        st.markdown(f"**Step {idx}: {sug.get('suggestion', 'Fix error')}**")
                        
                        implementation = sug.get('implementation', '')
                        if implementation:
                            st.code(implementation, language="text")
                        
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.caption(f"⏱️ Time: {sug.get('estimated_time', '30 min')}")
                        with col_b:
                            st.caption(f"⚠️ Risk: {sug.get('risk_level', 'low').upper()}")
                        with col_c:
                            st.caption(f"🎯 Type: {sug.get('type', 'code').upper()}")
                else:
                    # ✅ FALLBACK: Generate fix from error type
                    fix_guide = _generate_fix_guide(error_type, pattern)
                    st.code(fix_guide, language="text")
                
                st.divider()
                
                # Who to Contact
                st.markdown("### 📞 Who to Contact")
                
                contact = root_cause.get('contact_team', '')
                if not contact:
                    contact = _determine_contact_team(category, component)
                
                st.success(f"**👥 Contact:** {contact}")
                
                # If there are resolution suggestions, show contact from first one
                if suggestions and suggestions[0].get('contact'):
                    st.info(f"**Specific Owner:** {suggestions[0]['contact']}")
            
            # ══════════════════════════════════════════════════════════
            # 📊 DETAILED BREAKDOWN (Expandable Sections)
            # ══════════════════════════════════════════════════════════
            
            st.markdown("---")
            st.markdown("## 📊 Detailed Analysis")
            
            # Occurrence Timeline
            if pattern:
                with st.container(border=True):
                    st.markdown("#### ⏱️ Occurrence Timeline")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Count", pattern.occurrence_count)
                    with col2:
                        st.metric("First Seen", pattern.first_seen.strftime('%H:%M:%S'))
                    with col3:
                        st.metric("Last Seen", pattern.last_seen.strftime('%H:%M:%S'))
                    with col4:
                        duration = (pattern.last_seen - pattern.first_seen).total_seconds()
                        if duration < 60:
                            dur_str = f"{duration:.0f}s"
                        elif duration < 3600:
                            dur_str = f"{duration/60:.0f}m"
                        else:
                            dur_str = f"{duration/3600:.1f}h"
                        st.metric("Duration", dur_str)
            
            # Error Details
            if pattern:
                with st.container(border=True):
                    st.markdown("#### 🐛 Full Error Message")
                    st.code(pattern.error_message, language="text")
                    
                    if pattern.affected_modules:
                        st.markdown("**Affected Modules:**")
                        for module in pattern.affected_modules:
                            st.caption(f"• {module}")
            
            # Complete Stack Trace
            if pattern and pattern.stack_trace:
                with st.container(border=True):
                    st.markdown("#### 🔬 Complete Stack Trace")
                    st.code(pattern.stack_trace, language="python")
            
            # Sample Logs
            if pattern and pattern.sample_logs:
                with st.container(border=True):
                    st.markdown(f"#### 📜 Sample Error Logs ({len(pattern.sample_logs)})")
                    for idx, sample in enumerate(pattern.sample_logs[:2], 1):
                        st.caption(f"**Sample {idx}:**")
                        log_text = sample.get("log", "") if isinstance(sample, dict) else str(sample)
                        st.code(log_text[:500], language="json")
            
            # All Resolution Steps
            if len(suggestions) > 1:
                with st.container(border=True):
                    st.markdown("#### ✅ All Resolution Steps")
                    for idx, sug in enumerate(suggestions, 1):
                        priority = sug.get('priority', 'medium')
                        p_icons = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
                        
                        st.markdown(f"{p_icons.get(priority, '⚪')} **Step {idx}:** {sug.get('suggestion', 'N/A')}")
                        st.caption(f"Priority: {priority.upper()} | Type: {sug.get('type', 'N/A').upper()}")


def _generate_executive_summary(pattern, error_type: str) -> tuple:
    """Generate executive summary when RCA data is missing"""
    
    error_message = pattern.error_message if pattern else "Unknown error"
    stack_trace = pattern.stack_trace if pattern else ""
    affected_modules = pattern.affected_modules if pattern else []
    
    # ✅ FIX: Handle None stack trace
    if not stack_trace:
        stack_trace = ""
    
    # Extract file and line
    import re
    file_match = re.search(r'File "([^"]+)", line (\d+)', stack_trace) if stack_trace else None
    line_num = file_match.group(2) if file_match else "unknown"
    file_path = file_match.group(1) if file_match else (affected_modules[0] if affected_modules else "unknown file")
    
    function_match = re.search(r'in (\w+)', stack_trace) if stack_trace else None
    function_name = function_match.group(1) if function_match else "unknown function"
    
    error_lower = error_type.lower()
    
    if 'type' in error_lower:
        category = 'code'
        component = f"{file_path} → {function_name}()"
        description = f"""
    **Type Mismatch Error**

    The application attempted to combine incompatible data types (string + integer) at line {line_num} in {function_name}().

    **Root Cause:** Python cannot concatenate a string with an integer without explicit type conversion.

    **Exact Location:** `{file_path}`, line {line_num}

    **What the code tried to do:** Combine text with a number directly
    **Why it failed:** Python requires explicit conversion using str() or formatting
    """
        
    elif 'null' in error_lower or 'none' in error_lower:
        category = 'code'
        component = f"{file_path} → {function_name}()"
        description = f"""
    **Null Reference Error**

    The application tried to call a method on an object that was None/null at line {line_num} in {function_name}().

    **Root Cause:** An object was not properly initialized or a function returned None unexpectedly.

    **Exact Location:** `{file_path}`, line {line_num}

    **What the code tried to do:** Call a method on an object
    **Why it failed:** The object was None/null instead of a valid instance
    """
        
    elif 'division' in error_lower or 'zero' in error_lower:
        category = 'code'
        component = f"{file_path} → {function_name}()"
        description = f"""
    **Division by Zero Error**

    The application attempted to divide by zero at line {line_num} in {function_name}().

    **Root Cause:** A calculation used a denominator value of 0, which is mathematically undefined.

    **Exact Location:** `{file_path}`, line {line_num}

    **What the code tried to do:** Perform a division operation
    **Why it failed:** The denominator (bottom number) was zero
    """
        
    elif 'index' in error_lower or 'bound' in error_lower:
        category = 'code'
        component = f"{file_path} → {function_name}()"
        description = f"""
    **Array Index Out of Bounds**

    The application tried to access an array/list element that doesn't exist at line {line_num}.

    **Root Cause:** Attempted to access index position beyond array size.

    **Exact Location:** `{file_path}`, line {line_num}

    **What the code tried to do:** Access a list/array element
    **Why it failed:** The index was larger than the array size
    """
        
    elif 'connection' in error_lower or 'reset' in error_lower:
        category = 'infrastructure'
        component = "External Service / Network"
        description = f"""
    **Network Connection Failure**

    The application's network connection was interrupted or reset.

    **Root Cause:** Connection to external service was lost or reset by remote host.

    **Possible Causes:**
    - External service closed the connection unexpectedly
    - Network instability or packet loss
    - Firewall or load balancer reset the connection
    - Service restarted during the request
    - Connection timeout

    **Location:** {function_name}() attempted external call
    """
        
    elif 'timeout' in error_lower or 'dns' in error_lower:
        category = 'infrastructure'
        component = "External Service / Network"
        description = f"""
    **Network Timeout or DNS Failure**

    The application failed to connect to an external service within the timeout period.

    **Root Cause:** {error_message}

    **Possible Causes:**
    - External service is down or unavailable
    - Network connectivity issue
    - DNS resolution failure
    - Request timeout due to slow response
    - Firewall blocking the connection

    **Location:** {function_name}() attempted external call
    """
        
    else:
        category = 'code'
        component = f"{file_path} → {function_name}()"
        description = f"""
    **Application Error: {error_type}**

    {error_message}

    **Location:** `{file_path}`, line {line_num} in {function_name}()

    **Requires Investigation:** Review stack trace and recent code changes to determine exact cause.
    """
    
    return description, category, component

def _generate_fix_guide(error_type: str, pattern) -> str:
    """Generate fix guide when resolution suggestions are missing"""
    
    if not pattern:
        return "Error analysis in progress..."
    
    stack_trace = pattern.stack_trace if pattern.stack_trace else ""
    
    # ✅ FIX: Handle empty stack trace
    if not stack_trace:
        line_num = "XXX"
        file_path = "unknown"
        function_name = "unknown"
    else:
        import re
        
        file_match = re.search(r'File "([^"]+)", line (\d+)', stack_trace)
        line_num = file_match.group(2) if file_match else "XXX"
        file_path = file_match.group(1) if file_match else "unknown"
        
        function_match = re.search(r'in (\w+)', stack_trace)
        function_name = function_match.group(1) if function_match else "unknown"
    
    error_lower = error_type.lower()
    
    if 'type' in error_lower:
        return f"""FIX STEPS:

    1. Open file: {file_path}
    2. Go to line: {line_num}
    3. Find where string and integer are combined
    4. Add type conversion:
    
    WRONG: result = "string" + 123
    RIGHT: result = "string" + str(123)
    
    5. Test the fix
    6. Deploy to production

    Time: 5-10 minutes
    Risk: Low
    """
        
    elif 'null' in error_lower or 'none' in error_lower:
        return f"""FIX STEPS:   

    1. Open file: {file_path}
    2. Go to line: {line_num}
    3. Add null check BEFORE calling method:
    
    if obj is not None:
        result = obj.some_method()
    else:
        logger.error("Object is None")
        result = default_value
    
    4. Find WHY obj is None - check initialization
    5. Test thoroughly
    6. Deploy

    Time: 15-20 minutes
    Risk: Low
    """
        
    elif 'division' in error_lower or 'zero' in error_lower:
        return f"""FIX STEPS:

    1. Open file: {file_path}
    2. Go to line: {line_num}
    3. Add zero-check BEFORE division:
    
    if denominator != 0:
        result = numerator / denominator
    else:
        logger.error("Division by zero")
        result = 0  # or raise error
    
    4. Find why denominator is zero
    5. Add input validation
    6. Test and deploy

    Time: 10-15 minutes
    Risk: Low
    """
        
    elif 'index' in error_lower or 'bound' in error_lower:
        return f"""FIX STEPS:

    1. Open file: {file_path}
    2. Go to line: {line_num}
    3. Add bounds check:
    
    if 0 <= index < len(array):
        value = array[index]
    else:
        logger.error(f"Index {{index}} out of bounds")
        value = default
    
    4. Test with different array sizes
    5. Deploy

    Time: 10 minutes
    Risk: Low
    """
        
    elif 'connection' in error_lower or 'reset' in error_lower:
        return f"""FIX STEPS:

    1. Investigate connection stability
    - Check if external service is up
    - Review connection pool settings
    
    2. Add connection retry logic:
    for attempt in range(3):
        try:
            response = make_request()
            break
        except ConnectionReset:
            if attempt < 2:
                time.sleep(1)
                continue
            raise
    
    3. Increase connection timeout if needed
    4. Add connection pool health checks
    5. Monitor connection metrics

    Time: 30 minutes
    Risk: Low
    """
        
    elif 'timeout' in error_lower or 'dns' in error_lower:
        return f"""FIX STEPS:

    1. Check external service health status
    2. Verify network connectivity
    3. Test DNS resolution
    4. Increase timeout if needed:
    timeout = 30  # increase from 10s
    
    5. Add retry logic:
    for retry in range(3):
        try:
            response = call_api()
            break
        except Timeout:
            time.sleep(2 ** retry)
    
    6. Contact external service provider if down

    Time: 30-60 minutes
    Risk: Medium
    """
        
    else:
        if stack_trace:
            return f"""Review stack trace and fix at:
    File: {file_path}
    Line: {line_num}
    Function: {function_name}()

    Check recent code changes and add proper error handling.
    """
        else:
            return f"""ERROR: {error_type}

    Stack trace not available. 
    Review error logs and recent code changes to locate the issue.

    1. Check application logs for more details
    2. Review recent deployments
    3. Add error tracking/logging if missing
    """

def _determine_contact_team(category: str, component: str) -> str:
    """Determine who to contact based on error category"""
    
    contacts = {
        'code': 'Backend Development Team',
        'database': 'Database Administration Team + Backend Team',
        'infrastructure': 'DevOps Team + Infrastructure Team',
        'api': 'Integration Team + External API Provider',
        'cache': 'Backend Team + Infrastructure Team',
        'config': 'DevOps Team + Platform Team',
    }
    
    team = contacts.get(category, 'Engineering Team')
    
    # Add component-specific contact
    if 'main' in component.lower():
        team += ' → Main Application Owner'
    elif 'api' in component.lower():
        team += ' → API Team'
    
    return team
