"""
# tools/prometheus_tools.py
Prometheus tools for querying metrics, labels, and data
Supports generic Prometheus API interactions
"""

import logging
from typing import List, Dict, Optional
import aiohttp
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PrometheusClient:
    """
    Prometheus API client for metric operations
    """
    
    # Allowed labels for filtering (security measure)
    ALLOWED_LABELS = [
        "instance", "job", "name", "fstype", "persistentvolumeclaim", "service",
        "mountpoint", "mode", "cpu", "device", "namespace", "pod", "container",
        "deployment", "method", "status_code", "phase", "endpoint", "status",
        "env", "region", "zone", "version", "code", "protocol", "database",
        "table", "user", "command", "queue", "host", "availability_zone",
        "instance_type", "cluster", "role"
    ]
    
    def __init__(self, prometheus_url: str):
        """
        Initialize Prometheus client
        
        Args:
            prometheus_url: Prometheus server URL (e.g., http://localhost:9090)
        """
        self.base_url = prometheus_url.rstrip('/')
        logger.info(f"Prometheus client initialized for {self.base_url}")
    
    
    async def fetch_all_metrics(self) -> List[str]:
        """
        Fetch all metric names from Prometheus
        
        Returns:
            List of metric names
        """
        url = f"{self.base_url}/api/v1/label/__name__/values"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        metrics = data.get('data', [])
                        logger.info(f"Fetched {len(metrics)} metrics from Prometheus")
                        return metrics
                    else:
                        logger.error(f"Failed to fetch metrics: HTTP {response.status}")
                        return []
        
        except Exception as e:
            logger.error(f"Error fetching metrics: {e}")
            return []
    
    
    async def query_metric_labels(
        self,
        metric_name: str
    ) -> List[str]:
        """
        Get available labels for a specific metric
        
        Args:
            metric_name: Prometheus metric name
        
        Returns:
            List of label names
        """
        url = f"{self.base_url}/api/v1/query"
        params = {'query': metric_name}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get('data', {}).get('result', [])
                        
                        if not results:
                            logger.warning(f"No data found for metric {metric_name}")
                            return []
                        
                        # Extract labels from first result
                        metric_labels = results[0].get('metric', {})
                        
                        # Filter allowed labels and remove internal ones
                        labels = [
                            k for k in metric_labels.keys()
                            if k in self.ALLOWED_LABELS
                            and k not in ['__name__', 'id']
                            and not re.match(r'^[a-fA-F0-9]{32,64}$', k)  # Skip hash-like labels
                            and not re.match(r'.*\{\{.*\}\}.*', k)  # Skip templated labels
                        ]
                        
                        logger.info(f"Found {len(labels)} labels for {metric_name}: {labels}")
                        return labels
                    
                    else:
                        logger.error(f"Failed to query labels for {metric_name}: HTTP {response.status}")
                        return []
        
        except Exception as e:
            logger.error(f"Error querying labels for {metric_name}: {e}")
            return []
    
    
    async def query_metrics_batch(
        self,
        metrics: List[str]
    ) -> Dict[str, List[str]]:
        """
        Query labels for multiple metrics
        
        Args:
            metrics: List of metric names
        
        Returns:
            Dictionary mapping metric names to their labels
        """
        result = {}
        
        for metric in metrics:
            labels = await self.query_metric_labels(metric)
            if labels:
                result[metric] = labels
        
        return result
    
    
    async def execute_promql(
        self,
        query: str,
        time: Optional[str] = None
    ) -> Dict:
        """
        Execute a PromQL query
        
        Args:
            query: PromQL query string
            time: Optional timestamp (RFC3339 or Unix)
        
        Returns:
            Query result data
        """
        url = f"{self.base_url}/api/v1/query"
        params = {'query': query}
        
        if time:
            params['time'] = time
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('data', {})
                    else:
                        logger.error(f"PromQL query failed: HTTP {response.status}")
                        return {}
        
        except Exception as e:
            logger.error(f"Error executing PromQL: {e}")
            return {}
    
    async def test_connection(self) -> bool:
        """
        Test Prometheus connection
        
        Returns:
            True if connection successful
        """
        url = f"{self.base_url}/api/v1/status/config"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


# ===== TOOL FUNCTIONS (for LangGraph) =====

async def fetch_prometheus_metrics(prometheus_url: str) -> List[str]:
    """
    LangGraph tool: Fetch all metrics from Prometheus
    
    Args:
        prometheus_url: Prometheus server URL
    
    Returns:
        List of metric names
    """
    client = PrometheusClient(prometheus_url)
    return await client.fetch_all_metrics()


async def query_prometheus_labels(
    metrics: List[str],
    prometheus_url: str
) -> Dict[str, List[str]]:
    """
    LangGraph tool: Query labels for metrics
    
    Args:
        metrics: List of metric names
        prometheus_url: Prometheus server URL
    
    Returns:
        Dictionary mapping metrics to their labels
    """
    client = PrometheusClient(prometheus_url)
    return await client.query_metrics_batch(metrics)


async def execute_promql_query(
    query: str,
    prometheus_url: str
) -> Dict:
    """
    LangGraph tool: Execute PromQL query
    
    Args:
        query: PromQL query string
        prometheus_url: Prometheus URL
    
    Returns:
        Query results
    """
    client = PrometheusClient(prometheus_url)
    return await client.execute_promql(query)