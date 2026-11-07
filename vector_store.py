import logging
from threading import Lock
import config
from llm import embed_query, embed_documents
log = logging.getLogger(__name__)
_collection = None
_collection_lock = Lock()
_write_lock = Lock()

def get_collection():
    global _collection 
    if _collection is None:
        with _collection_lock:
            if _collection is None:
                import chromadb
                config.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
                client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
                _collection = client.get_or_create_collection(name = "food_knowledge", 
                    metadata={"hnsw:space": "cosine"})
    
    return _collection

def get_documents(where = None, ids = None):
    result = get_collection().get(
        where=where,
        ids=ids, include = ["documents"]
    )
    
    return dict(zip(result["ids"], result["documents"]))

def sync_documents(desired, where):
    existing = get_documents(where=where)
    changed = {doc_id: value for doc_id, value in desired.items() if existing.get(doc_id) != value[0]}
    stale = [doc_id for doc_id in existing if doc_id not in desired]
    upsert_document(changed)
    delete_documents(stale)
    
    return len(stale), len(changed)

def upsert_document(docs):
    if not docs:
        return
    ids = list(docs)
    text = [docs[doc_id][0] for doc_id in ids]
    metadata = [docs[doc_id][1] for doc_id in ids]
    embeddings = embed_documents(text)
    with _write_lock:
        get_collection().upsert(ids=ids, document=text, metadata=metadata, embeddings=embeddings)
        
def delete_documents(ids):
    if ids:
        with _write_lock:
            get_collection().delete(ids=list(ids))
   
def search_vector_store(query, n_results=5):
    collection=get_collection()
    if collection.count() == 0:
        return []
    results = collection.query(
        query_embeddings=[embed_query(query)],
        n_results=min(n_results, collection.count()),
        include = ["distances", "documents"]
    )
    
    documents = results["documents"][0] if results["documents"] else []
    distances = results["distances"][0] if results.get("distances") else [0] * len(documents)
    
    return [doc for doc, distance in zip(documents, distances) if distance <= config.RAG_MAX_DISTANCE]
    