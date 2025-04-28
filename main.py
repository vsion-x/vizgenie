import streamlit as st
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from handlers.prometheus_handler import PrometheusHandler
from handlers.postgres_handler import PostgresHandler
from svc import grafana, vectordbs, prometheus
from llm import prompt

# Load environment variables
load_dotenv()

# Initialize handlers
prometheus_handler = PrometheusHandler()
postgres_handler = PostgresHandler()

def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if 'metrics_labels' not in st.session_state:
        st.session_state.metrics_labels = {}
    if 'dummy_loaded' not in st.session_state:
        vectordbs.store_metrics([f"dummy_metric_{i}" for i in range(1, 11)], "sample-datasource-uid")
        st.session_state.dummy_loaded = True

def display_datasources(datasources):
    """Display available datasources in formatted way"""
    st.subheader("🔌 Connected Datasources")
    for ds in datasources:
        with st.expander(f"{ds['type'].upper()}: {ds['name']}", expanded=False):
            st.markdown(f"""
            **UID:** `{ds['uid']}`  
            **URL:** {ds.get('url', ds.get('adjusted_url', 'N/A'))}  
            **Database:** {ds.get('database', 'N/A')}
            """)

def handle_metric_management(datasources):
    """Metric management section for Prometheus"""
    with st.expander("🔄 Metric Management", expanded=False):
        if st.button("Refresh All Prometheus Metrics"):
            with st.spinner("Updating metrics across all Prometheus datasources..."):
                for ds in [d for d in datasources if d['type'] == 'prometheus']:
                    try:
                        count = prometheus_handler.fetch_metrics_data(ds)
                        st.success(f"Updated {ds['name']} with {count} new metrics")
                    except Exception as e:
                        st.error(f"Failed to update {ds['name']}: {str(e)}")

def main():
    """Main application flow"""
    st.set_page_config(page_title="VizGenie", layout="wide")
    initialize_session_state()
    
    st.title("🎩 VizGenie - Natural Language to Dashboard")
    st.markdown("Transform natural language queries into Grafana dashboards with AI magic!")
    
    # Fetch and display datasources
    datasources = grafana.fetch_datasources()
    if not datasources:
        st.warning("⚠️ No datasources found in Grafana!")
        st.stop()
    
    display_datasources(datasources)
    handle_metric_management(datasources)

    # Dashboard creation form
    st.header("🚀 Create New Dashboard")
    with st.form("main_form"):
        # Query input section
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
            if datasource['type'] == 'prometheus':
                response = handle_prometheus_query(query_text, datasource)
            elif datasource['type'] == 'postgres':
                response = handle_postgres_query(query_text, datasource)
            else:
                st.warning(f"Unsupported datasource type: {datasource['type']}")
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
        similar_metrics = vectordbs.query_metrics_batch(
            llm_response['data'][0]['metrics'],
            datasource['uid'],
            n_results=5
        )
        
        # Step 3: Discover labels
        metric_labels = prometheus_handler.get_metrics_labels(
            datasource['adjusted_url'],
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
            st.error("😢 Failed to generate dashboard JSON")
            return

        # Deploy to Grafana
        deploy_result = grafana.apply_grafana_dashboard(dashboard_json)
        if deploy_result.get('url'):
            st.success(f"✅ Dashboard created! [View in Grafana]({deploy_result['url']})")
        else:
            st.error("😢 Failed to deploy dashboard")

if __name__ == "__main__":
    main()