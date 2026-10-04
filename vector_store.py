import chromadb, os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

genai_client = None

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="food_knowledge", metadata={"hnsw:space": "cosine"})

def get_genai_client():
    global genai_client
    if genai_client is None:
        genai_client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=60000),
        )
    return genai_client

def embed_text(text):
    response = get_genai_client().models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
    )
    return response.embeddings[0].values

def embedding_query(text):
    response = get_genai_client().models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
    )
    return response.embeddings[0].values

def add_to_vector_store(docid, text, metadata=None):
    embedding = embed_text(text)
    collection.upsert(
        documents=[text],
        metadatas=[metadata or {}],
        ids=[docid],
        embeddings=[embedding]
    )
    return True
    
def search_vector_store(query, n_results=5):
    if collection.count() == 0:
        return []
    query_embedding = embedding_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    return results["documents"][0] if results["documents"] else []
    