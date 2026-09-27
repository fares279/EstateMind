import logging
import threading
from typing import List

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _cfg() -> dict:
    from django.conf import settings
    return getattr(settings, 'LEGAL_RAG', {})


def model_name() -> str:
    return _cfg().get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading embedding model: %s", model_name())
                _model = SentenceTransformer(model_name())
                logger.info("Embedding model ready")
    return _model


def embed_text(text: str) -> List[float]:
    """Embed a search query (with the model's query prefix, if it uses one)."""
    prefix = _cfg().get('EMBEDDING_QUERY_PREFIX', '')
    vec = _get_model().encode([prefix + text], show_progress_bar=False, normalize_embeddings=True)[0]
    return vec.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed passages to index (with the model's passage prefix, if it uses one)."""
    prefix = _cfg().get('EMBEDDING_PASSAGE_PREFIX', '')
    vecs = _get_model().encode(
        [prefix + t for t in texts], show_progress_bar=False, batch_size=32, normalize_embeddings=True,
    )
    return [v.tolist() for v in vecs]
