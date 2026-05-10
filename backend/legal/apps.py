from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class LegalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'legal'
    verbose_name = 'Legal AI Assistant'

    def ready(self):
        # Pre-load sentence_transformers / torch in the main thread.
        # On Windows, torch DLLs must be initialized from the main thread;
        # lazy loading inside a request-handler thread raises WinError 1114.
        import threading
        if threading.current_thread() is not threading.main_thread():
            return
        try:
            from .services import embedding_service
            embedding_service._get_model()
            logger.info("[Legal] Embedding model pre-loaded in main thread.")
        except Exception as exc:
            logger.warning("[Legal] Could not pre-load embedding model: %s", exc)
