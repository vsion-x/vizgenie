

import streamlit as st
from client import vectordb

def store_metrics(metrics, ds_uid):
    try:
        collection = vectordb.db.get_or_create_collection(name=ds_uid)
        existing = collection.get()['ids']
        new_metrics = [m for m in metrics if m not in existing]
        
        if new_metrics:
            collection.add(documents=new_metrics, ids=new_metrics)
        return len(new_metrics)
    except Exception as e:
        st.error(f"Storage error: {str(e)}")
        return 0


def query_metrics(user_query, ds_uid):
    """Query datasource-specific collection"""
    try:
        collection = vectordb.db.get_collection(name=ds_uid)
        results = collection.query(query_texts=[user_query], n_results=5)
        return results['documents'][0]
    except Exception as e:
        st.error(f"Query error: {str(e)}")
        return []
        

# Modified vector DB query function
def query_metrics_batch(metric_names: list, ds_uid: str, n_results: int = 3):
    """Batch query for multiple metrics"""
    try:
        collection = vectordb.db.get_collection(name=ds_uid)
        results = collection.query(
            query_texts=metric_names,  # Pass array directly
            n_results=n_results
        )
        # Flatten results from all queries
        return list(set([doc for docs in results['documents'] for doc in docs]))
    except Exception as e:
        st.error(f"Batch query error: {str(e)}")
        return []