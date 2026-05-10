import logging
import threading
from typing import List

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from django.conf import settings
                from sentence_transformers import SentenceTransformer
                model_name = getattr(settings, 'LEGAL_RAG', {}).get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
                logger.info("Loading embedding model: %s", model_name)
                _model = SentenceTransformer(model_name)
                logger.info("Embedding model ready")
    return _model


def embed_text(text: str) -> List[float]:
    vec = _get_model().encode([text], show_progress_bar=False)[0]
    return vec.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    vecs = _get_model().encode(texts, show_progress_bar=False, batch_size=32)
    return [v.tolist() for v in vecs]
