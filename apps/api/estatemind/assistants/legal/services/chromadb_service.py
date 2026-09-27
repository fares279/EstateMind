import os
import logging
import threading
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

_client = None
_collection = None
_chroma_lock = threading.Lock()


def _cfg():
    from django.conf import settings
    return getattr(settings, 'LEGAL_RAG', {})


def _get_collection():
    global _client, _collection
    if _collection is None:
        with _chroma_lock:
            if _collection is None:
                import chromadb
                cfg = _cfg()
                persist_dir = cfg.get('CHROMA_PERSIST_DIR', './legal_chroma')
                os.makedirs(persist_dir, exist_ok=True)

                settings = chromadb.Settings(anonymized_telemetry=False)
                _client = chromadb.PersistentClient(path=persist_dir, settings=settings)
                name = cfg.get('CHROMA_COLLECTION', 'estate_legal')

                try:
                    _collection = _client.get_collection(name)
                    logger.info("ChromaDB collection '%s' opened (%d docs)", name, _collection.count())
                except Exception:
                    _collection = _client.create_collection(
                        name=name,
                        metadata={"hnsw:space": "cosine"},
                    )
                    logger.info("ChromaDB collection '%s' created", name)
    return _collection


def get_document_count(collection_name: str | None = None) -> int:
    try:
        col = _get_collection_by_name(collection_name) if collection_name else _get_collection()
        return col.count()
    except Exception as exc:
        logger.warning("ChromaDB count failed: %s", exc)
        return 0


def reset_collection() -> None:
    """Delete and recreate the collection (used by --force re-index)."""
    global _client, _collection
    with _chroma_lock:
        import chromadb
        cfg = _cfg()
        persist_dir = cfg.get('CHROMA_PERSIST_DIR', './legal_chroma')
        os.makedirs(persist_dir, exist_ok=True)
        name = cfg.get('CHROMA_COLLECTION', 'estate_legal')

        if _client is None:
            _client = chromadb.PersistentClient(path=persist_dir, settings=chromadb.Settings(anonymized_telemetry=False))

        try:
            _client.delete_collection(name)
            logger.info("ChromaDB collection '%s' deleted", name)
        except Exception:
            pass

        _collection = _client.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection '%s' recreated", name)


def add_documents(
    ids: List[str],
    metadatas: List[Dict[str, Any]],
    documents: List[str],
    embeddings: List[List[float]],
) -> int:
    col = _get_collection()

    # Find IDs that already exist in the collection
    try:
        existing = set(col.get(ids=ids)['ids'])
    except Exception:
        existing = set()

    # Deduplicate: skip both already-stored IDs and duplicates within this batch
    seen = set(existing)
    new_ids, new_metas, new_docs, new_embs = [], [], [], []
    for i, doc_id in enumerate(ids):
        if doc_id not in seen:
            seen.add(doc_id)
            new_ids.append(doc_id)
            new_metas.append(metadatas[i])
            new_docs.append(documents[i])
            new_embs.append(embeddings[i])

    if new_ids:
        col.add(ids=new_ids, metadatas=new_metas, documents=new_docs, embeddings=new_embs)
        logger.info("Added %d documents to ChromaDB", len(new_ids))
    return len(new_ids)


def _get_collection_by_name(name: str):
    """Return a Chromadb collection object by name, creating it if missing."""
    # Reuse the same client instance but don't replace the global default collection
    global _client
    if _client is None:
        import chromadb
        cfg = _cfg()
        persist_dir = cfg.get('CHROMA_PERSIST_DIR', './legal_chroma')
        os.makedirs(persist_dir, exist_ok=True)
        settings = chromadb.Settings(anonymized_telemetry=False)
        _client = chromadb.PersistentClient(path=persist_dir, settings=settings)

    try:
        return _client.get_collection(name)
    except Exception:
        return _client.create_collection(name=name, metadata={"hnsw:space": "cosine"})


def query(embedding: List[float], n_results: int = 5, collection_name: str | None = None) -> Dict[str, Any]:
    """Query a chroma collection. If `collection_name` is provided, query that collection; otherwise use default."""
    if collection_name:
        col = _get_collection_by_name(collection_name)
    else:
        col = _get_collection()

    try:
        count = col.count()
    except Exception:
        return {'ids': [[]], 'metadatas': [[]], 'documents': [[]], 'distances': [[]]}

    if count == 0:
        return {'ids': [[]], 'metadatas': [[]], 'documents': [[]], 'distances': [[]]}

    n = min(n_results, count)
    return col.query(query_embeddings=[embedding], n_results=n)


def _client_instance():
    global _client
    if _client is None:
        import chromadb
        persist_dir = _cfg().get('CHROMA_PERSIST_DIR', './legal_chroma')
        os.makedirs(persist_dir, exist_ok=True)
        _client = chromadb.PersistentClient(path=persist_dir, settings=chromadb.Settings(anonymized_telemetry=False))
    return _client


def list_collection_names() -> List[str]:
    return [getattr(c, 'name', c) for c in _client_instance().list_collections()]


def index_collection(name: str, ids: List[str], metadatas: List[Dict[str, Any]],
                     documents: List[str], embeddings: List[List[float]]) -> int:
    """Create collection `name` (it must not exist yet) and fill it."""
    if name in list_collection_names():
        raise ValueError(f"Collection '{name}' already exists; collections are never overwritten.")
    col = _client_instance().create_collection(name=name, metadata={"hnsw:space": "cosine"})
    for start in range(0, len(ids), 500):
        end = start + 500
        col.add(ids=ids[start:end], metadatas=metadatas[start:end],
                documents=documents[start:end], embeddings=embeddings[start:end])
    logger.info("Indexed %d passages into new collection '%s'", len(ids), name)
    return col.count()
