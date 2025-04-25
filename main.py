import streamlit as st
import requests
import os
from dotenv import load_dotenv
import re
from loguru import logger
load_dotenv()

from llm import prompt
from svc import grafana, prometheus, vectordbs

# Get API keys and Grafana key from environment variables
apikeys = os.getenv("GROQ_API_KEY", "").split(",")

ALLOWED_METRIC_LABELS = [
    "instance", "job", "name", "fstype", "persistentvolumeclaim", "service", 
    "mountpoint", "mode", "cpu", "device", "namespace", "pod", "container", 
    "deployment", "method", "status_code", "phase", "endpoint", "status", 
    "env", "region", "zone", "version", "code", "protocol", "database",
    "table", "user", "command", "queue", "host", "availability_zone", 
    "instance_type", "cluster", "role"
]

dummy_metrics = [f"dummy_metric_{i}" for i in range(1, 11)]  # 10 dummy metric names
dummy_ds_uid = "sample-datasource-uid"

# Initialize session state for metrics labels
if 'metrics_labels' not in st.session_state:
    st.session_state.metrics_labels = {}

if 'dummy_loaded' not in st.session_state:
    count = vectordbs.store_metrics(dummy_metrics, dummy_ds_uid)
    st.info(f"Initialized vector DB with {count} dummy metrics for testing.")
    st.session_state['dummy_loaded'] = True

# Streamlit UI
st.title("Prometheus Metrics Dashboard Builder")

# Datasource initialization
datasources = grafana.fetch_datasources()
if not datasources:
    st.warning("No Prometheus datasources found in Grafana")
    st.stop()

ds_options = {ds['name']: (ds['uid'], ds['adjusted_url']) for ds in datasources}

# Metric management section
with st.expander("Metric Management", expanded=False):
    if st.button("Refresh All Metrics"):
        with st.spinner("Updating metrics..."):
            for ds in datasources:
                metrics = prometheus.fetch_metrics(ds['adjusted_url'])
                logger.info(f"Fetched {len(metrics)} metrics from {ds['name']}")
                if metrics:
                    count = vectordbs.store_metrics(metrics, ds['uid'])
                    st.success(f"Updated {ds['name']} with {count} new metrics")

# Dashboard creation form
st.header("Create New Dashboard")
with st.form("dashboard_form"):
    queries = []
    for i in range(3):
        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_input(f"Query {i+1}", key=f"q{i}")
        with col2:
            ds_name = st.selectbox(f"Datasource {i+1}", options=ds_options.keys(), key=f"ds{i}")
        queries.append((query, ds_name))
    
    if st.form_submit_button("Analyze Queries"):
        with st.spinner("Analyzing queries..."):
            st.session_state.llm_response = prompt.get_query_metrics_labels(queries)
            st.session_state.processed_queries = []
            st.session_state.promql_response = None
            st.session_state.dashboard_json = None
            logger.info("LLM response received")
    
# Show analysis results
if 'llm_response' in st.session_state and st.session_state.llm_response.get('data'):
    st.success("Query analysis completed! Ready to generate dashboard")
    
    # Store processed queries in session state
    if not st.session_state.processed_queries:
        for entry in st.session_state.llm_response['data']:
            query = entry['query']
            ds_name = entry['datasource']
            metrics = entry['metrics']
            labels = entry['related_metrics_labels']

            logger.info(f"Processing query: {query} from {ds_name}")
            
            if query and ds_name:
                ds_uid, ds_url = ds_options[ds_name]
                
                # VectorDB similarity search
                similar_metrics = vectordbs.query_metrics_batch(
                    metric_names=metrics,
                    ds_uid=ds_uid,
                    n_results=5
                )
                logger.info(f"Found {len(similar_metrics)} similar metrics for {query}")
                
                # Label fetching
                metric_labels = []
                for metric in similar_metrics:
                    try:
                        label_res = requests.get(f"{ds_url}/api/v1/query?query={metric}")
                        logger.info(f"Label fetch response: {label_res.status_code}")
                        if label_res.ok:
                            results = label_res.json().get('data', {}).get('result', [])
                            if results:
                                keys = set(results[0].get('metric', {}).keys())
                                filtered = [
                                    k for k in keys 
                                    if (
                                        k in ALLOWED_METRIC_LABELS and
                                        not re.match(r'^[a-fA-F0-9]{32,64}$', k) and
                                        not re.match(r'.*\{\{.*\}\}.*', k) and
                                        k not in ['__name__', 'id']
                                    )
                                ]
                                metric_labels.extend(filtered)
                                logger.info(f"Fetched labels for {metric}: {filtered}")
                    except Exception as e:
                        st.error(f"Label fetch failed for {metric}: {str(e)}")
                
                st.session_state.processed_queries.append({
                    "mandatory_datasource_uuid": ds_uid,
                    "userquery": query,
                    "mandatory_similar_metrics": similar_metrics,
                    "mandatry_corresponding_metrics_labels": list(set(metric_labels))
                })

# Dashboard generation section
if st.session_state.get('processed_queries'):
    if st.button("✨ Generate Dashboard"):
        with st.spinner("Generating PromQL queries..."):
            try:
                st.session_state.promql_response = prompt.generate_promql_query(
                    st.session_state.processed_queries
                )

                logger.info("PromQL response received")
                
                if st.session_state.promql_response.get('error'):
                    st.error("PromQL generation failed")
                    st.stop()
                
                st.success("PromQL queries generated successfully")
                
                # Dashboard generation
                with st.spinner("Building Grafana dashboard..."):
                    st.session_state.dashboard_json = prompt.generate_grafana_dashboard(
                        st.session_state.promql_response
                    )

                    logger.info("Dashboard JSON response received")
                    
                    if st.session_state.dashboard_json.get('error'):
                        st.error("Dashboard creation failed")
                        st.stop()
                    
                    # Deploy to Grafana
                    apply_response = grafana.apply_grafana_dashboard(
                        st.session_state.dashboard_json
                    )

                    logger.info("Dashboard deployment response received")
                    
                    if 'url' in apply_response:
                        st.success(f"Dashboard deployed: [View in Grafana]({apply_response['url']})")
                    else:
                        st.error("Dashboard deployment failed")
            except Exception as e:
                st.error(f"Generation failed: {str(e)}")

# Show intermediate results
if st.session_state.get('promql_response'):
    with st.expander("Generated PromQL Queries"):
        st.json(st.session_state.promql_response)

if st.session_state.get('dashboard_json'):
    with st.expander("Grafana Dashboard JSON"):
        st.json(st.session_state.dashboard_json)