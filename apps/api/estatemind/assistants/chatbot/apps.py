import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

# Global service instances (lazy-loaded on first use)
_intent_classifier = None
_market_retriever = None
_hallucination_guard = None
_quality_monitor = None
_reward_model = None


def get_intent_classifier():
    """Lazy-load and cache the intent classifier."""
    global _intent_classifier
    if _intent_classifier is None:
        from estatemind.assistants.chatbot.services.intent_classifier import IntentClassifier
        logger.info('Initializing IntentClassifier...')
        _intent_classifier = IntentClassifier()
    return _intent_classifier


def get_market_retriever():
    """Lazy-load and cache the market data retriever."""
    global _market_retriever
    if _market_retriever is None:
        from estatemind.assistants.chatbot.services.market_data_retriever import MarketDataRetriever
        logger.info('Initializing MarketDataRetriever...')
        _market_retriever = MarketDataRetriever()
    return _market_retriever


def get_hallucination_guard():
    """Lazy-load and cache the hallucination guard."""
    global _hallucination_guard
    if _hallucination_guard is None:
        from estatemind.assistants.chatbot.services.hallucination_guard import HallucinationGuard
        logger.info('Initializing HallucinationGuard...')
        _hallucination_guard = HallucinationGuard()
    return _hallucination_guard


def get_quality_monitor():
    """Lazy-load and cache the quality monitor."""
    global _quality_monitor
    if _quality_monitor is None:
        from estatemind.assistants.chatbot.services.response_quality_monitor import ResponseQualityMonitor
        logger.info('Initializing ResponseQualityMonitor...')
        _quality_monitor = ResponseQualityMonitor()
    return _quality_monitor


def get_reward_model():
    """Lazy-load and cache the reward model."""
    global _reward_model
    if _reward_model is None:
        from estatemind.assistants.chatbot.services.reward_model import RLHFRewardModel
        logger.info('Initializing RLHFRewardModel...')
        _reward_model = RLHFRewardModel()
    return _reward_model


class ChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estatemind.assistants.chatbot'
    label = 'chatbot'
    verbose_name = 'AI Chat Assistant'
    
    def ready(self):
        """Pre-load ML models on Django startup to avoid request timeouts."""
        logger.info('ChatbotConfig.ready() called - warming up ML models...')
        try:
            # Lazy-load models on startup (they'll be cached globally)
            get_intent_classifier()
            logger.info('✓ IntentClassifier ready')
        except Exception as e:
            logger.error(f'Failed to pre-load IntentClassifier: {e}')
        
        try:
            get_market_retriever()
            logger.info('✓ MarketDataRetriever ready')
        except Exception as e:
            logger.error(f'Failed to pre-load MarketDataRetriever: {e}')
        
        try:
            get_hallucination_guard()
            logger.info('✓ HallucinationGuard ready')
        except Exception as e:
            logger.error(f'Failed to pre-load HallucinationGuard: {e}')
        
        try:
            get_quality_monitor()
            logger.info('✓ ResponseQualityMonitor ready')
        except Exception as e:
            logger.error(f'Failed to pre-load ResponseQualityMonitor: {e}')
        
        try:
            get_reward_model()
            logger.info('✓ RLHFRewardModel ready')
        except Exception as e:
            logger.error(f'Failed to pre-load RLHFRewardModel: {e}')
        
        logger.info('ML model warm-up complete!')
