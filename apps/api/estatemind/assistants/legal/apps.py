import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)

# Service singletons, created once per process (same pattern as chatbot.apps).
_domain_classifier = None
_retriever = None
_hallucination_detector = None
_quality_monitor = None
_reward_model = None


def get_domain_classifier():
    global _domain_classifier
    if _domain_classifier is None:
        from .services.domain_classifier import LegalDomainClassifier
        _domain_classifier = LegalDomainClassifier()
    return _domain_classifier


def get_retriever():
    global _retriever
    if _retriever is None:
        from .services.retriever import LegalRetriever
        _retriever = LegalRetriever()
    return _retriever


def get_hallucination_detector():
    global _hallucination_detector
    if _hallucination_detector is None:
        from .services.hallucination_detector import HallucinationDetector
        _hallucination_detector = HallucinationDetector()
    return _hallucination_detector


def get_quality_monitor():
    global _quality_monitor
    if _quality_monitor is None:
        from .services.quality_monitor import LegalResponseQualityMonitor
        _quality_monitor = LegalResponseQualityMonitor()
    return _quality_monitor


def get_reward_model():
    global _reward_model
    if _reward_model is None:
        from .services.reward_model import LegalRewardModel
        _reward_model = LegalRewardModel()
    return _reward_model


class LegalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estatemind.assistants.legal'
    label = 'legal'
    verbose_name = 'Legal AI Assistant'

    def ready(self):
        """Load the legal models at startup so the first question does not pay for it.

        On by default, like the chatbot; set PRELOAD_LEGAL_EMBEDDING_MODEL=False
        (environment or .env) to load lazily instead.
        """
        from decouple import config

        if not config('PRELOAD_LEGAL_EMBEDDING_MODEL', default=True, cast=bool):
            return
        # On Windows, torch DLLs must be initialised from the main thread;
        # loading inside a request thread raises WinError 1114.
        import threading
        if threading.current_thread() is not threading.main_thread():
            return

        steps = (
            ('LegalDomainClassifier', get_domain_classifier),
            ('LegalRetriever', lambda: get_retriever().warm_up()),
            ('HallucinationDetector', get_hallucination_detector),
            ('LegalResponseQualityMonitor', get_quality_monitor),
            ('LegalRewardModel', get_reward_model),
        )
        for name, load in steps:
            try:
                load()
                logger.info('[Legal] %s ready', name)
            except Exception as exc:  # noqa: BLE001
                logger.warning('[Legal] Could not pre-load %s: %s', name, exc)
