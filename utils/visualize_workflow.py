# utils/visualize_workflow.py
# Script to visualize the LangGraph workflow

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.workflow import VizGenieWorkflow
from handlers.grafana_handler import GrafanaHandler
from handlers.prometheus_handler import PrometheusHandler
from handlers.postgres_handler import PostgresHandler
from handlers.vectordb_handler import VectorDBHandler


def main():
    """Generate and print workflow visualization"""
    
    # Initialize with dummy handlers
    handlers = {
        'prometheus': PrometheusHandler("http://localhost:9090"),
        'postgres': PostgresHandler("postgresql://localhost/db"),
        'grafana': GrafanaHandler("http://localhost:3000", "dummy_key"),
        'vectordb': VectorDBHandler()
    }
    
    # Create workflow
    workflow = VizGenieWorkflow(handlers)
    workflow.compile_graph()
    
    # Get visualization
    print("\n" + "="*70)
    print("VizGenie LangGraph Workflow Visualization")
    print("="*70 + "\n")
    
    try:
        mermaid = workflow.get_graph_visualization()
        print(mermaid)
    except Exception as e:
        print(f"Visualization generation failed: {e}")
        print("\nWorkflow structure:")
        print("  initialize → extract_intent → extract_metrics → vector_search")
        print("  → generate_query → validate_query → generate_dashboard → deploy_dashboard")
        print("  (with conditional routing and error handling)")
    
    print("\n" + "="*70)
    print("Node Descriptions:")
    print("="*70)
    
    nodes = {
        "initialize": "Set up workflow state and validate inputs",
        "extract_intent": "Classify queries and map datasources",
        "extract_metrics": "Extract metrics and labels from natural language",
        "vector_search": "Find similar metrics using vector similarity",
        "generate_query": "Generate PromQL or SQL queries",
        "validate_query": "Validate query syntax and semantics",
        "generate_dashboard": "Create Grafana dashboard JSON",
        "deploy_dashboard": "Deploy dashboard to Grafana",
        "error_handler": "Handle errors and retry logic"
    }
    
    for node, description in nodes.items():
        print(f"\n{node.upper()}")
        print(f"  {description}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()