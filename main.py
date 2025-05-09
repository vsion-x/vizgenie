import streamlit as st

st.set_page_config(
    page_title="VizGenie",
    layout="wide",
    page_icon="🎩"
)

from dotenv import load_dotenv
from handlers.prometheus_handler import PrometheusHandler
from handlers.postgres_handler import PostgresHandler
from handlers.grafana_handler import GrafanaHandler
from handlers.vectordb_handler import VectorDBHandler
from llm import prompt
import requests
import psycopg2

# Load environment variables
load_dotenv()

# Initialize session state variables if not already set
if "prometheus_url" not in st.session_state:
    st.session_state.prometheus_url = ""  # or set a default like "http://localhost:9090"

if "postgres_url" not in st.session_state:
    st.session_state.postgres_url = ""

if "grafana_url" not in st.session_state:
    st.session_state.grafana_url = ""

if "grafana_api_key" not in st.session_state:
    st.session_state.grafana_api_key = ""

def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if 'metrics_labels' not in st.session_state:
        st.session_state.metrics_labels = {}
    if 'dummy_loaded' not in st.session_state:
        st.session_state.dummy_loaded = False
    
    # Initialize connection statuses
    st.session_state.setdefault('grafana_tested', False)
    st.session_state.setdefault('prometheus_tested', False)
    st.session_state.setdefault('postgres_tested', False)
    
    # Initialize credential fields
    st.session_state.setdefault('grafana_url', '')
    st.session_state.setdefault('grafana_api_key', '')
    st.session_state.setdefault('prometheus_url', '')
    st.session_state.setdefault('postgres_url', '')


# Update your existing CSS with these additions
st.markdown("""
    <style>
    /* Main page background */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Sidebar navigation */
    .stSidebar {
        background-color: #ffffff !important;
        border-right: 1px solid #e9ecef !important;
    }
    
    /* Text input fields */
    div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea {
        background-color: #ffffff !important;
        color: #2c3e50 !important;
        border-color: #dee2e6 !important;
    }

    /* Dashboard success message styling */
    div[data-testid="stSuccess"] > div {
        background-color: #e8f4fc !important;
        border: 1px solid #c2e0ff !important;
        color: #2c3e50 !important;
        border-radius: 8px;
        padding: 1rem;
    }

    /* Dropdown styling */
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border-color: #dee2e6 !important;
    }
    div[data-baseweb="popover"] div {
        background-color: #ffffff !important;
        color: #2c3e50 !important;
    }

    /* Corrected and verified button styling */
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

    .stButton button:active {
        background-color: #3d8b40 !important;
        transform: translateY(0) !important;
    }

    /* Metric management buttons */
    div[data-testid="stExpander"] div[role="button"] {
        background-color: #4a90e2 !important;
        color: white !important;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }

    /* Status indicators */
    .status-box {
        padding: 1rem;
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* Text elements */
    h1, h2, h3, h4, h5, h6 {
        color: #2c3e50 !important;
    }
    p, div, span {
        color: #495057 !important;
    }

    /* Form styling */
    .stForm {
        border: 1px solid #e9ecef !important;
        border-radius: 8px;
        padding: 1rem;
        background-color: #ffffff !important;
    }

    /* Select box hover state */
    div[role="listbox"] div:hover {
        background-color: #f8f9fa !important;
    }
    
    /* Connection status badges */
    .connection-status {
        background-color: #f1f3f5 !important;
        border: 1px solid #dee2e6 !important;
    }
    /* Specific styling for query input boxes only */
    div[data-testid="stForm"] .stTextInput input {
        background-color: #ffffff !important;
        border: 2px solid #e0e0e0 !important;
        border-radius: 8px !important;
        padding: 0.8rem 1rem !important;
        font-size: 14px !important;
        color: #2c3e50 !important;
        transition: all 0.3s ease !important;
    }

    div[data-testid="stForm"] .stTextInput input:focus {
        border-color: #4CAF50 !important;
        box-shadow: 0 0 0 3px rgba(76,175,80,0.1) !important;
    }

    div[data-testid="stForm"] .stTextInput input:hover {
        border-color: #bdbdbd !important;
    }

    /* Preserve original select box styling */
    div[data-testid="stForm"] .stSelectbox div[data-baseweb="select"] {
        background-color: #ffffff !important;
        border-color: #dee2e6 !important;
    }
            
    /* Dashboard generation button styling */
    div[data-testid="stForm"] button {
        background-color: #4CAF50 !important;
        color: white !important;
        border: 1px solid #45a049 !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
        padding: 1rem !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    div[data-testid="stForm"] button:hover {
        background-color: #45a049 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15) !important;
    }

    div[data-testid="stForm"] button:active {
        background-color: #3d8b40 !important;
        transform: translateY(0) !important;
    }
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
    """Display credential input sections with visible cursor and proper status"""
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
            st.markdown("<br>", unsafe_allow_html=True)  # Vertical alignment
            if st.button("**🔒 Test Connection**", key="test_grafana"):
                if test_grafana_connection(st.session_state.grafana_url, st.session_state.grafana_api_key):
                    st.session_state.grafana_tested = True
                    st.success("Credentials verified!")
                else:
                    st.session_state.grafana_tested = False
                    st.error("Connection failed")

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
            if st.button("**✅ Test Connection**", key="test_prometheus"):
                if test_prometheus_connection(st.session_state.prometheus_url):
                    st.session_state.prometheus_tested = True
                    st.success("Connection successful!")
                else:
                    st.session_state.prometheus_tested = False
                    st.error("Connection failed")

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
            if st.button("**✅ Test Connection**", key="test_postgres"):
                if test_postgres_connection(st.session_state.postgres_url):
                    st.session_state.postgres_tested = True
                    st.success("Connection established!")
                else:
                    st.session_state.postgres_tested = False
                    st.error("Connection failed")

    # Status indicators
    st.divider()
    status_cols = st.columns(3)
    status_style = """
        padding: 12px; 
        border-radius: 8px; 
        text-align: center; 
        margin: 8px 0;
        font-size: 14px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    """
    
    with status_cols[0]:
        status = "✅ Active" if st.session_state.grafana_tested else "❌ Offline"
        st.markdown(f"<div style='{status_style} background-color: {'#e8f5e9' if st.session_state.grafana_tested else '#f8d7da'};'><b>Grafana:</b> {status}</div>", unsafe_allow_html=True)
    
    with status_cols[1]:
        status = "✅ Active" if st.session_state.prometheus_tested else "❌ Offline"
        st.markdown(f"<div style='{status_style} background-color: {'#e8f5e9' if st.session_state.prometheus_tested else '#f8d7da'};'><b>Prometheus:</b> {status}</div>", unsafe_allow_html=True)
    
    with status_cols[2]:
        status = "✅ Active" if st.session_state.postgres_tested else "❌ Offline"
        st.markdown(f"<div style='{status_style} background-color: {'#e8f5e9' if st.session_state.postgres_tested else '#f8d7da'};'><b>PostgreSQL:</b> {status}</div>", unsafe_allow_html=True)

def display_datasources(datasources):
    """Display available datasources in formatted way"""
    st.subheader("🔌 Connected Datasources")
    cols = st.columns(3)
    for idx, ds in enumerate(datasources):
        with cols[idx % 3]:
            with st.expander(f"{ds['type'].upper()}: {ds['name']}", expanded=False):
                st.markdown(f"""
                **UID:** `{ds['uid']}`  
                **URL:** {ds.get('url', 'N/A')}  
                **Database:** {ds.get('database', 'N/A')}
                """)


# Update metric management section
def handle_metric_management(datasources, prometheus_handler, vectordbs_handler):
    """Metric management section with button styling"""
    if st.button("🔄 Refresh All Metrics", 
                key="refresh_metrics",
                help="Update metrics from all Prometheus datasources"):
        with st.spinner("Updating metrics across all Prometheus datasources..."):
            success_count = 0
            error_count = 0
            print("here")
            print(datasources)
            for ds in [d for d in datasources if str.lower(d['name']) == 'prometheus']:
                try:
                    count = prometheus_handler.fetch_metrics_data(ds, vectordbs_handler)
                    if count > 0:
                        success_count += 1
                except Exception as e:
                    error_count += 1
                    st.error(f"Failed to update {ds['name']}: {str(e)}")
            
            if success_count > 0:
                st.success(f"Successfully updated {success_count} datasources")
            if error_count > 0:
                st.error(f"Failed to update {error_count} datasources")


# Initialize handlers
prometheus_handler = PrometheusHandler(st.session_state.prometheus_url)
postgres_handler = PostgresHandler(st.session_state.postgres_url)
grafana_handler = GrafanaHandler(st.session_state.grafana_url, st.session_state.grafana_api_key)
vectordbs_handler = VectorDBHandler()
def main():
    """Main application flow"""
    initialize_session_state()
    
    st.title("🎩 VizGenie - Natural Language to Dashboard")
    st.markdown("Transform natural language queries into Grafana dashboards with AI magic!")
    
    # Credential section
    credential_section()
    
    # Check connections with proper session state initialization
    required_connections = ['grafana_tested', 'prometheus_tested', 'postgres_tested']
    if not all(st.session_state.get(conn, False) for conn in required_connections):
        st.markdown("""
        <div class="status-box">
            ⚠️ Please configure and test all connections to continue
        </div>
        """, unsafe_allow_html=True)
        return
    
    print("All connections are valid.")
    print("Grafana URL:", st.session_state.grafana_url)
    print("Prometheus URL:", st.session_state.prometheus_url)
    print("PostgreSQL URL:", st.session_state.postgres_url)


    
    # Load dummy data if not loaded
    if not st.session_state.dummy_loaded:
        with st.spinner("Loading initial metrics..."):
            vectordbs_handler.store_metrics([f"dummy_metric_{i}" for i in range(1, 11)], "sample-datasource-uid")
            st.session_state.dummy_loaded = True

    # Fetch and display datasources
    datasources = grafana_handler.fetch_datasources()
    if not datasources:
        st.warning("⚠️ No datasources found in Grafana!")
        st.stop()
    
    display_datasources(datasources)
    handle_metric_management(datasources, prometheus_handler, vectordbs_handler)

    # Dashboard creation form
    st.header("🚀 Create New Dashboard")
    with st.form("main_form"):
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
                    f"Datasource {i+1}",
                    options=[ds['name'] for ds in datasources],
                    key=f"ds_{i}"
                )
            queries.append((query, ds_name))

        if st.form_submit_button("✨ Generate Dashboard", use_container_width=True):
            process_queries(queries, datasources)
def process_queries(queries, datasources):
    """Process queries through appropriate handlers"""
    processed_responses = []
    
    for query_text, ds_name in queries:
        if not query_text:
            continue
            
        # Find matching datasource
        datasource = next((ds for ds in datasources if ds['name'] == ds_name), None)
        if not datasource:
            st.error(f"🔴 Datasource '{ds_name}' not found!")
            continue

        try:
            if datasource['name'] == 'prometheus':
                response = handle_prometheus_query(query_text, datasource)
            elif datasource['name'] == 'postgresql':
                response = handle_postgres_query(query_text, datasource)
            else:
                st.warning(f"Unsupported datasource type: {datasource['name']}")
                continue

            if response and not response.get('error'):
                processed_responses.append(response)
                
        except Exception as e:
            st.error(f"🔴 Error processing query: {str(e)}")
            st.exception(e)

    if processed_responses:
        deploy_dashboard(processed_responses)

def handle_prometheus_query(query_text, datasource):
    """Process Prometheus query through full pipeline"""
    with st.spinner(f"🔍 Analyzing Prometheus query: '{query_text}'..."):
        # Step 1: Get metrics from LLM
        llm_response = prompt.get_query_metrics_labels([(query_text, datasource['name'])])
        if llm_response.get('error'):
            raise Exception("LLM analysis failed")
        
        # Step 2: VectorDB similarity search
        similar_metrics = vectordbs_handler.query_metrics_batch(
            llm_response['data'][0]['metrics'],
            datasource['uid'],
            n_results=5
        )

        # Step 3: Discover labels
        metric_labels = prometheus_handler.get_metrics_labels(
            st.session_state.prometheus_url,
            similar_metrics
        )
        # Step 4: Generate PromQL
        query_context = {
            "datasource": datasource['uid'],
            "original_query": query_text,
            "similar_metrics": similar_metrics,
            "labels": metric_labels
        }
        promql_response = prompt.generate_promql_query([query_context])

        return {
            'type': 'prometheus',
            'data': promql_response,
            'context': query_context
        }

def handle_postgres_query(query_text, datasource):
    """Process PostgreSQL query through full pipeline"""
    with st.spinner(f"🔍 Analyzing PostgreSQL query: '{query_text}'..."):
        # Get schema context from metadata
        metadata_context = postgres_handler.load_metadata()
        
        # Generate SQL with metadata
        sql_response = prompt.generate_sql_query(
            query=query_text,
            datasource=datasource['uid'],
            metadata_context = metadata_context
        )

        return {
            'type': 'postgres',
            'data': sql_response
        }

def deploy_dashboard(responses):
    """Deploy final dashboard to Grafana"""
    with st.spinner("🎨 Creating beautiful dashboard..."):
        # Generate Grafana JSON
        dashboard_json = prompt.generate_grafana_dashboard({
            "result": [resp['data'] for resp in responses if not resp.get('error')]
        })

        
        if dashboard_json.get('error'):
            st.error(f"😢 Failed to generate dashboard JSON: {dashboard_json['error']}")
            return

        # Deploy to Grafana
        deploy_result = grafana_handler.apply_dashboard(dashboard_json)
        if deploy_result.get('url'):
            st.success(f"✅ Dashboard created! [View in Grafana]({deploy_result['url']})")
        else:
            st.error("😢 Failed to deploy dashboard")

if __name__ == "__main__":
    main()