import chromadb
from chromadb.config import Settings
from chromadb import PersistentClient

# Initialize ChromaDB client with persistent storage
db = PersistentClient(path="./chroma_db")

collection = db.get_or_create_collection(name="metrics")