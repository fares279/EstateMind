import logging
from dataclasses import dataclass

from estatemind.assistants.legal.models import EmbeddingCollectionVersion

logger = logging.getLogger(__name__)


@dataclass
class Route:
    collection: str
    embedding_model: str
    source: str  # 'registry' | 'settings_fallback'


class ChromaRouter:
    """All ChromaDB queries MUST go through this router.
    Never hardcode a collection name in the RAG engine.

    Resolution order: the active collection registered for the domain, then
    any active collection, then the collection named in settings (used when
    the registry is empty, e.g. a fresh database with an existing index).
    """

    def _settings(self) -> dict:
        from django.conf import settings
        return getattr(settings, 'LEGAL_RAG', {})

    def route(self, domain: str) -> Route:
        record = (
            EmbeddingCollectionVersion.objects.filter(domain=domain, is_active=True).first()
            or EmbeddingCollectionVersion.objects.filter(is_active=True).first()
        )
        cfg = self._settings()
        configured_model = cfg.get('EMBEDDING_MODEL', '')
        if record:
            if configured_model and record.embedding_model != configured_model:
                logger.error(
                    "Collection '%s' was indexed with %s but EMBEDDING_MODEL is %s; "
                    "retrieval will be unreliable until the index is rebuilt.",
                    record.collection_name, record.embedding_model, configured_model,
                )
            return Route(record.collection_name, record.embedding_model, 'registry')

        name = cfg.get('CHROMA_COLLECTION', 'estate_legal')
        logger.warning("No active collection registered; using '%s' from settings.", name)
        return Route(name, configured_model, 'settings_fallback')

    # Kept for callers of the original API.
    def get_active_collection(self, domain: str) -> str:
        return self.route(domain).collection

    def get_embedding_model_for_query(self, domain: str) -> str:
        return self.route(domain).embedding_model
