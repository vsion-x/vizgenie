"""
# tools/vectordb_tools.py
VectorDB tools using ChromaDB for metric similarity search
Supports per-datasource collections for isolation
"""

import logging
from typing import List, Dict, Optional
from chromadb import PersistentClient
from chromadb.config import Settings
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorDBClient:
    """
    ChromaDB client for metric storage and similarity search
    """
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize ChromaDB client
        
        Args:
            persist_directory: Path to persist ChromaDB data
        """
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self.client = PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        logger.info(f"VectorDB initialized at {self.persist_dir}")
    
    
    def get_collection(self, datasource_uid: str):
        """
        Get or create collection for specific datasource
        
        Args:
            datasource_uid: Unique datasource identifier
        
        Returns:
            ChromaDB collection
        """
        # Sanitize collection name (ChromaDB naming rules)
        collection_name = datasource_uid.replace('-', '_').replace('.', '_')
        
        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"datasource_uid": datasource_uid}
            )
            return collection
        except Exception as e:
            logger.error(f"Failed to get collection for {datasource_uid}: {e}")
            raise
    
    
    async def store_metrics(
        self,
        metrics: List[str],
        datasource_uid: str
    ) -> int:
        """
        Store metrics in VectorDB with deduplication
        
        Args:
            metrics: List of metric names
            datasource_uid: Datasource identifier
        
        Returns:
            Number of new metrics added
        """
        if not metrics:
            logger.warning("No metrics provided to store")
            return 0
        
        try:
            collection = self.get_collection(datasource_uid)
            
            # Get existing metrics
            existing = collection.get()
            existing_ids = set(existing['ids']) if existing['ids'] else set()
            
            # Filter new metrics
            new_metrics = [m for m in metrics if m not in existing_ids]
            
            if not new_metrics:
                logger.info(f"No new metrics to add for {datasource_uid}")
                return 0
            
            # Add to collection
            collection.add(
                documents=new_metrics,
                ids=new_metrics,
                metadatas=[{"datasource_uid": datasource_uid} for _ in new_metrics]
            )
            
            logger.info(f"Stored {len(new_metrics)} new metrics for {datasource_uid}")
            return len(new_metrics)
        
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")
            return 0
    
    
    async def query_similar_metrics(
        self,
        query_metrics: List[str],
        datasource_uid: str,
        n_results: int = 5
    ) -> List[str]:
        """
        Find similar metrics using semantic search
        
        Args:
            query_metrics: Metrics to search for
            datasource_uid: Datasource to search in
            n_results: Number of results per query
        
        Returns:
            Deduplicated list of similar metrics
        """
        if not query_metrics:
            logger.warning("No query metrics provided")
            return []
        
        try:
            collection = self.get_collection(datasource_uid)
            
            # Check if collection has data
            count = collection.count()
            if count == 0:
                logger.warning(f"Collection for {datasource_uid} is empty")
                return []
            
            # Query for similar metrics
            results = collection.query(
                query_texts=query_metrics,
                n_results=min(n_results, count)
            )
            
            # Flatten and deduplicate results
            similar_metrics = []
            seen = set()
            
            for docs in results['documents']:
                for doc in docs:
                    if doc not in seen:
                        similar_metrics.append(doc)
                        seen.add(doc)
            
            logger.info(f"Found {len(similar_metrics)} similar metrics for {datasource_uid}")
            return similar_metrics
        
        except Exception as e:
            logger.error(f"VectorDB query failed: {e}")
            # Fallback: return original query metrics
            return query_metrics[:n_results]
    
    
    def delete_collection(self, datasource_uid: str) -> bool:
        """
        Delete collection for a datasource
        
        Args:
            datasource_uid: Datasource identifier
        
        Returns:
            True if successful
        """
        try:
            collection_name = datasource_uid.replace('-', '_').replace('.', '_')
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection for {datasource_uid}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False
    
    
    def get_collection_stats(self, datasource_uid: str) -> Dict:
        """
        Get statistics for a datasource collection
        
        Args:
            datasource_uid: Datasource identifier
        
        Returns:
            Dictionary with collection stats
        """
        try:
            collection = self.get_collection(datasource_uid)
            count = collection.count()
            
            # Sample some metrics
            sample = collection.peek(limit=10)
            
            return {
                'datasource_uid': datasource_uid,
                'total_metrics': count,
                'sample_metrics': sample['ids'][:10] if sample['ids'] else []
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                'datasource_uid': datasource_uid,
                'total_metrics': 0,
                'error': str(e)
            }


# ===== GLOBAL INSTANCE =====

_vectordb_client: Optional[VectorDBClient] = None


def get_vectordb_client() -> VectorDBClient:
    """Get global VectorDB client instance"""
    global _vectordb_client
    if _vectordb_client is None:
        _vectordb_client = VectorDBClient()
    return _vectordb_client


# ===== TOOL FUNCTIONS (for LangGraph) =====

async def vector_similarity_search(
    metric_names: List[str],
    datasource_uid: str,
    n_results: int = 5
) -> List[str]:
    """
    LangGraph tool: Search for similar metrics
    
    Args:
        metric_names: Metrics to search for
        datasource_uid: Datasource UID
        n_results: Number of results
    
    Returns:
        List of similar metrics
    """
    client = get_vectordb_client()
    return await client.query_similar_metrics(
        query_metrics=metric_names,
        datasource_uid=datasource_uid,
        n_results=n_results
    )


async def store_metrics_in_vectordb(
    metrics: List[str],
    datasource_uid: str
) -> int:
    """
    LangGraph tool: Store metrics in VectorDB
    
    Args:
        metrics: List of metric names
        datasource_uid: Datasource UID
    
    Returns:
        Number of metrics stored
    """
    client = get_vectordb_client()
    return await client.store_metrics(
        metrics=metrics,
        datasource_uid=datasource_uid
    )