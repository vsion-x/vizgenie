import streamlit as st
import requests
from loguru import logger
import re

class PrometheusHandler:
    def __init__(self, url):
        self.ALLOWED_METRIC_LABELS = [
            "instance", "job", "name", "fstype", "persistentvolumeclaim", "service", 
            "mountpoint", "mode", "cpu", "device", "namespace", "pod", "container", 
            "deployment", "method", "status_code", "phase", "endpoint", "status", 
            "env", "region", "zone", "version", "code", "protocol", "database",
            "table", "user", "command", "queue", "host", "availability_zone", 
            "instance_type", "cluster", "role"
        ]
        self.url = url

    def fetch_metrics_data(self, ds, vectordbs_handler):
    
        """Fetch metrics from specific Prometheus instance"""
        try:
            print("--url", self.url)
            response = requests.get(f"{self.url}/api/v1/label/__name__/values", timeout=10)
            metrics=response.json().get('data', []) if response.ok else []
            logger.info(f"Metrics fetch response: {response.status_code}")
            if response.ok:
                count = vectordbs_handler.store_metrics(
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
    
    def process_final_response(self, ds_uuid, query,similar_metrics, labels):
        return {
            "query": query,
            "metrics": similar_metrics,
            "labels": labels,
            "datasource": ds_uuid
        }
    