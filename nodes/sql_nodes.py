"""
# nodes/sql_nodes.py
Nodes for deterministic PostgreSQL SQL workflow
Schema loading → SQL generation → Dashboard
"""

import logging
from schemas.state import AgentState
from llm.prompts import SQL_GENERATION_PROMPT
from llm.retry_handler import get_llm_handler

logger = logging.getLogger(__name__)


async def schema_loader_node(state: AgentState) -> AgentState:
    """
    Step 1: Load PostgreSQL schema metadata
    """
    from tools.postgres_tools import load_postgres_metadata
    
    try:
        metadata = await load_postgres_metadata()
        state['postgres_metadata'] = metadata
        logger.info(f"Loaded PostgreSQL metadata: {len(metadata.get('tables', []))} tables")
    
    except Exception as e:
        logger.error(f"Schema loading failed: {e}")
        state['error'] = f"Could not load database schema: {str(e)}"
        state['postgres_metadata'] = {}
    
    return state


async def sql_generation_node(state: AgentState) -> AgentState:
    """
    Step 2: Generate SQL query using LLM
    """
    user_query = state['user_query']
    metadata = state['postgres_metadata']
    datasource_uid = state['selected_datasource']['uid']
    
    # Format metadata for prompt
    metadata_text = _format_metadata_for_prompt(metadata)
    
    prompt = SQL_GENERATION_PROMPT.format(
        user_query=user_query,
        metadata_context=metadata_text,
        datasource_uid=datasource_uid
    )
    
    try:
        llm_handler = get_llm_handler()
        result = await llm_handler.call_llm(
            prompt=prompt,
            temperature=0.1,
            max_tokens=1500,
            response_format="json"
        )
        
        state['generated_query'] = result.get('query', '')
        state['query_type'] = 'sql'
        logger.info(f"Generated SQL: {state['generated_query']}")
    
    except Exception as e:
        logger.error(f"SQL generation failed: {e}")
        state['error'] = f"SQL generation failed: {str(e)}"
        state['fallback_mode'] = True
    
    return state


def _format_metadata_for_prompt(metadata: dict) -> str:
    """
    Format database schema metadata for LLM prompt
    """
    if not metadata or 'tables' not in metadata:
        return "No schema metadata available"
    
    formatted = []
    
    for table in metadata['tables']:
        table_name = table['table_name']
        table_desc = table.get('table_desc', '')
        
        formatted.append(f"Table: {table_name}")
        if table_desc:
            formatted.append(f"  Description: {table_desc}")
        
        formatted.append("  Columns:")
        for col_name, col_desc in table.get('columns_metadata', {}).items():
            formatted.append(f"    - {col_name}: {col_desc}")
        
        formatted.append("")  # Blank line between tables
    
    return "\n".join(formatted)