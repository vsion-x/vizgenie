# handlers/postgres_handler.py
# Handler for PostgreSQL metadata operations

import yaml
from pathlib import Path
from typing import Dict, Any


class PostgresHandler:
    """Handler for PostgreSQL database metadata"""
    
    def __init__(self, url: str):
        """
        Initialize PostgreSQL handler
        
        Args:
            url: PostgreSQL connection string
        """
        self.url = url
        self.metadata = self.load_metadata()
        
    def load_metadata(self) -> Dict[str, Any]:
        """
        Load database schema metadata from YAML file
        
        Returns:
            Parsed metadata dictionary
        """
        metadata_path = Path(__file__).parent.parent / 'metadata' / 'metadata.yaml'
        
        try:
            with open(metadata_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Warning: metadata.yaml not found at {metadata_path}")
            return {"postgres": {"tables": []}}
        except Exception as e:
            print(f"Error loading metadata: {str(e)}")
            return {"postgres": {"tables": []}}

    def get_schema_context(self) -> str:
        """
        Get formatted schema context for LLM
        
        Returns:
            Formatted string describing database schema
        """
        context = []
        
        postgres_meta = self.metadata.get('postgres', {})
        db_name = postgres_meta.get('database_name', 'Unknown')
        db_desc = postgres_meta.get('database_desc', '')
        
        context.append(f"Database: {db_name}")
        if db_desc:
            context.append(f"Description: {db_desc}\n")
        
        for table in postgres_meta.get('tables', []):
            table_name = table.get('table_name', 'unknown')
            table_desc = table.get('table_desc', '')
            
            table_info = f"\nTable: {table_name}"
            if table_desc:
                table_info += f" - {table_desc}"
            context.append(table_info)
            
            # Add columns
            columns_meta = table.get('columns_metadata', {})
            for col_name, col_desc in columns_meta.items():
                context.append(f"  - {col_name}: {col_desc}")
        
        return "\n".join(context)
    
    def get_tables(self) -> list:
        """
        Get list of table names
        
        Returns:
            List of table name strings
        """
        tables = []
        postgres_meta = self.metadata.get('postgres', {})
        
        for table in postgres_meta.get('tables', []):
            tables.append(table.get('table_name'))
        
        return tables
    
    def get_columns(self, table_name: str) -> Dict[str, str]:
        """
        Get columns for a specific table
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dict mapping column names to descriptions
        """
        postgres_meta = self.metadata.get('postgres', {})
        
        for table in postgres_meta.get('tables', []):
            if table.get('table_name') == table_name:
                return table.get('columns_metadata', {})
        
        return {}