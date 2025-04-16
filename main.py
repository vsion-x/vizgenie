import streamlit as st
import requests
import os
from dotenv import load_dotenv
from llm import prompt

load_dotenv()

from svc import grafana, prometheus, vectordbs

# Get API keys and Grafana key from environment variables
apikeys = os.getenv("GROQ_API_KEY", "").split(",")

metric_labels = [
    "instance", "job", "name", "fstype", "persistentvolumeclaim", "service", 
    "mountpoint", "mode", "cpu", "device", "namespace", "pod", "container", 
    "deployment", "method", "status_code", "phase", "endpoint", "status", 
    "env", "region", "zone", "version", "code", "protocol", "database",
    "table", "user", "command", "queue", "host", "availability_zone", 
    "instance_type", "cluster", "role"
]


# Initialize session state for metrics labels
if 'metrics_labels' not in st.session_state:
    st.session_state.metrics_labels = {}


# Streamlit UI
st.title("Prometheus Metrics Dashboard Builder")

datasources = grafana.fetch_datasources()
if not datasources:
    st.warning("No Prometheus datasources found in Grafana")
    st.stop()

ds_options = {ds['name']: (ds['uid'], ds['adjusted_url']) for ds in datasources}

with st.expander("Metric Management", expanded=False):
    if st.button("Refresh All Metrics"):
        with st.spinner("Updating metrics..."):
            for ds in datasources:
                metrics = prometheus.fetch_metrics(ds['adjusted_url'])
                if metrics:
                    count = vectordbs.store_metrics(metrics, ds['uid'])
                    st.success(f"Updated {ds['name']} with {count} new metrics")

st.header("Create New Dashboard")
queries = []

with st.form("dashboard_form"):
    for i in range(3):
        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_input(f"Query {i+1}", key=f"q{i}")
        with col2:
            ds_name = st.selectbox(f"Datasource {i+1}", options=ds_options.keys(), key=f"ds{i}")
        queries.append((query, ds_name))


    if st.form_submit_button("Generate Dashboard"):
        processed_queries = []
        for query, ds_name in queries:
            if query and ds_name:
                ds_uid, ds_url = ds_options[ds_name]
                similar = vectordbs.query_metrics(query, ds_uid)
                labels = {}
                
                for metric in similar:
                    label_res = requests.get(f"{ds_url}/api/v1/query?query={metric}")
                    if label_res.ok:
                        # Get the full response data
                        response_data = label_res.json().get('data', {})
                        results = response_data.get('result', [])

                        # Check if there are any results before accessing
                        if results:
                            # Get all metric keys and filter against approved list
                            metric_keys = set(results[0].get('metric', {}).keys())
                            metric_keys.discard("id")  # Always remove 'id'
                            
                            # Filter keys using the approved metric_labels list
                            filtered_keys = [key for key in metric_keys if key in metric_labels]
                            
                            labels[metric] = filtered_keys
                        else:
                            labels[metric] = []
                            st.warning(f"No results found for metric: {metric}")
                
                processed_queries.append({
                    "mandatory_datasource_uuid": ds_uid,
                    "userquery": query,
                    "mandatory_similar_metrics": similar,
                    "mandatry_corresponding_metrics_labels": labels
                })

        if processed_queries:
            with st.spinner("Generating queries..."):
                promql_response = prompt.generate_promql_query(processed_queries)
                
            if not promql_response.get('error'):
                with st.spinner("Creating dashboard..."):
                    dashboard_json = prompt.generate_grafana_dashboard(promql_response)
                    
                if not dashboard_json.get('error'):
                    apply_response = grafana.apply_grafana_dashboard(dashboard_json)
                    if 'url' in apply_response:
                        st.success(f"Dashboard created: [View Dashboard]({apply_response['url']})")
                    else:
                        st.error("Failed to deploy dashboard")
                else:
                    st.error("Dashboard generation failed")
            else:
                st.error("Query generation failed")