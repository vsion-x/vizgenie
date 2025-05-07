import yaml
from pathlib import Path

class PostgresHandler:
    def __init__(self, url):
        self.metadata = self.load_metadata()
        self.url = url
        
    def load_metadata(self):
        metadata_path = Path(__file__).parent.parent / 'metadata' / 'metadata.yaml'
        with open(metadata_path) as f:
            return yaml.safe_load(f)

    def get_schema_context(self):
        context = []
        for table in self.metadata['postgres']['tables']:
            columns = [f"{col}: {desc}" for col, desc in table['columns_metadata'].items()]
            context.append(f"Table {table['table_name']} ({table['table_desc']}):\n" + "\n".join(columns))
        return "\n\n".join(context)
