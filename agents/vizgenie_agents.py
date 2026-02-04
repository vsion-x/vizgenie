# agents/vizgenie_agents.py
# Agent node implementations for VizGenie workflow

from typing import Dict, Any, List
from datetime import datetime
from state.graph_state import (
    VizGenieState, 
    ProcessingStage, 
    QueryType,
    MetricsContext,
    GeneratedQuery,
    DashboardSpec
)
import json


class VizGenieAgents:
    """Collection of agent nodes for VizGenie workflow"""
    
    def __init__(self, tools: Any):
        """
        Initialize agents with tools
        
        Args:
            tools: VizGenieTools instance
        """
        self.tools = tools
    
    def log_execution(self, state: VizGenieState, agent: str, message: str, 
                     metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Helper to log execution steps"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "stage": state['current_stage'],
            "message": message,
            "metadata": metadata or {}
        }
        return {"execution_log": [log_entry]}
    
    def initialize_node(self, state: VizGenieState) -> Dict[str, Any]:
        """
        Initialize the workflow state
        
        Args:
            state: Current state
            
        Returns:
            Updated state dict
        """
        updates = {
            "current_stage": ProcessingStage.INITIALIZED,
            "current_query_index": 0,
            "retry_count": 0,
            "max_retries": 3,
            "start_time": datetime.now().isoformat(),
            "metrics_contexts": [],
            "generated_queries": [],
            "errors": [],
            "execution_log": []
        }
        
        updates.update(
            self.log_execution(
                state, 
                "InitializationAgent",
                f"Workflow initialized with {len(state['user_queries'])} queries"
            )
        )
        
        return updates
    
    def extract_intent_node(self, state: VizGenieState) -> Dict[str, Any]:
        """
        Extract user intent and plan execution
        
        Args:
            state: Current state
            
        Returns:
            Updated state dict
        """
        try:
            queries = state['user_queries']
            
            # Classify query types and validate datasources
            classified_queries = []
            for query_ctx in queries:
                # Find matching datasource
                ds = next(
                    (d for d in state['available_datasources'] 
                     if d['name'] == query_ctx['datasource_name']),
                    None
                )
                
                if not ds:
                    return {
                        "errors": [{
                            "stage": "intent_extraction",
                            "error": f"Datasource '{query_ctx['datasource_name']}' not found",
                            "query": query_ctx['query_text']
                        }],
                        "current_stage": ProcessingStage.FAILED
                    }
                
                # Update query context with full datasource info
                query_ctx['datasource_uid'] = ds['uid']
                query_ctx['datasource_type'] = ds.get('type', ds['name'])
                query_ctx['query_type'] = (
                    QueryType.PROMETHEUS if ds['name'] == 'prometheus' 
                    else QueryType.POSTGRES
                )
                classified_queries.append(query_ctx)
            
            updates = {
                "user_queries": classified_queries,
                "current_stage": ProcessingStage.INTENT_EXTRACTED,
            }
            
            updates.update(
                self.log_execution(
                    state,
                    "IntentExtractionAgent",
                    f"Intent extracted for {len(classified_queries)} queries",
                    {"query_types": [q['query_type'] for q in classified_queries]}
                )
            )
            
            return updates
            
        except Exception as e:
            return {
                "errors": [{
                    "stage": "intent_extraction",
                    "error": str(e)
                }],
                "current_stage": ProcessingStage.FAILED
            }
    
    def extract_metrics_node(self, state: VizGenieState) -> Dict[str, Any]:
        """
        Extract metrics and labels from queries
        
        Args:
            state: Current state
            
        Returns:
            Updated state dict
        """
        try:
            extract_tool = self.tools.extract_metrics_tool()
            metrics_contexts = []
            
            for query_ctx in state['user_queries']:
                # Only extract metrics for Prometheus queries
                if query_ctx['query_type'] == QueryType.PROMETHEUS:
                    result = extract_tool.invoke({
                        "query": query_ctx['query_text'],
                        "datasource_name": query_ctx['datasource_name']
                    })
                    
                    if not result.get('success'):
                        return {
                            "errors": [{
                                "stage": "metrics_extraction",
                                "error": result.get('error', 'Unknown error'),
                                "query": query_ctx['query_text']
                            }],
                            "current_stage": ProcessingStage.FAILED
                        }
                    
                    metrics_contexts.append({
                        "suggested_metrics": result['suggested_metrics'],
                        "suggested_labels": result['suggested_labels'],
                        "similar_metrics": [],
                        "metric_labels": {}
                    })
                else:
                    # For PostgreSQL, we don't need metric extraction
                    metrics_contexts.append({
                        "suggested_metrics": [],
                        "suggested_labels": [],
                        "similar_metrics": [],
                        "metric_labels": {}
                    })
            
            updates = {
                "metrics_contexts": metrics_contexts,
                "current_stage": ProcessingStage.METRICS_EXTRACTED
            }
            
            updates.update(
                self.log_execution(
                    state,
                    "MetricsExtractionAgent",
                    "Metrics extracted from queries",
                    {"contexts_count": len(metrics_contexts)}
                )
            )
            
            return updates
            
        except Exception as e:
            return {
                "errors": [{
                    "stage": "metrics_extraction",
                    "error": str(e)
                }],
                "current_stage": ProcessingStage.FAILED
            }
    
    def vector_search_node(self, state: VizGenieState) -> Dict[str, Any]:
        """
        Perform vector similarity search for metrics
        
        Args:
            state: Current state
            
        Returns:
            Updated state dict
        """
        try:
            search_tool = self.tools.vector_similarity_search_tool()
            fetch_labels_tool = self.tools.fetch_metric_labels_tool()
            
            updated_contexts = []
            
            for idx, query_ctx in enumerate(state['user_queries']):
                metrics_ctx = state['metrics_contexts'][idx].copy()
                
                # Only search for Prometheus queries
                if query_ctx['query_type'] == QueryType.PROMETHEUS:
                    # Vector similarity search
                    search_result = search_tool.invoke({
                        "metric_names": metrics_ctx['suggested_metrics'],
                        "datasource_uid": query_ctx['datasource_uid'],
                        "n_results": 5
                    })
                    
                    if not search_result.get('success'):
                        return {
                            "errors": [{
                                "stage": "vector_search",
                                "error": search_result.get('error', 'Search failed'),
                                "query": query_ctx['query_text']
                            }],
                            "current_stage": ProcessingStage.FAILED
                        }
                    
                    similar_metrics = search_result['similar_metrics']
                    metrics_ctx['similar_metrics'] = similar_metrics
                    
                    # Fetch actual labels from Prometheus
                    if similar_metrics:
                        labels_result = fetch_labels_tool.invoke({
                            "prometheus_url": state['prometheus_url'],
                            "metric_names": similar_metrics
                        })
                        
                        if labels_result.get('success'):
                            metrics_ctx['metric_labels'] = labels_result['metric_labels']
                
                updated_contexts.append(metrics_ctx)
            
            updates = {
                "metrics_contexts": updated_contexts,
                "current_stage": ProcessingStage.SIMILARITY_SEARCHED
            }
            
            updates.update(
                self.log_execution(
                    state,
                    "VectorSearchAgent",
                    "Vector similarity search completed",
                    {"contexts_updated": len(updated_contexts)}
                )
            )
            
            return updates
            
        except Exception as e:
            return {
                "errors": [{
                    "stage": "vector_search",
                    "error": str(e)
                }],
                "current_stage": ProcessingStage.FAILED
            }
    
    def generate_query_node(self, state: VizGenieState) -> Dict[str, Any]:
        """
        Generate PromQL or SQL queries
        
        Args:
            state: Current state
            
        Returns:
            Updated state dict
        """
        try:
            promql_tool = self.tools.generate_promql_tool()
            sql_tool = self.tools.generate_sql_tool()
            
            generated_queries = []
            
            for idx, query_ctx in enumerate(state['user_queries']):
                if query_ctx['query_type'] == QueryType.PROMETHEUS:
                    # Generate PromQL
                    metrics_ctx = state['metrics_contexts'][idx]
                    
                    query_context = {
                        "datasource": query_ctx['datasource_uid'],
                        "original_query": query_ctx['query_text'],
                        "similar_metrics": metrics_ctx['similar_metrics'],
                        "labels": metrics_ctx['metric_labels']
                    }
                    
                    result = promql_tool.invoke({"query_context": query_context})
                    
                    if not result.get('success'):
                        return {
                            "errors": [{
                                "stage": "query_generation",
                                "error": result.get('error', 'PromQL generation failed'),
                                "query": query_ctx['query_text']
                            }],
                            "current_stage": ProcessingStage.FAILED
                        }
                    
                    generated_queries.append({
                        "datasource_uid": result['datasource_uid'],
                        "original_query": result['original_query'],
                        "generated_query": result['query'],
                        "query_type": "prometheus",
                        "is_valid": False,
                        "validation_errors": None
                    })
                    
                elif query_ctx['query_type'] == QueryType.POSTGRES:
                    # Generate SQL
                    from handlers.postgres_handler import PostgresHandler
                    postgres_handler = PostgresHandler(state['postgres_url'])
                    metadata_context = postgres_handler.get_schema_context()
                    
                    result = sql_tool.invoke({
                        "query": query_ctx['query_text'],
                        "datasource_uid": query_ctx['datasource_uid'],
                        "metadata_context": metadata_context
                    })
                    
                    if not result.get('success'):
                        return {
                            "errors": [{
                                "stage": "query_generation",
                                "error": result.get('error', 'SQL generation failed'),
                                "query": query_ctx['query_text']
                            }],
                            "current_stage": ProcessingStage.FAILED
                        }
                    
                    generated_queries.append({
                        "datasource_uid": result['datasource_uid'],
                        "original_query": result['original_query'],
                        "generated_query": result['query'],
                        "query_type": "postgres",
                        "is_valid": False,
                        "validation_errors": None
                    })
            
            updates = {
                "generated_queries": generated_queries,
                "current_stage": ProcessingStage.QUERY_GENERATED
            }
            
            updates.update(
                self.log_execution(
                    state,
                    "QueryGenerationAgent",
                    f"Generated {len(generated_queries)} queries",
                    {"query_types": [q['query_type'] for q in generated_queries]}
                )
            )
            
            return updates
            
        except Exception as e:
            return {
                "errors": [{
                    "stage": "query_generation",
                    "error": str(e)
                }],
                "current_stage": ProcessingStage.FAILED
            }
    
    def validate_query_node(self, state: VizGenieState) -> Dict[str, Any]:
        """
        Validate generated queries
        
        Args:
            state: Current state
            
        Returns:
            Updated state dict
        """
        try:
            validate_tool = self.tools.validate_query_tool()
            
            validated_queries = []
            all_valid = True
            
            for gen_query in state['generated_queries']:
                result = validate_tool.invoke({
                    "query": gen_query['generated_query'],
                    "query_type": gen_query['query_type'],
                    "datasource_config": {}
                })
                
                gen_query['is_valid'] = result.get('is_valid', False)
                gen_query['validation_errors'] = result.get('errors', [])
                
                if not gen_query['is_valid']:
                    all_valid = False
                
                validated_queries.append(gen_query)
            
            if not all_valid and state['retry_count'] < state['max_retries']:
                # Need to retry
                return {
                    "generated_queries": validated_queries,
                    "retry_count": state['retry_count'] + 1,
                    "errors": [{
                        "stage": "validation",
                        "error": "Query validation failed, retrying",
                        "retry_count": state['retry_count'] + 1
                    }]
                }
            
            updates = {
                "generated_queries": validated_queries,
                "current_stage": ProcessingStage.QUERY_VALIDATED
            }
            
            updates.update(
                self.log_execution(
                    state,
                    "ValidationAgent",
                    f"Validated {len(validated_queries)} queries",
                    {"all_valid": all_valid}
                )
            )
            
            return updates
            
        except Exception as e:
            return {
                "errors": [{
                    "stage": "validation",
                    "error": str(e)
                }],
                "current_stage": ProcessingStage.FAILED
            }
    
    def generate_dashboard_node(self, state: VizGenieState) -> Dict[str, Any]:
        """
        Generate dashboard JSON
        
        FIXED: Validates panel count matches query count
        """
        try:
            dashboard_tool = self.tools.generate_dashboard_tool()
            
            # PREPARE QUERY RESPONSES - ONLY VALID QUERIES
            
            query_responses = []
            for gen_query in state['generated_queries']:
                if gen_query['is_valid']:
                    query_responses.append({
                        "mandatory_datasource_uuid": gen_query['datasource_uid'],
                        "userquery": gen_query['original_query'],
                        "query": gen_query['generated_query']
                    })
            
            # ✅ Validation: Must have at least one valid query
            if not query_responses:
                return {
                    "errors": [{
                        "stage": "dashboard_generation",
                        "error": "No valid queries to generate dashboard"
                    }],
                    "current_stage": ProcessingStage.FAILED
                }
            
            print(f"📊 Generating dashboard with {len(query_responses)} queries:")
            for qr in query_responses:
                print(f"  - {qr['userquery']}: {qr['query'][:50]}...")
            
            # CALL DASHBOARD GENERATION TOOL
            
            result = dashboard_tool.invoke({
                "query_responses": query_responses
            })
            
            if not result.get('success'):
                return {
                    "errors": [{
                        "stage": "dashboard_generation",
                        "error": result.get('error', 'Dashboard generation failed')
                    }],
                    "current_stage": ProcessingStage.FAILED
                }
            
            dashboard_json = result['dashboard_json']
            
            # ✅ VALIDATE PANEL COUNT
            
            panels = dashboard_json.get('panels', [])
            expected_count = len(query_responses)
            actual_count = len(panels)
            
            if actual_count != expected_count:
                print(f"⚠️  WARNING: Expected {expected_count} panels, got {actual_count}")
                
                # Remove duplicates by title
                seen_titles = set()
                unique_panels = []
                for panel in panels:
                    title = panel.get('title', '')
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        unique_panels.append(panel)
                
                # Trim to expected count
                dashboard_json['panels'] = unique_panels[:expected_count]
                
                print(f"✅ Fixed to {len(dashboard_json['panels'])} unique panels")
            
            # ✅ VALIDATE DATASOURCE TYPES
            
            # Get datasource types from input
            input_datasources = set([qr['mandatory_datasource_uuid'] for qr in query_responses])
            
            # Remove panels with datasources not in input
            valid_panels = []
            for panel in dashboard_json['panels']:
                ds = panel.get('datasource', {})
                ds_uid = ds.get('uid', '') if isinstance(ds, dict) else ds
                
                if ds_uid in input_datasources:
                    valid_panels.append(panel)
                else:
                    print(f"⚠️  Removed panel '{panel.get('title', '')}' - datasource {ds_uid} not in input")
            
            dashboard_json['panels'] = valid_panels
            
            # CREATE DASHBOARD SPEC
            
            dashboard_spec = {
                "title": dashboard_json.get('title', 'Generated Dashboard'),
                "panels": dashboard_json.get('panels', []),
                "uid": dashboard_json.get('uid', ''),
                "deployed_url": None
            }
            
            updates = {
                "dashboard_spec": dashboard_spec,
                "current_stage": ProcessingStage.DASHBOARD_GENERATED
            }
            
            updates.update(
                self.log_execution(
                    state,
                    "DashboardGenerationAgent",
                    f"Dashboard generated with {len(dashboard_spec['panels'])} panels",
                    {
                        "panel_count": len(dashboard_spec['panels']),
                        "panel_titles": [p.get('title', '') for p in dashboard_spec['panels']]
                    }
                )
            )
            
            return updates
            
        except Exception as e:
            return {
                "errors": [{
                    "stage": "dashboard_generation",
                    "error": str(e)
                }],
                "current_stage": ProcessingStage.FAILED
            }


    def deploy_dashboard_node(self, state: VizGenieState) -> Dict[str, Any]:
        """
        Deploy dashboard to Grafana
        
        Args:
            state: Current state
            
        Returns:
            Updated state dict
        """
        try:
            deploy_tool = self.tools.deploy_dashboard_tool()
            
            # Reconstruct full dashboard JSON
            dashboard_json = {
                "title": state['dashboard_spec']['title'],
                "uid": state['dashboard_spec']['uid'],
                "panels": state['dashboard_spec']['panels'],
                "schemaVersion": 36
            }
            
            result = deploy_tool.invoke({
                "dashboard_json": dashboard_json
            })
            
            if not result.get('success'):
                return {
                    "errors": [{
                        "stage": "deployment",
                        "error": result.get('error', 'Deployment failed')
                    }],
                    "current_stage": ProcessingStage.FAILED
                }
            
            updates = {
                "deployment_result": result,
                "current_stage": ProcessingStage.DEPLOYED,
                "end_time": datetime.now().isoformat()
            }
            
            # Update dashboard spec with deployed URL
            dashboard_spec = state['dashboard_spec'].copy()
            dashboard_spec['deployed_url'] = result.get('url')
            updates['dashboard_spec'] = dashboard_spec
            
            updates.update(
                self.log_execution(
                    state,
                    "DeploymentAgent",
                    "Dashboard successfully deployed",
                    {"url": result.get('url')}
                )
            )
            
            return updates
            
        except Exception as e:
            return {
                "errors": [{
                    "stage": "deployment",
                    "error": str(e)
                }],
                "current_stage": ProcessingStage.FAILED,
                "end_time": datetime.now().isoformat()
            }
    
    def error_handler_node(self, state: VizGenieState) -> Dict[str, Any]:
        """
        Handle errors and decide on recovery strategy
        
        Args:
            state: Current state
            
        Returns:
            Updated state dict
        """
        errors = state.get('errors', [])
        
        if not errors:
            return {
                "current_stage": ProcessingStage.FAILED,
                "end_time": datetime.now().isoformat()
            }
        
        last_error = errors[-1]
        
        # Log the error
        log_entry = self.log_execution(
            state,
            "ErrorHandlerAgent",
            f"Error in {last_error.get('stage', 'unknown')}: {last_error.get('error', 'Unknown error')}"
        )
        
        return {
            "current_stage": ProcessingStage.FAILED,
            "end_time": datetime.now().isoformat(),
            **log_entry
        }