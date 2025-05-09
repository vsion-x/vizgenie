import chromadb
from chromadb.config import Settings
from chromadb import PersistentClient
import streamlit as st

class VectorDBHandler:
    def __init__(self):
        self.client = PersistentClient(path="./chroma_db")

    def get_collection(self, ds_uid: str):
        """Get or create a collection named after the datasource UID."""
        return self.client.get_or_create_collection(name=ds_uid)

    def store_metrics(self, metrics: list, ds_uid: str):
        """Store metrics in a collection specific to the datasource."""
        try:
            collection = self.get_collection(ds_uid)
            existing = collection.get()['ids']
            new_metrics = [m for m in metrics if m not in existing]
            
            if new_metrics:
                collection.add(documents=new_metrics, ids=new_metrics)
            return len(new_metrics)
        except Exception as e:
            st.error(f"Storage error: {str(e)}")
            return 0

    def query_metrics_batch(self, metric_names: list, ds_uid: str, n_results: int = 3):
        """Query metrics from the datasource-specific collection."""
        try:
            collection = self.get_collection(ds_uid)
            results = collection.query(
                query_texts=metric_names,
                n_results=n_results
            )
            # Flatten and deduplicate results
            return list(set([doc for docs in results['documents'] for doc in docs]))
        except Exception as e:
            st.error(f"Batch query error: {str(e)}")
            return []