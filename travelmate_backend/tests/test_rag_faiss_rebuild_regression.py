import os
from unittest.mock import MagicMock, patch

from app.services import rag_engine as rag_mod
from app.services.rag_engine import init_vector_store


def test_force_rebuild_rebuilds_even_when_vector_store_is_initialized():
    """init_vector_store(force_rebuild=True) must rebuild even when vector_store is already initialized."""
    old_vs = MagicMock(name="initial_vector_store")
    new_vs = MagicMock(name="rebuilt_vector_store")

    rag_mod.vector_store = old_vs
    try:
        with patch.object(rag_mod, "FAISS") as mock_faiss, \
             patch.object(rag_mod, "PyPDFLoader") as mock_loader, \
             patch.object(rag_mod, "get_embeddings", return_value=MagicMock()), \
             patch("os.listdir", return_value=["test.pdf"]), \
             patch("os.path.exists", return_value=True), \
             patch.object(rag_mod, "_save_index") as mock_save:

            mock_loader_inst = MagicMock()
            mock_loader_inst.load_and_split.return_value = [MagicMock()]
            mock_loader.return_value = mock_loader_inst
            mock_faiss.from_documents.return_value = new_vs

            # Call with force_rebuild=True while vector_store is already old_vs
            init_vector_store(force_rebuild=True)

            # Verification:
            # 1. FAISS.from_documents must have been called (rebuild happened)
            assert mock_faiss.from_documents.called
            # 2. _save_index must have persisted the new vector store
            assert mock_save.called
            # 3. vector_store must now be new_vs, replacing old_vs
            assert rag_mod.vector_store is new_vs
            assert rag_mod.vector_store is not old_vs
    finally:
        rag_mod.vector_store = None


def test_no_force_rebuild_preserves_initialized_vector_store():
    """init_vector_store(force_rebuild=False) preserves initialized vector_store and does not rebuild."""
    existing_vs = MagicMock(name="existing_vector_store")
    rag_mod.vector_store = existing_vs

    try:
        with patch.object(rag_mod, "FAISS") as mock_faiss, \
             patch.object(rag_mod, "_load_index") as mock_load, \
             patch.dict(os.environ, {"FORCE_RAG_REBUILD": "0"}):

            init_vector_store(force_rebuild=False)

            # Neither rebuild nor disk reload should be invoked
            assert not mock_faiss.from_documents.called
            assert not mock_load.called
            assert rag_mod.vector_store is existing_vs
    finally:
        rag_mod.vector_store = None


def test_env_force_rag_rebuild_triggers_rebuild_when_initialized():
    """FORCE_RAG_REBUILD=true environment variable triggers a rebuild even when initialized."""
    old_vs = MagicMock(name="old_vs")
    new_vs = MagicMock(name="new_vs")
    rag_mod.vector_store = old_vs

    try:
        with patch.object(rag_mod, "FAISS") as mock_faiss, \
             patch.object(rag_mod, "PyPDFLoader") as mock_loader, \
             patch.object(rag_mod, "get_embeddings", return_value=MagicMock()), \
             patch("os.listdir", return_value=["guide.pdf"]), \
             patch("os.path.exists", return_value=True), \
             patch.object(rag_mod, "_save_index"), \
             patch.dict(os.environ, {"FORCE_RAG_REBUILD": "true"}):

            mock_loader_inst = MagicMock()
            mock_loader_inst.load_and_split.return_value = [MagicMock()]
            mock_loader.return_value = mock_loader_inst
            mock_faiss.from_documents.return_value = new_vs

            init_vector_store(force_rebuild=False)

            assert mock_faiss.from_documents.called
            assert rag_mod.vector_store is new_vs
    finally:
        rag_mod.vector_store = None


def test_normal_cached_loading_from_persisted_index():
    """When vector_store is None and disk index is current, loads cached index from disk without PDF rebuild."""
    rag_mod.vector_store = None
    persisted_vs = MagicMock(name="persisted_vs")

    try:
        with patch.object(rag_mod, "_index_is_current", return_value=True), \
             patch.object(rag_mod, "_load_index", return_value=persisted_vs) as mock_load, \
             patch.object(rag_mod, "FAISS") as mock_faiss, \
             patch.dict(os.environ, {"FORCE_RAG_REBUILD": "false"}):

            init_vector_store(force_rebuild=False)

            assert mock_load.called
            assert not mock_faiss.from_documents.called
            assert rag_mod.vector_store is persisted_vs
    finally:
        rag_mod.vector_store = None
