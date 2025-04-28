import streamlit as st
from svc import prometheus, vectordbs
import requests
from loguru import logger
import re

class PrometheusHandler:
    def __init__(self):
        self.ALLOWED_METRIC_LABELS = [
            "instance", "job", "name", "fstype", "persistentvolumeclaim", "service", 
            "mountpoint", "mode", "cpu", "device", "namespace", "pod", "container", 
            "deployment", "method", "status_code", "phase", "endpoint", "status", 
            "env", "region", "zone", "version", "code", "protocol", "database",
            "table", "user", "command", "queue", "host", "availability_zone", 
            "instance_type", "cluster", "role"
        ]

    def fetch_metrics_data(self, ds):
    
        """Fetch metrics from specific Prometheus instance"""
        try:
            response = requests.get(f"{ds['adjusted_url']}/api/v1/label/__name__/values", timeout=10)
            metrics=response.json().get('data', []) if response.ok else []
            logger.info(f"Metrics fetch response: {response.status_code}")
            if response.ok:
                count = vectordbs.store_metrics(
                    metrics=metrics,
                    ds_uid=ds['uid'],
                )
                logger.info(f"Metrics stored: {count}")
            return count
        except Exception as e:
            st.error(f"Metrics fetch failed: {str(e)}")
            return []

    def get_metrics_labels(self, ds_url, similar_metrics):
        final = {}
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
                                k in self.ALLOWED_METRIC_LABELS and
                                not re.match(r'^[a-fA-F0-9]{32,64}$', k) and
                                not re.match(r'.*\{\{.*\}\}.*', k) and
                                k not in ['__name__', 'id']
                            )
                        ]
                        logger.info(f"Fetched labels for {metric}: {filtered}")
                        final[metric] = filtered
                        return final
                    
            except Exception as e:
                st.error(f"Label fetch failed for {metric}: {str(e)}")
        return []
    
    def similarity_search(self, response, query, ds_options):
            ds_name = response['datasource']
            metrics = response['metrics']
            labels = response['related_metrics_labels']

            logger.info(f"Processing query: {query} from {ds_name}")
            
            if query and ds_name:
                ds_uid, ds_url = ds_options[ds_name]
                
                similar_metrics = vectordbs.query_metrics_batch(
                    metric_names=metrics,
                    ds_uid=ds_uid,
                    n_results=5
                )
                if similar_metrics:
                    st.session_state.similar_metrics = similar_metrics
                    st.session_state.similar_metrics_labels = labels
                    st.session_state.ds_uid = ds_uid
                    st.session_state.ds_url = ds_url
                else:
                    st.error("No similar metrics found.")
            return similar_metrics
    
    def process_final_response(self, ds_uuid, query,similar_metrics, labels):
        return {
            "query": query,
            "metrics": similar_metrics,
            "labels": labels,
            "datasource": ds_uuid
        }
    