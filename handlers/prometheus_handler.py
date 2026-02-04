# handlers/prometheus_handler.py
# Handler for Prometheus API operations

import requests
import re
from typing import Dict, List, Any
from loguru import logger


class PrometheusHandler:
    """Handler for Prometheus API operations"""
    
    # Allowed labels to prevent noise
    ALLOWED_METRIC_LABELS = [
        "instance", "job", "name", "fstype", "persistentvolumeclaim", "service", 
        "mountpoint", "mode", "cpu", "device", "namespace", "pod", "container", 
        "deployment", "method", "status_code", "phase", "endpoint", "status", 
        "env", "region", "zone", "version", "code", "protocol", "database",
        "table", "user", "command", "queue", "host", "availability_zone", 
        "instance_type", "cluster", "role"
    ]
    
    def __init__(self, url: str):
        """
        Initialize Prometheus handler
        
        Args:
            url: Prometheus instance URL (e.g., http://localhost:9090)
        """
        self.url = url

    def fetch_metrics_data(self, ds: Dict[str, Any], vectordbs_handler: Any) -> int:
        """
        Fetch all available metrics from Prometheus and store in vector database
        
        Args:
            ds: Datasource dictionary with uid
            vectordbs_handler: VectorDB handler instance
            
        Returns:
            Number of new metrics stored
        """
        try:
            response = requests.get(
                f"{self.url}/api/v1/label/__name__/values", 
                timeout=10
            )
            
            if response.ok:
                metrics = response.json().get('data', [])
                logger.info(f"Fetched {len(metrics)} metrics from Prometheus")
                
                count = vectordbs_handler.store_metrics(
                    metrics=metrics,
                    ds_uid=ds['uid'],
                )
                logger.info(f"Stored {count} new metrics in vector DB")
                return count
            else:
                logger.error(f"Metrics fetch failed: {response.status_code}")
                return 0
                
        except requests.exceptions.Timeout:
            logger.error("Prometheus request timeout")
            return 0
        except Exception as e:
            logger.error(f"Metrics fetch failed: {str(e)}")
            return 0

    def get_metrics_labels(self, ds_url: str, similar_metrics: List[str]) -> Dict[str, List[str]]:
        """
        Fetch actual labels for given metrics from Prometheus
        
        Args:
            ds_url: Prometheus URL
            similar_metrics: List of metric names to fetch labels for
            
        Returns:
            Dict mapping metric name to list of labels
        """
        final = {}
        
        for metric in similar_metrics:
            try:
                # Query Prometheus for metric
                label_res = requests.get(
                    f"{ds_url}/api/v1/query?query={metric}",
                    timeout=5
                )
                
                if label_res.ok:
                    results = label_res.json().get('data', {}).get('result', [])
                    
                    if results:
                        # Get all label keys from first result
                        keys = set(results[0].get('metric', {}).keys())
                        
                        # Filter labels
                        filtered = [
                            k for k in keys 
                            if (
                                k in self.ALLOWED_METRIC_LABELS and
                                not re.match(r'^[a-fA-F0-9]{32,64}$', k) and  # No hash-like labels
                                not re.match(r'.*\{\{.*\}\}.*', k) and  # No template labels
                                k not in ['__name__', 'id']  # Skip special labels
                            )
                        ]
                        
                        logger.info(f"Fetched {len(filtered)} labels for {metric}")
                        final[metric] = filtered
                        
                        # Return after first successful fetch
                        # (assuming all instances have similar labels)
                        return final
                    
            except Exception as e:
                logger.error(f"Label fetch failed for {metric}: {str(e)}")
        
        return final
    
    def test_connection(self) -> bool:
        """
        Test Prometheus connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = requests.get(f"{self.url}/api/v1/status/config", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def process_final_response(
        self, 
        ds_uuid: str, 
        query: str, 
        similar_metrics: List[str], 
        labels: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Process and format final response
        
        Args:
            ds_uuid: Datasource UUID
            query: Original user query
            similar_metrics: List of similar metrics found
            labels: Metric labels mapping
            
        Returns:
            Formatted response dictionary
        """
        return {
            "query": query,
            "metrics": similar_metrics,
            "labels": labels,
            "datasource": ds_uuid
        }