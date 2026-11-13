import os, re, hashlib, json, logging, time
from collections import Counter
from typing import Dict, Optional
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

logger = logging.getLogger(__name__)

PDF_FOLDER = os.path.join(os.path.dirname(__file__), "..", "pdfs")
FAISS_INDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "faiss_index")
FAISS_MANIFEST_PATH = os.path.join(FAISS_INDEX_DIR, "manifest.json")
HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")
FORCE_RAG_REBUILD = os.getenv("FORCE_RAG_REBUILD", "").strip().lower() in ("1", "true", "yes")

vector_store = None


def get_embeddings():
    try:
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu", "local_files_only": True}
        )
    except Exception:
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"}
        )


# ---------------------------------------------------------------------------
# FAISS index persistence helpers
# ---------------------------------------------------------------------------
def _pdf_manifest() -> dict:
    """Build a manifest of PDF files: {filename: sha256_hex, ...} + sorted names list."""
    if not os.path.isdir(PDF_FOLDER):
        return {"files": {}}
    manifest: dict = {}
    for fname in sorted(os.listdir(PDF_FOLDER)):
        if fname.lower().endswith(".pdf"):
            fpath = os.path.join(PDF_FOLDER, fname)
            h = hashlib.sha256()
            with open(fpath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            manifest[fname] = h.hexdigest()
    return {"files": manifest}


def _save_manifest(manifest: dict) -> None:
    """Write manifest JSON alongside the FAISS index."""
    os.makedirs(FAISS_INDEX_DIR, exist_ok=True)
    with open(FAISS_MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def _load_manifest() -> Optional[dict]:
    """Load saved manifest, or None if missing / corrupt."""
    if not os.path.isfile(FAISS_MANIFEST_PATH):
        return None
    try:
        with open(FAISS_MANIFEST_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("[RAG] Could not read FAISS manifest: %s", exc)
        return None


def _index_is_current() -> bool:
    """Return True if a persisted FAISS index exists and matches the current PDFs."""
    faiss_file = os.path.join(FAISS_INDEX_DIR, "index.faiss")
    pkl_file = os.path.join(FAISS_INDEX_DIR, "index.pkl")
    if not (os.path.isfile(faiss_file) and os.path.isfile(pkl_file)):
        return False
    saved = _load_manifest()
    if saved is None:
        return False
    current = _pdf_manifest()
    return saved.get("files") == current.get("files")


def _save_index(vs) -> None:
    """Persist the FAISS vector store and manifest to disk."""
    try:
        os.makedirs(FAISS_INDEX_DIR, exist_ok=True)
        vs.save_local(FAISS_INDEX_DIR)
        _save_manifest(_pdf_manifest())
        logger.info("[RAG] FAISS index saved to %s", FAISS_INDEX_DIR)
    except Exception as exc:
        logger.error("[RAG] Failed to save FAISS index: %s", exc)


def _load_index():
    """Load a persisted FAISS index. Returns the vector store or None."""
    faiss_file = os.path.join(FAISS_INDEX_DIR, "index.faiss")
    if not os.path.isfile(faiss_file):
        return None
    try:
        embeddings = get_embeddings()
        vs = FAISS.load_local(
            FAISS_INDEX_DIR,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info("[RAG] FAISS index loaded from disk.")
        return vs
    except Exception as exc:
        logger.error(
            "[RAG] Failed to load persisted FAISS index (will rebuild): %s", exc
        )
        return None


# ---------------------------------------------------------------------------
# Vector store initialization with persistence
# ---------------------------------------------------------------------------
def init_vector_store(force_rebuild: bool = False):
    global vector_store
    env_force = os.getenv("FORCE_RAG_REBUILD", "").strip().lower() in ("1", "true", "yes")
    should_rebuild = force_rebuild or FORCE_RAG_REBUILD or env_force

    if not should_rebuild and vector_store is not None:
        return

    if not should_rebuild and _index_is_current():
        t0 = time.time()
        vs = _load_index()
        if vs is not None:
            vector_store = vs
            elapsed = time.time() - t0
            logger.info("[RAG] Loaded persisted index in %.2fs", elapsed)
            print(f"[RAG] VectorDB loaded from persisted index in {elapsed:.2f}s")
            return
        else:
            logger.warning("[RAG] Persisted index failed to load; rebuilding.")

    if should_rebuild:
        logger.info("[RAG] Forced rebuild requested.")

    # -- Build from PDFs --
    t0 = time.time()
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
        elapsed = time.time() - t0
        print(f"[RAG] VectorDB initialized with {len(docs)} chunks in {elapsed:.2f}s")
        logger.info("[RAG] VectorDB built from PDFs with %d chunks in %.2fs", len(docs), elapsed)
        _save_index(vector_store)
    else:
        vector_store = None
        print("[RAG] No PDFs found -> VectorDB NOT initialized")

def fallback_recommendation(query: str, context: str, destination_name: Optional[str] = None) -> Dict:
    destination = destination_name.strip() if destination_name and destination_name.strip() else None

    if not destination:
        match = re.search(r"(?:in|at|near|to|for)\s+([A-Z][a-zA-Z\s]+)", query)
        if match:
            candidate = match.group(1).strip()
            # Exclude generic travel keywords
            if candidate.lower() not in {"a trip", "vacation", "holiday", "travel", "adventure"}:
                destination = candidate

    lowered = query.lower()

    if any(word in lowered for word in ["hike", "trek", "explore", "adventure"]):
        mood = "Adventure"
    elif any(word in lowered for word in ["couple", "honeymoon", "romantic"]):
        mood = "Romantic"
    else:
        mood = "Relaxing"

    if "luxury" in lowered or "expensive" in lowered:
        budget = "Luxury"
    elif "cheap" in lowered or "budget" in lowered or "low cost" in lowered:
        budget = "Low"
    else:
        budget = "Medium"

    if "forest" in lowered:
        dtype = "Forest"
    elif "beach" in lowered or "coastal" in lowered:
        dtype = "Beach"
    elif "desert" in lowered:
        dtype = "Desert"
    elif "city" in lowered or "urban" in lowered:
        dtype = "City"
    elif any(word in lowered for word in ["historic", "temple", "heritage", "fort"]):
        dtype = "Heritage"
    else:
        dtype = "Nature"

    best_time = "October to March"
    target_name = destination if destination else "your selected destination"
    description = f"A calming, memorable travel experience in {target_name}. Ideal for {mood.lower()} trips."

    return {
        "destination": destination,
        "mood": mood,
        "budget": budget,
        "type": dtype,
        "best_time": best_time,
        "description": description
    }

def query_knowledge_base(query: str, top_k: int = 4, destination_name: Optional[str] = None) -> Dict:
    global vector_store

    print("[RAG] Received query:", query)

    target_dest = (destination_name or "").strip()
    if not target_dest:
        known_cities = [
            "Bangalore", "Bengaluru", "Goa", "Kerala", "Shimla", "Manali",
            "Ooty", "Coorg", "Rishikesh", "Darjeeling", "Mussoorie",
            "Gokarna", "Ganpatipule", "Pondicherry", "Puducherry",
            "Solang Valley", "Delhi", "New Delhi", "Mumbai", "Jaipur",
            "Agra", "Chennai", "Hyderabad", "Kolkata", "Varanasi"
        ]
        q_lower = query.lower()
        for city in known_cities:
            if city.lower() in q_lower:
                target_dest = city
                break

    if vector_store is None:
        print("[RAG] Vector store not initialized")
        fallback = fallback_recommendation(query, "", destination_name=target_dest)
        best_dest = target_dest or fallback.get("destination")
        return {
            "error": "Knowledge base not initialized",
            "best_destination": best_dest,
            "fallback": fallback,
            "snippets": [],
            "context": ""
        }

    docs = vector_store.similarity_search(query, k=top_k * 2)

    print(f"[RAG] Retrieved {len(docs)} candidate documents")

    if target_dest:
        dest_key = target_dest.lower()
        matching_docs = [d for d in docs if dest_key in d.page_content.lower()]
        if matching_docs:
            docs = matching_docs[:top_k]
        else:
            foreign_markers = [
                "gokarna", "ganpatipule", "pondicherry", "goa", "kerala backwaters",
                "kudle beach", "om beach", "miramar beach"
            ]
            if dest_key not in ("gokarna", "goa", "pondicherry", "puducherry", "ganpatipule"):
                uncontaminated = [
                    d for d in docs
                    if not any(marker in d.page_content.lower() for marker in foreign_markers)
                ]
                if uncontaminated:
                    docs = uncontaminated[:top_k]
                else:
                    docs = []
            else:
                docs = docs[:top_k]
    else:
        docs = docs[:top_k]

    for i, doc in enumerate(docs):
        print(f"  [RAG] Snippet {i+1}: {doc.page_content[:100].strip()}...")

    snippets = [
        {
            "text": d.page_content,
            "metadata": getattr(d, "metadata", {}),
            "score": None
        }
        for d in docs
    ]

    context = "\n\n".join([d.page_content for d in docs])

    fallback = fallback_recommendation(query, context, destination_name=target_dest)

    best_dest = target_dest or fallback.get("destination")
    print(f"[RAG] Fallback destination from context: {best_dest}")

    return {
        "snippets": snippets,
        "context": context,
        "best_destination": best_dest,
        "fallback": fallback
    }

def ensure_initialized():
    global vector_store
    if vector_store is None:
        init_vector_store()