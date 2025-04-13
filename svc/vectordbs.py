

import streamlit as st
from client import vectordb

def store_metrics(metrics, ds_uid):
    """Store metrics in datasource-specific collection"""
    collection = vectordb.db.get_or_create_collection(name=ds_uid)
    existing = collection.get()['ids']
    new_metrics = [m for m in metrics if m not in existing]
    
    if new_metrics:
        collection.add(documents=new_metrics, ids=new_metrics)
    return len(new_metrics)


def query_metrics(user_query, ds_uid):
    """Query datasource-specific collection"""
    try:
        collection = vectordb.db.get_collection(name=ds_uid)
        results = collection.query(query_texts=[user_query], n_results=5)
        return results['documents'][0]
    except Exception as e:
        st.error(f"Query error: {str(e)}")
        return []
        