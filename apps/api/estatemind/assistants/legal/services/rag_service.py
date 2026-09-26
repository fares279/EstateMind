import logging
import threading
import re
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

_indexed = False
_index_lock = threading.Lock()


def _ensure_indexed() -> None:
    """Index dataset into ChromaDB on first use if the collection is empty."""
    global _indexed
    if _indexed:
        return
    """Compatibility wrapper around the newer rag_engine implementation.

    This module keeps the original import paths used by views. It delegates
    to `legal.services.rag_engine` which integrates the new Router,
    Domain classifier, Hallucination detector and Citation builder.
    """

    from .rag_engine import ask_question, get_status  # re-export for backward compatibility

    def answer_question(question: str, top_k: int = 5):
        return ask_question(question)

