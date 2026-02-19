"""
# main.py
VizGenie v2.0 — AI-Powered Log Intelligence Platform
"""

import streamlit as st
from pathlib import Path

from utils.logger           import setup_logging
from utils.credentials_store import load_credentials

# ══════════════════════════════════════════════════════════════════════
#  App Configuration
# ══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="VizGenie — Log Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

setup_logging()
load_credentials()


# ══════════════════════════════════════════════════════════════════════
#  Clean Minimal CSS
# ══════════════════════════════════════════════════════════════════════

def _inject_custom_css():
    st.markdown("""
    <style>
    /* Remove all default padding and margins */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 3rem;
        padding-right: 3rem;
    }
    
    /* Clean sidebar */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
        padding: 1rem;
    }
    
    [data-testid="stSidebar"] h1 {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
        color: #1a1a1a;
    }
    
    /* Remove excessive borders on containers */
    div[data-testid="stVerticalBlock"] > div {
        background-color: transparent;
        border: none;
        padding: 0;
        box-shadow: none;
    }
    
    /* Clean button style */
    .stButton > button {
        background-color: #0066cc;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    .stButton > button:hover {
        background-color: #0052a3;
    }
    
    /* Simple input fields */
    .stTextInput input {
        border: 1px solid #d0d0d0;
        border-radius: 4px;
    }
    
    /* Clean tabs - no background boxes */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background-color: transparent;
        border-bottom: 1px solid #e0e0e0;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        padding: 0.75rem 1.5rem;
        color: #666;
        font-weight: 500;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #0066cc;
    }
    
    .stTabs [aria-selected="true"] {
        color: #0066cc;
        border-bottom: 2px solid #0066cc;
    }
    
    /* Remove expander borders */
    .streamlit-expanderHeader {
        background-color: transparent;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
    }
    
    /* Simple metrics */
    [data-testid="metric-container"] {
        background-color: transparent;
        border: none;
        padding: 0.5rem 0;
    }
    
    /* Clean headers */
    h1, h2, h3 {
        color: #1a1a1a;
    }
    
    h1 {
        font-size: 1.75rem;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        font-size: 1.25rem;
        margin-bottom: 0.5rem;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.875rem;
        font-weight: 500;
        margin: 0.5rem 0;
    }
    
    .status-connected {
        background-color: #e7f5e9;
        color: #2e7d32;
    }
    
    .status-disconnected {
        background-color: #fdecea;
        color: #c62828;
    }
    
    .status-running {
        background-color: #e3f2fd;
        color: #1565c0;
    }
    
    /* Remove divider margins */
    hr {
        margin: 1rem 0;
        border: none;
        border-top: 1px solid #e0e0e0;
    }
    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  Sidebar Navigation
# ══════════════════════════════════════════════════════════════════════

def _render_sidebar() -> None:
    with st.sidebar:
        st.title("🔍 VizGenie")
        st.caption("AI-Powered Log Intelligence")
        st.divider()
        
        # Navigation menu
        page = st.radio(
            "Navigation",
            ["🔌 Connection", "📜 Log Sources", "🔍 Monitor & RCA"],
            label_visibility="collapsed"
        )
        
        st.session_state["active_page"] = page
        
        st.divider()
        
        # System Status
        st.subheader("System Status")
        
        # Groq status
        if st.session_state.get("groq_validated"):
            st.markdown('<div class="status-badge status-connected">✓ Groq Connected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-badge status-disconnected">✗ Groq Not Connected</div>', unsafe_allow_html=True)
        
        # Log sources status
        from tools.log_source_manager import get_log_source_registry
        registry = get_log_source_registry()
        sources = registry.list_sources()
        st.metric("Active Log Sources", len(sources))
        
        # Monitor status
        from jobs.smart_monitor import get_monitor
        monitor = get_monitor()
        
        if monitor.is_running():
            st.markdown('<div class="status-badge status-running">Monitor Running</div>', unsafe_allow_html=True)
            stats = monitor.get_stats()
            st.metric("Logs Checked", f"{stats.get('total_logs', 0):,}")
            st.metric("RCAs Generated", stats.get('rca_count', 0))
        else:
            st.markdown('<div class="status-badge status-disconnected">Monitor Stopped</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  Page 1: Connection (Groq API)
# ══════════════════════════════════════════════════════════════════════

def _render_connection_page():
    st.title("Connection Settings")
    st.caption("Configure Groq API for AI-powered log analysis")
    
    st.divider()
    
    # Groq API Key
    st.subheader("Groq API Key")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        groq_key = st.text_input(
            "API Key",
            type="password",
            value=st.session_state.get("groq_api_key", ""),
            placeholder="gsk_...",
            help="Get your free API key from console.groq.com",
            label_visibility="collapsed"
        )
    
    with col2:
        if st.button("Validate", use_container_width=True, type="primary"):
            _validate_groq(groq_key)
    
    if st.session_state.get("groq_validated"):
        st.success("✓ Groq API key validated successfully")
    
    st.divider()
    
    # Info
    st.info("""
    **Get your Groq API Key:**
    1. Visit [console.groq.com](https://console.groq.com)
    2. Create a free account
    3. Generate an API key
    4. Paste it above and click Validate
    """)


def _validate_groq(key: str) -> None:
    """Validate Groq API key"""
    from utils.validators import validate_groq_key
    
    valid, err = validate_groq_key(key)
    if not valid:
        st.error(f"❌ {err}")
        return
    
    try:
        from llm.retry_handler import initialize_llm_handler
        initialize_llm_handler(key.split(","))
        
        st.session_state["groq_api_key"] = key
        st.session_state["groq_validated"] = True
        
        from utils.credentials_store import save_credentials
        save_credentials()
        
        st.rerun()
    except Exception as exc:
        st.error(f"❌ {exc}")


# ══════════════════════════════════════════════════════════════════════
#  Page 2: Log Sources
# ══════════════════════════════════════════════════════════════════════

def _render_log_sources_page():
    if not st.session_state.get("groq_validated"):
        st.warning("⚠️ Please configure Groq API in Connection page first")
        return
    
    from ui.log_sources import render_log_sources
    render_log_sources()


# ══════════════════════════════════════════════════════════════════════
#  Page 3: Monitor & RCA
# ══════════════════════════════════════════════════════════════════════

def _render_monitor_page():
    if not st.session_state.get("groq_validated"):
        st.warning("⚠️ Please configure Groq API in Connection page first")
        return
    
    from tools.log_source_manager import get_log_source_registry
    registry = get_log_source_registry()
    
    if not registry.list_sources():
        st.warning("⚠️ Please add at least one log source in Log Sources page")
        return
    
    from ui.monitor_screen import render_monitor_screen
    render_monitor_screen()


# ══════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    _inject_custom_css()
    _render_sidebar()
    
    # Route to appropriate page based on sidebar selection
    page = st.session_state.get("active_page", "🔌 Connection")
    
    if page == "🔌 Connection":
        _render_connection_page()
    elif page == "📜 Log Sources":
        _render_log_sources_page()
    elif page == "🔍 Monitor & RCA":
        _render_monitor_page()


if __name__ == "__main__":
    main()