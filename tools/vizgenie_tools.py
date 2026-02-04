# tools/vizgenie_tools.py
# Complete tool definitions for VizGenie agents

from typing import Dict, List, Any
from langchain.tools import tool
from langchain_core.tools import Tool
import json


class VizGenieTools:
    """Collection of tools for VizGenie agents"""
    
    def __init__(self, handlers: Dict[str, Any]):
        """
        Initialize tools with handler instances
        
        Args:
            handlers: Dict containing all handler instances
                - prometheus: PrometheusHandler
                - postgres: PostgresHandler
                - grafana: GrafanaHandler
                - vectordb: VectorDBHandler
                - groq: GroqHandler (optional, used via llm.prompt)
        """
        self.prometheus_handler = handlers.get('prometheus')
        self.postgres_handler = handlers.get('postgres')
        self.grafana_handler = handlers.get('grafana')
        self.vectordb_handler = handlers.get('vectordb')
    
    def get_all_tools(self) -> List[Tool]:
        """Get all available tools for agents"""
        return [
            self.extract_metrics_tool(),
            self.vector_similarity_search_tool(),
            self.fetch_metric_labels_tool(),
            self.generate_promql_tool(),
            self.generate_sql_tool(),
            self.validate_query_tool(),
            self.generate_dashboard_tool(),
            self.deploy_dashboard_tool(),
            self.fetch_datasources_tool()
        ]
    
    # ==================== TOOL 1: EXTRACT METRICS ====================
    
    def extract_metrics_tool(self) -> Tool:
        """Tool to extract metrics from natural language query"""
        
        @tool
        def extract_metrics(query: str, datasource_name: str) -> Dict[str, Any]:
            """
            Extract potential metrics and labels from a natural language query.
            
            Args:
                query: The natural language query
                datasource_name: Name of the target datasource
                
            Returns:
                Dict with success status, suggested_metrics, and suggested_labels
            """
            try:
                # Import here to avoid circular dependency
                from llm.prompt import get_query_metrics_labels
                
                result = get_query_metrics_labels([(query, datasource_name)])
                print("extract_metrics Input:", [(query, datasource_name)])
                print("extract_metrics Output:", result)
                
                if result.get('error'):
                    return {
                        "success": False,
                        "error": result['error'],
                        "suggested_metrics": [],
                        "suggested_labels": []
                    }
                
                data = result.get('data', [{}])[0]
                return {
                    "success": True,
                    "suggested_metrics": data.get('metrics', []),
                    "suggested_labels": data.get('related_metrics_labels', []),
                    "original_query": data.get('query', query)
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "suggested_metrics": [],
                    "suggested_labels": []
                }
        
        return extract_metrics
    
    # ==================== TOOL 2: VECTOR SEARCH ====================
    
    def vector_similarity_search_tool(self) -> Tool:
        """Tool to find similar metrics using vector database"""
        
        @tool
        def search_similar_metrics(
            metric_names: List[str], 
            datasource_uid: str, 
            n_results: int = 5
        ) -> Dict[str, Any]:
            """
            Find similar metrics in the vector database.
            
            Args:
                metric_names: List of metric names to search for
                datasource_uid: UID of the datasource
                n_results: Number of similar metrics to return
                
            Returns:
                Dict with success status and similar_metrics list
            """
            try:
                similar = self.vectordb_handler.query_metrics_batch(
                    metric_names=metric_names,
                    ds_uid=datasource_uid,
                    n_results=n_results
                )
                
                print("search_similar_metrics Input:", metric_names, datasource_uid, n_results)
                print("search_similar_metrics Output:", similar)
                
                return {
                    "success": True,
                    "similar_metrics": similar,
                    "count": len(similar)
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "similar_metrics": []
                }
        
        return search_similar_metrics
    
    # ==================== TOOL 3: FETCH LABELS ====================
    
    def fetch_metric_labels_tool(self) -> Tool:
        """Tool to fetch actual labels for metrics from Prometheus"""
        
        @tool
        def fetch_metric_labels(
            prometheus_url: str,
            metric_names: List[str]
        ) -> Dict[str, Any]:
            """
            Fetch actual labels for given metrics from Prometheus.
            
            Args:
                prometheus_url: URL of Prometheus instance
                metric_names: List of metric names
                
            Returns:
                Dict with success status and metric_labels mapping
            """
            try:
                labels = self.prometheus_handler.get_metrics_labels(
                    ds_url=prometheus_url,
                    similar_metrics=metric_names
                )
                
                print("fetch_metric_labels Input:", prometheus_url, metric_names)
                print("fetch_metric_labels Output:", labels)
                
                return {
                    "success": True,
                    "metric_labels": labels,
                    "metrics_count": len(labels)
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "metric_labels": {}
                }
        
        return fetch_metric_labels
    
    # ==================== TOOL 4: GENERATE PROMQL ====================
    
    def generate_promql_tool(self) -> Tool:
        """Tool to generate PromQL queries"""
        
        @tool
        def generate_promql(query_context: Dict[str, Any]) -> Dict[str, Any]:
            """
            Generate PromQL query from context.
            
            Args:
                query_context: Dict containing datasource, query, metrics, labels
                
            Returns:
                Dict with success status and generated PromQL query
            """
            try:
                from llm.prompt import generate_promql_query
                
                result = generate_promql_query([query_context])
                
                if result.get('error'):
                    return {
                        "success": False,
                        "error": result['error']
                    }
                
                queries = result.get('result', [])
                
                print("generate_promql Input:", query_context)
                print("generate_promql Output:", queries)

                if queries:
                    return {
                        "success": True,
                        "query": queries[0].get('query', ''),
                        "datasource_uid": queries[0].get('mandatory_datasource_uuid', ''),
                        "original_query": queries[0].get('userquery', '')
                    }
                else:
                    return {
                        "success": False,
                        "error": "No query generated"
                    }
                    
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return generate_promql

    # ==================== TOOL 5: GENERATE SQL ====================
    
    def generate_sql_tool(self) -> Tool:
        """Tool to generate SQL queries"""
        
        @tool
        def generate_sql(
            query: str, 
            datasource_uid: str,
            metadata_context: str
        ) -> Dict[str, Any]:
            """
            Generate SQL query from natural language.
            
            Args:
                query: Natural language query
                datasource_uid: UID of PostgreSQL datasource
                metadata_context: Database schema metadata
                
            Returns:
                Dict with success status and generated SQL query
            """
            try:
                from llm.prompt import generate_sql_query
                
                result = generate_sql_query(
                    query=query,
                    datasource=datasource_uid,
                    metadata_context=metadata_context
                )
                
                # Parse LLM response
                if result.startswith("```"):
                    result = result.strip("`").strip()
                if result.lower().startswith("json"):
                    result = result[4:].strip()
                
                parsed = json.loads(result)
                
                if parsed.get('error'):
                    return {
                        "success": False,
                        "error": parsed['error']
                    }
                
                queries = parsed.get('result', [])
                if queries:
                    return {
                        "success": True,
                        "query": queries[0].get('query', ''),
                        "datasource_uid": queries[0].get('mandatory_datasource_uuid', ''),
                        "original_query": queries[0].get('userquery', '')
                    }
                else:
                    return {
                        "success": False,
                        "error": "No SQL generated"
                    }
                    
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Failed to parse SQL response: {str(e)}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return generate_sql

    # ==================== TOOL 6: VALIDATE QUERY ====================
    
    def validate_query_tool(self) -> Tool:
        """Tool to validate generated queries"""
        
        @tool
        def validate_query(
            query: str, 
            query_type: str,
            datasource_config: Dict[str, Any]
        ) -> Dict[str, Any]:
            """
            Validate a generated query (PromQL or SQL).
            
            Args:
                query: The query to validate
                query_type: Either 'prometheus' or 'postgres'
                datasource_config: Configuration for the datasource
                
            Returns:
                Dict with success status, is_valid flag, and error list
            """
            try:
                errors = []
                
                if query_type == 'prometheus':
                    # Basic PromQL validation
                    if not query or len(query.strip()) == 0:
                        errors.append("Empty PromQL query")
                    if '{' in query and '}' not in query:
                        errors.append("Unmatched braces in PromQL")
                    if '(' in query and ')' not in query:
                        errors.append("Unmatched parentheses in PromQL")
                        
                elif query_type == 'postgres':
                    # Basic SQL validation
                    if not query or len(query.strip()) == 0:
                        errors.append("Empty SQL query")
                    query_upper = query.upper()
                    if 'SELECT' not in query_upper:
                        errors.append("SQL query must contain SELECT")
                    # Check for balanced quotes
                    if query.count('"') % 2 != 0:
                        errors.append("Unmatched quotes in SQL")
                
                return {
                    "success": True,
                    "is_valid": len(errors) == 0,
                    "errors": errors,
                    "query": query
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "is_valid": False,
                    "errors": [str(e)]
                }
        
        return validate_query
    
    # ==================== TOOL 7: GENERATE DASHBOARD ====================
    
    def generate_dashboard_tool(self) -> Tool:
        """Tool to generate Grafana dashboard JSON"""
        
        @tool
        def generate_dashboard(query_responses: List[Dict[str, Any]]) -> Dict[str, Any]:
            """
            Generate Grafana dashboard JSON from query responses.
            
            Args:
                query_responses: List of query response dicts with datasource_uid and query
                
            Returns:
                Dict with success status and dashboard_json
            """
            try:
                from llm.prompt import generate_grafana_dashboard
                
                dashboard_json = generate_grafana_dashboard({
                    "result": query_responses
                })
                
                if dashboard_json.get('error'):
                    return {
                        "success": False,
                        "error": dashboard_json['error']
                    }
                
                return {
                    "success": True,
                    "dashboard_json": dashboard_json,
                    "panel_count": len(dashboard_json.get('panels', []))
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return generate_dashboard
    
    # ==================== TOOL 8: DEPLOY DASHBOARD ====================
    
    def deploy_dashboard_tool(self) -> Tool:
        """Tool to deploy dashboard to Grafana"""
        
        @tool
        def deploy_dashboard(dashboard_json: Dict[str, Any]) -> Dict[str, Any]:
            """
            Deploy dashboard to Grafana.
            
            Args:
                dashboard_json: Complete dashboard JSON specification
                
            Returns:
                Dict with success status, URL, and UID
            """
            try:
                result = self.grafana_handler.apply_dashboard(dashboard_json)
                
                if result.get('error'):
                    return {
                        "success": False,
                        "error": result['error']
                    }
                
                return {
                    "success": True,
                    "url": result.get('url', ''),
                    "uid": result.get('uid', ''),
                    "message": "Dashboard deployed successfully"
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return deploy_dashboard
    
    # ==================== TOOL 9: FETCH DATASOURCES ====================
    
    def fetch_datasources_tool(self) -> Tool:
        """Tool to fetch available datasources from Grafana"""
        
        @tool
        def fetch_datasources() -> Dict[str, Any]:
            """
            Fetch all available datasources from Grafana.
            
            Returns:
                Dict with success status and list of datasources
            """
            try:
                datasources = self.grafana_handler.fetch_datasources()
                
                return {
                    "success": True,
                    "datasources": datasources,
                    "count": len(datasources)
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "datasources": []
                }
        
        return fetch_datasources