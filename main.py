# main.py
# Main entry point for VizGenie with LangGraph

import streamlit as st
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="VizGenie - Agentic AI",
    layout="wide",
    page_icon="🎩"
)

from dotenv import load_dotenv
import os
from datetime import datetime

# Import handlers
from handlers.prometheus_handler import PrometheusHandler
from handlers.postgres_handler import PostgresHandler
from handlers.grafana_handler import GrafanaHandler
from handlers.vectordb_handler import VectorDBHandler

# Import workflow
from agents.workflow import VizGenieWorkflow
from state.graph_state import VizGenieState, ProcessingStage, QueryContext

import requests
import psycopg2

# Load environment variables
load_dotenv()


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    defaults = {
        'grafana_url': '',
        'grafana_api_key': '',
        'prometheus_url': '',
        'postgres_url': '',
        'grafana_tested': False,
        'prometheus_tested': False,
        'postgres_tested': False,
        'workflow_state': None,
        'execution_logs': [],
        'current_stage': None
    }
    
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


# Styling
st.markdown("""
    <style>
    .stApp {
        background-color: #f8f9fa;
    }
    
    .stSidebar {
        background-color: #ffffff !important;
        border-right: 1px solid #e9ecef !important;
    }
    
    div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea {
        background-color: #ffffff !important;
        color: #2c3e50 !important;
        border-color: #dee2e6 !important;
    }

    .stButton button {
        background-color: #4CAF50 !important;
        color: white !important;
        border: 1px solid #45a049 !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }

    .stButton button:hover {
        background-color: #45a049 !important;
        transform: translateY(-1px);
        box-shadow: 0 2px 6px rgba(0,0,0,0.1) !important;
    }
    
    .stage-box {
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid;
    }
    
    .stage-initialized { border-color: #007bff; background-color: #e7f3ff; }
    .stage-processing { border-color: #ffc107; background-color: #fff8e1; }
    .stage-completed { border-color: #28a745; background-color: #d4edda; }
    .stage-failed { border-color: #dc3545; background-color: #f8d7da; }
    
    h1, h2, h3, h4, h5, h6 { color: #2c3e50 !important; }
    p, div, span { color: #495057 !important; }
    </style>
""", unsafe_allow_html=True)


def test_grafana_connection(url, api_key):
    """Test Grafana connection"""
    try:
        response = requests.get(
            f"{url}/api/datasources",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5
        )
        return response.status_code == 200
    except Exception:
        return False


def test_prometheus_connection(url):
    """Test Prometheus connection"""
    try:
        response = requests.get(f"{url}/api/v1/status/config", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def test_postgres_connection(url):
    """Test PostgreSQL connection"""
    try:
        conn = psycopg2.connect(url)
        conn.close()
        return True
    except Exception:
        return False


def credential_section():
    """Display credential input sections"""
    st.header("🔐 Connection Settings")

    # Grafana Connection
    with st.expander("📊 **Grafana Configuration**", expanded=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.session_state.grafana_url = st.text_input(
                "Grafana URL",
                value=st.session_state.grafana_url,
                placeholder="http://your-grafana-url:3000"
            )
        
        with col2:
            st.session_state.grafana_api_key = st.text_input(
                "API Key",
                type="password",
                value=st.session_state.grafana_api_key,
                placeholder="glsa_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            )
        
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔒 Test", key="test_grafana"):
                if test_grafana_connection(st.session_state.grafana_url, st.session_state.grafana_api_key):
                    st.session_state.grafana_tested = True
                    st.success("✓ Connected")
                else:
                    st.session_state.grafana_tested = False
                    st.error("✗ Failed")

    # Prometheus Connection
    with st.expander("📈 **Prometheus Configuration**", expanded=True):
        cols = st.columns([4, 1])
        with cols[0]:
            st.session_state.prometheus_url = st.text_input(
                "Prometheus URL",
                value=st.session_state.prometheus_url,
                placeholder="http://your-prometheus-url:9090"
            )
        with cols[1]:
            if st.button("✅ Test", key="test_prometheus"):
                if test_prometheus_connection(st.session_state.prometheus_url):
                    st.session_state.prometheus_tested = True
                    st.success("✓ Connected")
                else:
                    st.session_state.prometheus_tested = False
                    st.error("✗ Failed")

    # PostgreSQL Connection
    with st.expander("🗄️ **PostgreSQL Configuration**", expanded=True):
        cols = st.columns([4, 1])
        with cols[0]:
            st.session_state.postgres_url = st.text_input(
                "PostgreSQL Connection",
                value=st.session_state.postgres_url,
                placeholder="postgresql://user:pass@host:port/db"
            )
        with cols[1]:
            if st.button("✅ Test", key="test_postgres"):
                if test_postgres_connection(st.session_state.postgres_url):
                    st.session_state.postgres_tested = True
                    st.success("✓ Connected")
                else:
                    st.session_state.postgres_tested = False
                    st.error("✗ Failed")

    # Status indicators
    st.divider()
    status_cols = st.columns(3)
    status_style = "padding: 12px; border-radius: 8px; text-align: center; margin: 8px 0; font-size: 14px;"
    
    statuses = [
        ("Grafana", st.session_state.grafana_tested),
        ("Prometheus", st.session_state.prometheus_tested),
        ("PostgreSQL", st.session_state.postgres_tested)
    ]
    
    for col, (name, status) in zip(status_cols, statuses):
        with col:
            color = '#e8f5e9' if status else '#f8d7da'
            icon = "✅" if status else "❌"
            st.markdown(
                f"<div style='{status_style} background-color: {color};'>"
                f"<b>{name}:</b> {icon}</div>",
                unsafe_allow_html=True
            )


def display_datasources(datasources):
    """Display available datasources"""
    st.subheader("🔌 Connected Datasources")
    cols = st.columns(min(3, len(datasources)))
    for idx, ds in enumerate(datasources):
        with cols[idx % 3]:
            with st.expander(f"{ds['type'].upper()}: {ds['name']}", expanded=False):
                st.markdown(f"""
                **UID:** `{ds['uid']}`  
                **Type:** {ds.get('type', 'N/A')}  
                **Name:** {ds.get('name', 'N/A')}
                """)


def handle_metric_management(datasources, prometheus_handler, vectordbs_handler):
    """Metric management section"""
    if st.button("🔄 Refresh All Metrics", help="Update metrics from all Prometheus datasources"):
        with st.spinner("Updating metrics..."):
            success_count = 0
            for ds in [d for d in datasources if d['name'] == 'prometheus']:
                try:
                    count = prometheus_handler.fetch_metrics_data(ds, vectordbs_handler)
                    if count >= 0:
                        success_count += 1
                except Exception as e:
                    st.error(f"Failed to update {ds['name']}: {str(e)}")
            
            if success_count > 0:
                st.success(f"✅ Updated {success_count} datasource(s)")


def display_workflow_progress(state: VizGenieState):
    """Display workflow progress and logs"""
    if not state:
        return
    
    st.subheader("🤖 Agent Workflow Progress")
    
    # Stage mapping
    stage_info = {
        ProcessingStage.INITIALIZED: ("🎬", "Initialized", "initialized"),
        ProcessingStage.INTENT_EXTRACTED: ("🧠", "Intent Extracted", "processing"),
        ProcessingStage.METRICS_EXTRACTED: ("📊", "Metrics Extracted", "processing"),
        ProcessingStage.SIMILARITY_SEARCHED: ("🔍", "Vector Search Complete", "processing"),
        ProcessingStage.QUERY_GENERATED: ("⚡", "Queries Generated", "processing"),
        ProcessingStage.QUERY_VALIDATED: ("✅", "Queries Validated", "processing"),
        ProcessingStage.DASHBOARD_GENERATED: ("🎨", "Dashboard Generated", "processing"),
        ProcessingStage.DEPLOYED: ("🚀", "Deployed to Grafana", "completed"),
        ProcessingStage.FAILED: ("❌", "Failed", "failed"),
    }
    
    current_stage = state.get('current_stage')
    if current_stage:
        icon, label, stage_class = stage_info.get(current_stage, ("⏳", "Processing", "processing"))
        st.markdown(
            f"<div class='stage-box stage-{stage_class}'>"
            f"<strong>{icon} Current Stage:</strong> {label}"
            f"</div>",
            unsafe_allow_html=True
        )
    
    # Display execution logs
    if state.get('execution_log'):
        with st.expander("📝 Execution Logs", expanded=True):
            for log in state['execution_log'][-10:]:  # Show last 10 logs
                st.text(f"[{log.get('timestamp', '')}] {log.get('agent', '')}: {log.get('message', '')}")
    
    # Display errors
    if state.get('errors'):
        with st.expander("⚠️ Errors", expanded=True):
            for error in state['errors']:
                st.error(f"Stage: {error.get('stage', 'unknown')} - {error.get('error', 'Unknown error')}")


def create_dashboard_with_workflow(queries, datasources, handlers):
    """Create dashboard using LangGraph workflow"""
    # Initialize workflow
    workflow = VizGenieWorkflow(handlers)
    workflow.compile_graph()
    
    # Prepare query contexts
    user_queries = []
    for query_text, ds_name in queries:
        if not query_text:
            continue
        
        ds = next((d for d in datasources if d['name'] == ds_name), None)
        if not ds:
            st.error(f"Datasource '{ds_name}' not found!")
            continue
        
        user_queries.append({
            "query_text": query_text,
            "datasource_name": ds_name,
            "datasource_uid": ds['uid'],
            "datasource_type": ds.get('type', ds['name']),
            "query_type": "prometheus" if ds['name'] == 'prometheus' else "postgres"
        })
    
    if not user_queries:
        st.warning("No valid queries to process")
        return
    
    # Prepare initial state
    initial_state = {
        "user_queries": user_queries,
        "grafana_url": st.session_state.grafana_url,
        "grafana_api_key": st.session_state.grafana_api_key,
        "prometheus_url": st.session_state.prometheus_url,
        "postgres_url": st.session_state.postgres_url,
        "available_datasources": datasources,
        "current_stage": ProcessingStage.INITIALIZED,
        "current_query_index": 0,
        "metrics_contexts": [],
        "generated_queries": [],
        "dashboard_spec": None,
        "deployment_result": None,
        "errors": [],
        "retry_count": 0,
        "max_retries": 3,
        "execution_log": [],
        "start_time": None,
        "end_time": None
    }
    
    # Create progress container
    progress_container = st.container()
    
    with st.spinner("🤖 Agentic workflow in progress..."):
        # Stream workflow execution
        for output in workflow.stream(initial_state):
            # Update progress display
            with progress_container:
                for node_name, node_state in output.items():
                    st.session_state.workflow_state = node_state
                    display_workflow_progress(node_state)
    
    # Display final results
    final_state = st.session_state.workflow_state
    
    if final_state and final_state.get('current_stage') == ProcessingStage.DEPLOYED:
        st.success("🎉 Dashboard successfully created!")
        
        if final_state.get('deployment_result'):
            result = final_state['deployment_result']
            st.markdown(f"### 🔗 [View Dashboard in Grafana]({result.get('url', '')})")
        
        # Show summary
        with st.expander("📊 Workflow Summary", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Queries Processed", len(final_state.get('generated_queries', [])))
            with col2:
                st.metric("Panels Created", len(final_state.get('dashboard_spec', {}).get('panels', [])))
            with col3:
                start = final_state.get('start_time')
                end = final_state.get('end_time')
                if start and end:
                    duration = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
                    st.metric("Duration", f"{duration:.2f}s")
    
    elif final_state and final_state.get('current_stage') == ProcessingStage.FAILED:
        st.error("❌ Workflow failed. Please check the errors above.")


def main():
    """Main application flow"""
    initialize_session_state()
    
    st.title("🎩 VizGenie - Agentic AI Dashboard Generator")
    st.markdown("Transform natural language into Grafana dashboards using LangGraph agents!")
    
    # Credential section
    credential_section()
    
    # Check connections
    required_connections = ['grafana_tested', 'prometheus_tested', 'postgres_tested']
    if not all(st.session_state.get(conn, False) for conn in required_connections):
        st.warning("⚠️ Please configure and test all connections to continue")
        return
    
    # Initialize handlers
    handlers = {
        'prometheus': PrometheusHandler(st.session_state.prometheus_url),
        'postgres': PostgresHandler(st.session_state.postgres_url),
        'grafana': GrafanaHandler(st.session_state.grafana_url, st.session_state.grafana_api_key),
        'vectordb': VectorDBHandler()
    }
    
    # Fetch datasources
    datasources = handlers['grafana'].fetch_datasources()
    if not datasources:
        st.warning("⚠️ No datasources found in Grafana!")
        return
    
    display_datasources(datasources)
    handle_metric_management(datasources, handlers['prometheus'], handlers['vectordb'])
    
    # Dashboard creation form
    st.header("🚀 Create Dashboard with AI Agents")
    
    with st.form("dashboard_form"):
        queries = []
        for i in range(2):
            cols = st.columns([4, 1])
            with cols[0]:
                query = st.text_input(
                    f"Query {i+1}",
                    placeholder="Describe your visualization in plain English...",
                    key=f"query_{i}"
                )
            with cols[1]:
                ds_name = st.selectbox(
                    f"DS {i+1}",
                    options=[ds['name'] for ds in datasources],
                    key=f"ds_{i}"
                )
            queries.append((query, ds_name))
        
        if st.form_submit_button("✨ Generate Dashboard with Agents", use_container_width=True):
            create_dashboard_with_workflow(queries, datasources, handlers)


if __name__ == "__main__":
    main()