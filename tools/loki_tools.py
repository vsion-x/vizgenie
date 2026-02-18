"""
# tools/loki_tools.py
Loki tools for log querying and analysis
Supports LogQL queries and pattern matching
"""

import logging
from typing import List, Dict, Optional, Any
import aiohttp
import re
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class LokiClient:
    """
    Loki API client for log operations
    """
    
    def __init__(self, loki_url: str):
        """
        Initialize Loki client
        
        Args:
            loki_url: Loki server URL (e.g., http://localhost:3100)
        """
        self.base_url = loki_url.rstrip('/')
        logger.info(f"Loki client initialized for {self.base_url}")
    
    
    async def test_connection(self) -> bool:
        """
        Test Loki connection
        
        Returns:
            True if connection successful
        """
        url = f"{self.base_url}/ready"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Loki connection test failed: {e}")
            return False
    
    
    async def query_logs(
        self,
        filter: str = '{container=~".+"}',
        time_range: str = "1h",
        limit: int = 100,
        direction: str = "backward"
    ) -> List[Dict]:
        """
        Query Loki logs using LogQL
        
        Args:
            filter: LogQL filter expression (e.g., '{app="fastapi"}', '{level="error"}')
            time_range: Time window (15s, 5m, 1h, 24h)
            limit: Maximum results
            direction: "forward" or "backward"
        
        Returns:
            List of log entries with timestamps
        """
        # Calculate time range
        now_ns = int(time.time() * 1e9)
        duration_map = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        
        match = re.match(r'(\d+)([smhd])', time_range)
        if match:
            value, unit = int(match.group(1)), match.group(2)
            seconds = value * duration_map[unit]
            start_ns = now_ns - (seconds * int(1e9))
        else:
            start_ns = now_ns - (3600 * int(1e9))  # default 1h
        
        # ✅ Validate filter is not empty
        if not filter or filter.strip() == '{}':
            filter = '{job=~".+"}'  # match all jobs
        
        url = f"{self.base_url}/loki/api/v1/query_range"
        params = {
            'query': filter,
            'start': str(start_ns),
            'end':   str(now_ns),
            'limit': limit,
            'direction': direction
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_loki_response(data)
                    else:
                        body = await response.text()
                        logger.error(f"Loki query failed: HTTP {response.status} — {body[:200]}")
                        return []
        
        except Exception as e:
            logger.error(f"Error querying Loki: {e}")
            return []
    
    
    def _parse_loki_response(self, response: Dict) -> List[Dict]:
        """
        Parse Loki API response to standard format
        
        Args:
            response: Raw Loki API response
        
        Returns:
            List of log entries
        """
        logs = []
        
        for stream in response.get('data', {}).get('result', []):
            labels = stream.get('stream', {})
            values = stream.get('values', [])
            
            for timestamp_ns, log_line in values:
                logs.append({
                    'timestamp': int(timestamp_ns) / 1e9,  # Convert to seconds
                    'timestamp_ns': int(timestamp_ns),
                    'log': log_line,
                    'labels': labels
                })
        
        logger.info(f"Parsed {len(logs)} log entries from Loki")
        return logs

class LogAnalyzer:
    """
    Analyze logs for patterns, anomalies, and metrics
    """
    
    @staticmethod
    def extract_metrics(logs: List[Dict]) -> Dict[str, Any]:
        """
        Extract observability metrics from logs
        
        Args:
            logs: List of log entries
        
        Returns:
            Dictionary of extracted metrics
        """
        if not logs:
            return {
                'total_logs': 0,
                'error_count': 0,
                'error_rate': 0.0,
                'latency_p50': 0.0,
                'latency_p95': 0.0,
                'latency_p99': 0.0,
                'unique_errors': 0,
                'error_types': {}
            }
        
        total = len(logs)
        
        # Identify error logs
        error_logs = [
            log for log in logs
            if re.search(
                r'\b(error|exception|failed|critical|fatal|panic)\b',
                log['log'],
                re.IGNORECASE
            )
        ]
        
        # Extract latencies
        latencies = []
        for log in logs:
            # Look for latency patterns
            patterns = [
                r'(?:took|duration|latency)[=:]\s*(\d+(?:\.\d+)?)\s*ms',
                r'(\d+(?:\.\d+)?)\s*ms',
                r'time[=:]\s*(\d+(?:\.\d+)?)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, log['log'], re.IGNORECASE)
                if match:
                    latencies.append(float(match.group(1)))
                    break
        
        # Calculate percentiles
        latency_p50 = latency_p95 = latency_p99 = 0.0
        if latencies:
            latencies.sort()
            latency_p50 = latencies[int(len(latencies) * 0.50)]
            latency_p95 = latencies[int(len(latencies) * 0.95)]
            latency_p99 = latencies[int(len(latencies) * 0.99)]
        
        # Categorize error types
        error_types = {}
        for log in error_logs:
            # Extract error type
            match = re.search(
                r'([\w]+Error|[\w]+Exception|\w+Fault)',
                log['log']
            )
            if match:
                error_type = match.group(1)
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            'total_logs': total,
            'error_count': len(error_logs),
            'error_rate': len(error_logs) / total if total > 0 else 0.0,
            'latency_p50': latency_p50,
            'latency_p95': latency_p95,
            'latency_p99': latency_p99,
            'unique_errors': len(error_types),
            'error_types': error_types
        }
    
    
    @staticmethod
    def analyze_patterns(
        logs: List[Dict],
        known_patterns: List[Dict]
    ) -> Dict[str, Any]:
        """
        Analyze logs for known and unknown patterns
        
        Args:
            logs: List of log entries
            known_patterns: List of pattern dictionaries from YAML
        
        Returns:
            Analysis results
        """
        matched = {pattern['id']: [] for pattern in known_patterns}
        unknown = []
        
        for log in logs:
            log_text = log['log']
            matched_any = False
            
            for pattern in known_patterns:
                try:
                    if re.search(pattern['regex'], log_text, re.IGNORECASE):
                        matched[pattern['id']].append(log)
                        matched_any = True
                        break
                except re.error:
                    logger.warning(f"Invalid regex in pattern {pattern['id']}")
                    continue
            
            if not matched_any:
                unknown.append(log)
        
        # Calculate pattern frequencies
        pattern_stats = []
        for pattern in known_patterns:
            count = len(matched[pattern['id']])
            if count > 0:
                pattern_stats.append({
                    'pattern_id': pattern['id'],
                    'category': pattern['category'],
                    'severity': pattern['severity'],
                    'count': count,
                    'percentage': (count / len(logs)) * 100 if logs else 0
                })
        
        # Sort by count
        pattern_stats.sort(key=lambda x: x['count'], reverse=True)
        
        return {
            'matched_patterns': pattern_stats,
            'unknown_count': len(unknown),
            'unknown_percentage': (len(unknown) / len(logs)) * 100 if logs else 0,
            'unknown_samples': unknown[:10]  # First 10 unknown logs
        }
    
    
    @staticmethod
    def detect_anomalies(
        logs: List[Dict],
        baseline_error_rate: float = 0.02
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in logs
        
        Args:
            logs: List of log entries
            baseline_error_rate: Expected error rate baseline
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        metrics = LogAnalyzer.extract_metrics(logs)
        
        # High error rate
        if metrics['error_rate'] > baseline_error_rate * 2:
            anomalies.append({
                'type': 'high_error_rate',
                'severity': 'high' if metrics['error_rate'] > 0.1 else 'medium',
                'description': f"Error rate: {metrics['error_rate']:.2%} (baseline: {baseline_error_rate:.2%})",
                'current_value': metrics['error_rate'],
                'threshold': baseline_error_rate * 2
            })
        
        # High latency
        if metrics['latency_p95'] > 500:
            severity = 'critical' if metrics['latency_p95'] > 1000 else 'high'
            anomalies.append({
                'type': 'high_latency',
                'severity': severity,
                'description': f"P95 latency: {metrics['latency_p95']:.0f}ms",
                'current_value': metrics['latency_p95'],
                'threshold': 500
            })
        
        # Error burst detection
        if len(logs) > 0:
            time_buckets = {}
            for log in logs:
                if 'error' in log['log'].lower() or 'exception' in log['log'].lower():
                    bucket = int(log['timestamp'] / 60)  # 1-minute buckets
                    time_buckets[bucket] = time_buckets.get(bucket, 0) + 1
            
            max_errors_per_minute = max(time_buckets.values()) if time_buckets else 0
            if max_errors_per_minute > 10:
                anomalies.append({
                    'type': 'error_burst',
                    'severity': 'critical',
                    'description': f"{max_errors_per_minute} errors in 1 minute",
                    'current_value': max_errors_per_minute,
                    'threshold': 10
                })
        
        return anomalies


# ===== TOOL FUNCTIONS (for LangGraph) =====

async def query_loki_logs(
    loki_url: str,
    filter: str = "{}",
    time_range: str = "1h",
    limit: int = 100
) -> List[Dict]:
    """
    LangGraph tool: Query Loki logs
    
    Args:
        loki_url: Loki server URL
        filter: LogQL filter
        time_range: Time window
        limit: Max results
    
    Returns:
        List of log entries
    """
    client = LokiClient(loki_url)
    return await client.query_logs(filter, time_range, limit)


async def analyze_logs(
    logs: List[Dict],
    known_patterns: List[Dict]
) -> Dict[str, Any]:
    """
    LangGraph tool: Analyze logs for patterns
    
    Args:
        logs: List of log entries
        known_patterns: Known patterns from YAML
    
    Returns:
        Analysis results
    """
    analyzer = LogAnalyzer()
    return analyzer.analyze_patterns(logs, known_patterns)


async def extract_log_metrics(logs: List[Dict]) -> Dict[str, Any]:
    """
    LangGraph tool: Extract metrics from logs
    
    Args:
        logs: List of log entries
    
    Returns:
        Extracted metrics
    """
    analyzer = LogAnalyzer()
    return analyzer.extract_metrics(logs)
