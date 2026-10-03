import os, re
from collections import Counter
from typing import Dict
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

PDF_FOLDER = os.path.join(os.path.dirname(__file__), "..", "pdfs")
HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")

vector_store = None

# -------------------------------------------------
# EMBEDDINGS
# -------------------------------------------------
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"}
    )

# -------------------------------------------------
# LOAD PDFS → VECTOR STORE
# -------------------------------------------------
def init_vector_store():
    global vector_store
    docs = []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150
    )

    if not os.path.exists(PDF_FOLDER):
        os.makedirs(PDF_FOLDER)

    for file_name in os.listdir(PDF_FOLDER):
        if file_name.lower().endswith(".pdf"):
            path = os.path.join(PDF_FOLDER, file_name)
            loader = PyPDFLoader(path)
            pages = loader.load_and_split(text_splitter=splitter)
            docs.extend(pages)
            print(f"[RAG] Loaded {file_name} ({len(pages)} chunks)")

    if docs:
        vector_store = FAISS.from_documents(docs, get_embeddings())
        print(f"[RAG] VectorDB initialized with {len(docs)} chunks")
    else:
        vector_store = None
        print("[RAG] No PDFs found → VectorDB NOT initialized")

# -------------------------------------------------
# FALLBACK RECOMMENDER (No LLM)
# -------------------------------------------------
def fallback_recommendation(query: str, context: str) -> Dict:
    destination = None

    # Try to infer destination name from context or query
    match = re.search(r"(?:in|at|near)\s+([A-Z][a-zA-Z\s]+)", query)
    if match:
        destination = match.group(1).strip()
    else:
        destination = "Peaceful Nature Retreat"  # fallback default

    lowered = query.lower()

    # Infer mood
    if any(word in lowered for word in ["hike", "trek", "explore", "adventure"]):
        mood = "Adventure"
    elif any(word in lowered for word in ["couple", "honeymoon", "romantic"]):
        mood = "Romantic"
    else:
        mood = "Relaxing"

    # Infer budget
    if "luxury" in lowered or "expensive" in lowered:
        budget = "Luxury"
    elif "cheap" in lowered or "budget" in lowered or "low cost" in lowered:
        budget = "Low"
    else:
        budget = "Medium"

    # Infer type
    if "forest" in lowered:
        dtype = "Forest"
    elif "beach" in lowered:
        dtype = "Beach"
    elif "desert" in lowered:
        dtype = "Desert"
    elif "city" in lowered:
        dtype = "City"
    elif any(word in lowered for word in ["historic", "temple", "heritage", "fort"]):
        dtype = "Heritage"
    else:
        dtype = "Nature"

    best_time = "October to March"
    description = f"A calming, peaceful travel location near {destination}. Ideal for relaxation."

    return {
        "destination": destination,
        "mood": mood,
        "budget": budget,
        "type": dtype,
        "best_time": best_time,
        "description": description
    }


# -------------------------------------------------
# MAIN QUERY (RAG)
# -------------------------------------------------
def query_knowledge_base(query: str, top_k: int = 4) -> Dict:
    global vector_store

    print("🔍 [RAG] Received query:", query)

    if vector_store is None:
        print("❌ [RAG] Vector store not initialized")
        return {
            "error": "Knowledge base not initialized",
            "fallback": fallback_recommendation(query, "")
        }

    # Perform vector similarity search
    docs = vector_store.similarity_search(query, k=top_k)

    print(f"📄 [RAG] Retrieved {len(docs)} similar documents")

    for i, doc in enumerate(docs):
        print(f"  👉 Snippet {i+1}: {doc.page_content[:100].strip()}...")

    snippets = [
        {
            "text": d.page_content,
            "metadata": getattr(d, "metadata", {}),
            "score": None
        }
        for d in docs
    ]

    context = "\n\n".join([d.page_content for d in docs])

    fallback = fallback_recommendation(query, context)

    print(f"🧠 [RAG] Fallback destination from context: {fallback.get('destination')}")

    return {
        "snippets": snippets,
        "context": context,
        "best_destination": fallback.get("destination"),
        "fallback": fallback
    }
def ensure_initialized():
    global vector_store
    if vector_store is None:
        init_vector_store()
