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


def get_document_count() -> int:
    try:
        return _get_collection().count()
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


def query(embedding: List[float], n_results: int = 5) -> Dict[str, Any]:
    col = _get_collection()
    count = col.count()
    if count == 0:
        return {'metadatas': [[]], 'documents': [[]], 'distances': [[]]}
    n = min(n_results, count)
    return col.query(query_embeddings=[embedding], n_results=n)
