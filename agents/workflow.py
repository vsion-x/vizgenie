# agents/workflow.py
# LangGraph workflow orchestrator for VizGenie

from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from state.graph_state import VizGenieState, ProcessingStage
from agents.vizgenie_agents import VizGenieAgents
from tools.vizgenie_tools import VizGenieTools


class VizGenieWorkflow:
    """LangGraph workflow for VizGenie dashboard generation"""
    
    def __init__(self, handlers: dict):
        """
        Initialize workflow with handlers
        
        Args:
            handlers: Dict containing all handler instances
        """
        self.tools = VizGenieTools(handlers)
        self.agents = VizGenieAgents(self.tools)
        self.graph = None
        self.compiled_graph = None
        
    def create_graph(self) -> StateGraph:
        """
        Create the state graph for VizGenie workflow
        
        Returns:
            StateGraph instance
        """
        # Create the graph
        workflow = StateGraph(VizGenieState)
        
        # Add nodes
        workflow.add_node("initialize", self.agents.initialize_node)
        workflow.add_node("extract_intent", self.agents.extract_intent_node)
        workflow.add_node("extract_metrics", self.agents.extract_metrics_node)
        workflow.add_node("vector_search", self.agents.vector_search_node)
        workflow.add_node("generate_query", self.agents.generate_query_node)
        workflow.add_node("validate_query", self.agents.validate_query_node)
        workflow.add_node("generate_dashboard", self.agents.generate_dashboard_node)
        workflow.add_node("deploy_dashboard", self.agents.deploy_dashboard_node)
        workflow.add_node("error_handler", self.agents.error_handler_node)
        
        # Set entry point
        workflow.set_entry_point("initialize")
        
        # Add edges
        workflow.add_edge("initialize", "extract_intent")
        
        # Conditional edge after intent extraction
        workflow.add_conditional_edges(
            "extract_intent",
            self.route_after_intent,
            {
                "extract_metrics": "extract_metrics",
                "error": "error_handler"
            }
        )
        
        workflow.add_edge("extract_metrics", "vector_search")
        workflow.add_edge("vector_search", "generate_query")
        
        # Conditional edge after query generation
        workflow.add_conditional_edges(
            "generate_query",
            self.route_after_generation,
            {
                "validate": "validate_query",
                "error": "error_handler"
            }
        )
        
        # Conditional edge after validation
        workflow.add_conditional_edges(
            "validate_query",
            self.route_after_validation,
            {
                "generate_dashboard": "generate_dashboard",
                "retry": "generate_query",
                "error": "error_handler"
            }
        )
        
        # Conditional edge after dashboard generation
        workflow.add_conditional_edges(
            "generate_dashboard",
            self.route_after_dashboard_generation,
            {
                "deploy": "deploy_dashboard",
                "error": "error_handler"
            }
        )
        
        # Final edges
        workflow.add_edge("deploy_dashboard", END)
        workflow.add_edge("error_handler", END)
        
        self.graph = workflow
        return workflow
    
    def compile_graph(self, checkpointer=None):
        """
        Compile the graph with optional checkpointing
        
        Args:
            checkpointer: Optional checkpointer for persistence
            
        Returns:
            Compiled graph
        """
        if not self.graph:
            self.create_graph()
        
        if checkpointer is None:
            checkpointer = MemorySaver()
        
        self.compiled_graph = self.graph.compile(checkpointer=checkpointer)
        return self.compiled_graph
    
    def route_after_intent(
        self, 
        state: VizGenieState
    ) -> Literal["extract_metrics", "error"]:
        """
        Route after intent extraction
        
        Args:
            state: Current state
            
        Returns:
            Next node name
        """
        if state['current_stage'] == ProcessingStage.FAILED:
            return "error"
        return "extract_metrics"
    
    def route_after_generation(
        self,
        state: VizGenieState
    ) -> Literal["validate", "error"]:
        """
        Route after query generation
        
        Args:
            state: Current state
            
        Returns:
            Next node name
        """
        if state['current_stage'] == ProcessingStage.FAILED:
            return "error"
        return "validate"
    
    def route_after_validation(
        self,
        state: VizGenieState
    ) -> Literal["generate_dashboard", "retry", "error"]:
        """
        Route after query validation
        
        Args:
            state: Current state
            
        Returns:
            Next node name
        """
        if state['current_stage'] == ProcessingStage.FAILED:
            # Check if we should retry
            if state['retry_count'] < state['max_retries']:
                # Check if any queries are invalid
                invalid_queries = [
                    q for q in state['generated_queries'] 
                    if not q.get('is_valid', False)
                ]
                if invalid_queries:
                    return "retry"
            return "error"
        
        return "generate_dashboard"
    
    def route_after_dashboard_generation(
        self,
        state: VizGenieState
    ) -> Literal["deploy", "error"]:
        """
        Route after dashboard generation
        
        Args:
            state: Current state
            
        Returns:
            Next node name
        """
        if state['current_stage'] == ProcessingStage.FAILED:
            return "error"
        return "deploy"
    
    async def arun(self, initial_state: VizGenieState, config: dict = None):
        """
        Run the workflow asynchronously
        
        Args:
            initial_state: Initial state
            config: Optional configuration
            
        Returns:
            Final state
        """
        if not self.compiled_graph:
            self.compile_graph()
        
        if config is None:
            config = {"configurable": {"thread_id": "1"}}
        
        result = await self.compiled_graph.ainvoke(initial_state, config)
        return result
    
    def run(self, initial_state: VizGenieState, config: dict = None):
        """
        Run the workflow synchronously
        
        Args:
            initial_state: Initial state
            config: Optional configuration
            
        Returns:
            Final state
        """
        if not self.compiled_graph:
            self.compile_graph()
        
        if config is None:
            config = {"configurable": {"thread_id": "1"}}
        
        result = self.compiled_graph.invoke(initial_state, config)
        return result
    
    def stream(self, initial_state: VizGenieState, config: dict = None):
        """
        Stream the workflow execution
        
        Args:
            initial_state: Initial state
            config: Optional configuration
            
        Yields:
            State updates at each step
        """
        if not self.compiled_graph:
            self.compile_graph()
        
        if config is None:
            config = {"configurable": {"thread_id": "1"}}
        
        for output in self.compiled_graph.stream(initial_state, config):
            yield output
    
    def get_graph_visualization(self) -> str:
        """
        Get Mermaid visualization of the graph
        
        Returns:
            Mermaid diagram string
        """
        if not self.compiled_graph:
            self.compile_graph()
        
        try:
            from langgraph.graph import graph_to_mermaid
            return graph_to_mermaid(self.compiled_graph)
        except ImportError:
            return "Mermaid visualization requires additional dependencies"