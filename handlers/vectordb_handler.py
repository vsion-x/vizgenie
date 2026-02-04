# handlers/vectordb_handler.py
# Handler for ChromaDB vector database operations

from chromadb import PersistentClient
from typing import List


class VectorDBHandler:
    """Handler for ChromaDB vector database operations"""
    
    def __init__(self, db_path: str = "./chroma_db"):
        """
        Initialize ChromaDB handler
        
        Args:
            db_path: Path to store ChromaDB data
        """
        self.client = PersistentClient(path=db_path)

    def get_collection(self, ds_uid: str):
        """
        Get or create a collection for a specific datasource
        
        Args:
            ds_uid: Datasource UID (used as collection name)
            
        Returns:
            ChromaDB collection object
        """
        return self.client.get_or_create_collection(name=ds_uid)

    def store_metrics(self, metrics: List[str], ds_uid: str) -> int:
        """
        Store metrics in the vector database
        
        Args:
            metrics: List of metric names to store
            ds_uid: Datasource UID
            
        Returns:
            Number of new metrics stored
        """
        try:
            collection = self.get_collection(ds_uid)
            
            # Get existing metrics
            existing = collection.get()['ids']
            
            # Filter out duplicates
            new_metrics = [m for m in metrics if m not in existing]
            
            if new_metrics:
                # Store new metrics (document = metric name, id = metric name)
                collection.add(
                    documents=new_metrics,
                    ids=new_metrics
                )
            
            return len(new_metrics)
            
        except Exception as e:
            print(f"Storage error: {str(e)}")
            return 0

    def query_metrics_batch(
        self, 
        metric_names: List[str], 
        ds_uid: str, 
        n_results: int = 5
    ) -> List[str]:
        """
        Query for similar metrics using vector similarity search
        
        Args:
            metric_names: List of metric names to search for
            ds_uid: Datasource UID
            n_results: Number of similar results to return per query
            
        Returns:
            Deduplicated list of similar metric names
        """
        try:
            collection = self.get_collection(ds_uid)
            
            # Perform batch query
            results = collection.query(
                query_texts=metric_names,
                n_results=n_results
            )
            
            # Flatten and deduplicate results
            all_metrics = []
            for docs in results['documents']:
                all_metrics.extend(docs)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_metrics = []
            for metric in all_metrics:
                if metric not in seen:
                    seen.add(metric)
                    unique_metrics.append(metric)
            
            return unique_metrics
            
        except Exception as e:
            print(f"Query error: {str(e)}")
            return []
    
    def delete_collection(self, ds_uid: str) -> bool:
        """
        Delete a collection
        
        Args:
            ds_uid: Datasource UID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete_collection(name=ds_uid)
            return True
        except Exception as e:
            print(f"Delete error: {str(e)}")
            return False
    
    def get_collection_count(self, ds_uid: str) -> int:
        """
        Get number of metrics in a collection
        
        Args:
            ds_uid: Datasource UID
            
        Returns:
            Count of metrics
        """
        try:
            collection = self.get_collection(ds_uid)
            return collection.count()
        except Exception as e:
            print(f"Count error: {str(e)}")
            return 0