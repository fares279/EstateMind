"""Sentence-transformer models shared by the chatbot and the legal assistant.

Each model is loaded once per process, however many services use it.
"""
import logging
import threading

logger = logging.getLogger(__name__)

INTENT_MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'

_models: dict = {}
_lock = threading.Lock()


def get_sentence_model(name: str = INTENT_MODEL):
    model = _models.get(name)
    if model is None:
        with _lock:
            model = _models.get(name)
            if model is None:
                import torch
                from sentence_transformers import SentenceTransformer
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                logger.info('Loading sentence model %s on %s', name, device)
                model = SentenceTransformer(name, device=device)
                _models[name] = model
    return model
