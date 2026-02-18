"""
# tools/postgres_tools.py
PostgreSQL tools for schema introspection and query execution
Supports metadata loading and SQL generation
"""

import logging
from typing import Dict, List, Optional, Any
import yaml
from pathlib import Path
import asyncpg
import json

logger = logging.getLogger(__name__)


class PostgreSQLClient:
    """
    PostgreSQL client for schema operations and queries
    """
    
    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL client
        
        Args:
            connection_string: PostgreSQL connection string
            Example: postgresql://user:pass@localhost:5432/dbname
        """
        self.connection_string = connection_string
        logger.info("PostgreSQL client initialized")
    
    
    async def test_connection(self) -> bool:
        """
        Test database connection
        
        Returns:
            True if connection successful
        """
        try:
            conn = await asyncpg.connect(self.connection_string)
            await conn.close()
            logger.info("PostgreSQL connection test successful")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection test failed: {e}")
            return False
    
    
    async def introspect_schema(self, schema: str = "public") -> Dict[str, Any]:
        """
        Introspect database schema dynamically
        
        Args:
            schema: Schema name to introspect
        
        Returns:
            Schema metadata dictionary
        """
        try:
            conn = await asyncpg.connect(self.connection_string)
            
            # Query to get all tables and their columns
            query = """
            SELECT 
                t.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default
            FROM 
                information_schema.tables t
            JOIN 
                information_schema.columns c 
                ON t.table_name = c.table_name
            WHERE 
                t.table_schema = $1
                AND t.table_type = 'BASE TABLE'
            ORDER BY 
                t.table_name, c.ordinal_position;
            """
            
            rows = await conn.fetch(query, schema)
            await conn.close()
            
            # Organize into metadata structure
            tables = {}
            for row in rows:
                table_name = row['table_name']
                if table_name not in tables:
                    tables[table_name] = {
                        'table_name': table_name,
                        'columns': [],
                        'columns_metadata': {}
                    }
                
                col_info = f"{row['data_type']}" + (
                    " (nullable)" if row['is_nullable'] == 'YES' else ""
                )
                
                tables[table_name]['columns'].append(row['column_name'])
                tables[table_name]['columns_metadata'][row['column_name']] = col_info
            
            metadata = {
                'schema': schema,
                'tables': list(tables.values())
            }
            
            logger.info(f"Introspected {len(tables)} tables from schema '{schema}'")
            return metadata
        
        except Exception as e:
            logger.error(f"Schema introspection failed: {e}")
            return {'schema': schema, 'tables': []}
    
    
    async def execute_query(
        self,
        query: str,
        params: Optional[List] = None
    ) -> List[Dict]:
        """
        Execute SQL query and return results
        
        Args:
            query: SQL query string
            params: Optional query parameters
        
        Returns:
            List of result rows as dictionaries
        """
        try:
            conn = await asyncpg.connect(self.connection_string)
            
            if params:
                rows = await conn.fetch(query, *params)
            else:
                rows = await conn.fetch(query)
            
            await conn.close()
            
            # Convert to list of dicts
            results = [dict(row) for row in rows]
            
            logger.info(f"Query executed successfully, returned {len(results)} rows")
            return results
        
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    
    async def validate_query(self, query: str) -> tuple[bool, Optional[str]]:
        """
        Validate SQL query syntax without executing
        
        Args:
            query: SQL query to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            conn = await asyncpg.connect(self.connection_string)
            
            # Use EXPLAIN to validate without executing
            explain_query = f"EXPLAIN {query}"
            await conn.fetch(explain_query)
            
            await conn.close()
            
            logger.info("Query validation successful")
            return True, None
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Query validation failed: {error_msg}")
            return False, error_msg


class MetadataLoader:
    """
    Load PostgreSQL metadata from YAML files
    """
    
    def __init__(self, metadata_dir: str = "metadata"):
        """
        Initialize metadata loader
        
        Args:
            metadata_dir: Directory containing metadata YAML files
        """
        self.metadata_dir = Path(metadata_dir)
        logger.info(f"Metadata loader initialized for {self.metadata_dir}")
    
    
    def load_metadata(self, filename: str = "metadata.yaml") -> Dict:
        """
        Load metadata from YAML file
        
        Args:
            filename: YAML filename
        
        Returns:
            Metadata dictionary
        """
        metadata_file = self.metadata_dir / filename
        
        if not metadata_file.exists():
            logger.warning(f"Metadata file not found: {metadata_file}")
            return {'postgres': {'tables': []}}
        
        try:
            with open(metadata_file, 'r') as f:
                data = yaml.safe_load(f)
            
            logger.info(f"Loaded metadata from {metadata_file}")
            return data
        
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return {'postgres': {'tables': []}}
    
    
    def save_metadata(self, metadata: Dict, filename: str = "metadata.yaml"):
        """
        Save metadata to YAML file
        
        Args:
            metadata: Metadata dictionary
            filename: Output filename
        """
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = self.metadata_dir / filename
        
        try:
            with open(metadata_file, 'w') as f:
                yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Saved metadata to {metadata_file}")
        
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")


# ===== TOOL FUNCTIONS (for LangGraph) =====

async def load_postgres_metadata() -> Dict:
    """
    LangGraph tool: Load PostgreSQL metadata from YAML
    
    Returns:
        Metadata dictionary
    """
    loader = MetadataLoader()
    metadata = loader.load_metadata()
    return metadata.get('postgres', {'tables': []})


async def introspect_postgres_schema(
    connection_string: str,
    schema: str = "public"
) -> Dict:
    """
    LangGraph tool: Dynamically introspect PostgreSQL schema
    
    Args:
        connection_string: PostgreSQL connection string
        schema: Schema name
    
    Returns:
        Schema metadata
    """
    client = PostgreSQLClient(connection_string)
    return await client.introspect_schema(schema)


async def execute_postgres_query(
    connection_string: str,
    query: str
) -> List[Dict]:
    """
    LangGraph tool: Execute PostgreSQL query
    
    Args:
        connection_string: PostgreSQL connection string
        query: SQL query
    
    Returns:
        Query results
    """
    client = PostgreSQLClient(connection_string)
    return await client.execute_query(query)


async def validate_postgres_query(
    connection_string: str,
    query: str
) -> tuple[bool, Optional[str]]:
    """
    LangGraph tool: Validate SQL query
    
    Args:
        connection_string: PostgreSQL connection string
        query: SQL query
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    client = PostgreSQLClient(connection_string)
    return await client.validate_query(query)