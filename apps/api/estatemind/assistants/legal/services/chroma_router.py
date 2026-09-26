import logging
from typing import Optional

from estatemind.assistants.legal.models import EmbeddingCollectionVersion

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2'


class ChromaRouter:
    """All ChromaDB queries MUST go through this router.
    Never hardcode a collection name in the RAG engine.
    """

    def get_active_collection(self, domain: str) -> str:
        record = EmbeddingCollectionVersion.objects.filter(
            domain=domain, is_active=True
        ).first()

        if not record:
            fallback = EmbeddingCollectionVersion.objects.filter(is_active=True).first()
            if fallback:
                logger.warning(
                    "No active collection for domain '%s'. Using fallback '%s'.",
                    domain, fallback.collection_name
                )
                return fallback.collection_name
            raise RuntimeError(f"No active ChromaDB collection for domain: {domain}")

        return record.collection_name

    def get_embedding_model_for_query(self, domain: str) -> str:
        record = EmbeddingCollectionVersion.objects.filter(domain=domain, is_active=True).first()
        return record.embedding_model if record else DEFAULT_EMBEDDING_MODEL
