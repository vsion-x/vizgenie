import requests
from urllib.parse import urlparse
import os
from utils import utils
import streamlit as st



def adjust_prometheus_url(original_url):
    """
    Adjust the Prometheus URL based on environment configuration or via Docker inspection.
    
    Steps:
      1. Parses the original URL (e.g., "https://prometheus:9090") and extracts the hostname
         to use as the container name.
      2. Checks for an environment variable `PROMETHEUS_HOST` to override URL details.
         If defined, it extracts the host (and possibly a port) from it.
      3. If no environment variable is set, it calls get_exposed_port using the container 
         name parsed from the original URL to get the actual exposed host port.
      4. Rebuilds the URL with the new host and port as determined.
    """
    original_parsed = urlparse(original_url)
    # Parse container name from the original URL's hostname
    container_name = original_parsed.hostname

    # Check for an override using PROMETHEUS_HOST environment variable
    prometheus_host = os.getenv("PROMETHEUS_HOST", "http://localhost").strip()
    if prometheus_host:
        # Determine if PROMETHEUS_HOST includes a scheme
        if prometheus_host.startswith(('http://', 'https://')):
            parsed_env = urlparse(prometheus_host)
            new_host = parsed_env.hostname
            new_port = utils.get_exposed_port(container_name)
        else:
            if ':' in prometheus_host:
                new_host, port_part = prometheus_host.split(':', 1)
                new_port = int(port_part) if port_part.isdigit() else None
            else:
                new_host = prometheus_host
                new_port = None
        # Use new_port if provided, otherwise fall back to the port in the original URL.
        final_port = new_port or original_parsed.port
    else:
        # If no environment override exists, use Docker SDK to inspect the container's port mapping.
        exposed_port = utils.get_exposed_port(container_name)
        new_host = container_name  # Keep the container name as the host
        final_port = exposed_port if exposed_port else original_parsed.port

    # Rebuild the netloc (host:port) portion.
    if final_port:
        new_netloc = f"{new_host}:{final_port}"
    else:
        new_netloc = new_host

    return original_parsed._replace(netloc=new_netloc).geturl()


def fetch_metrics(prom_url):
    """Fetch metrics from specific Prometheus instance"""
    try:
        response = requests.get(f"{prom_url}/api/v1/label/__name__/values", timeout=10)
        return response.json().get('data', []) if response.ok else []
    except Exception as e:
        st.error(f"Metrics fetch failed: {str(e)}")
        return []