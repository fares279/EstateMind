from django.apps import AppConfig
import logging
import os

logger = logging.getLogger(__name__)


class LegalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'legal'
    verbose_name = 'Legal AI Assistant'

    def ready(self):
        # Loading SentenceTransformer at process start is too expensive for
        # the Render free tier. Keep it opt-in so the web worker can bind a port
        # quickly and only preload when explicitly requested.
        if os.environ.get('LEGAL_PRELOAD_MODEL', '').lower() not in {'1', 'true', 'yes'}:
            return

        import threading
        if threading.current_thread() is not threading.main_thread():
            return
        try:
            from .services import embedding_service
            embedding_service._get_model()
            logger.info("[Legal] Embedding model pre-loaded in main thread.")
        except Exception as exc:
            logger.warning("[Legal] Could not pre-load embedding model: %s", exc)
