"""
Intent classification service using sentence-transformers.
Handles 8 core intents with embedding-based similarity + fallback keyword matching.
Target accuracy: ≥92%
"""

import logging
import re
from typing import Optional, Dict, List
from sentence_transformers import SentenceTransformer, util
import torch
import numpy as np

logger = logging.getLogger(__name__)


GREETING_PHRASES = (
    'hello', 'hi', 'hey', 'bonjour', 'salut', 'salam', 'marhaba', 'good morning',
    'good afternoon', 'good evening', 'my name is', 'thanks', 'thank you', 'merci', 'shukran',
)
# Words that make a message a real question even when it opens with a greeting.
_DOMAIN_WORDS = (
    'price', 'prix', 'cost', 'rent', 'loyer', 'buy', 'sell', 'invest', 'yield', 'market', 'value',
    'worth', 'forecast', 'predict', 'future', 'grow', 'rise', 'fall', 'tax', 'law', 'loi', 'legal',
    'flood', 'climate', 'risk', 'portfolio', 'apartment', 'appartement', 'house', 'villa', 'maison',
    'land', 'terrain', 'delegation', 'governorate',
)


def is_greeting(message: str) -> bool:
    """A greeting, thanks or introduction with no real question in it.

    Words are matched whole: the old substring test read 'which' and 'high' as
    'hi', so "Which delegations will grow fastest?" was answered as a greeting."""
    text = ' ' + re.sub(r'[^\w\s]', ' ', message.lower()) + ' '
    if not any(f' {phrase} ' in text for phrase in GREETING_PHRASES):
        return False
    return not any(re.search(rf'\b{word}', text) for word in _DOMAIN_WORDS)


class IntentClassifier:
    """
    ML-based intent classifier using sentence-transformers embeddings.
    Supports zero-shot classification initially, transitions to fine-tuned
    model as labeled feedback accumulates.
    """
    
    # Eight core intents
    INTENTS = [
        'market_inquiry',
        'valuation_request',
        'investment_advice',
        'legal_question',
        'forecast_inquiry',
        'portfolio_question',
        'climate_question',
        'general_greeting'
    ]
    
    # Intent descriptions for zero-shot matching
    INTENT_DESCRIPTIONS = {
        'market_inquiry': 
            'asking about current real estate market conditions, prices, or trends in a location',
        'valuation_request': 
            'requesting a property valuation or asking how much a property is worth',
        'investment_advice': 
            'seeking investment guidance, rental yields, or buy/sell recommendations',
        'legal_question': 
            'asking about property laws, taxes, registration, or regulations',
        'forecast_inquiry': 
            'asking about future price predictions or market forecasts',
        'portfolio_question': 
            'asking about portfolio performance, diversification, or owned properties',
        'climate_question': 
            'asking about flood risk, climate change, or environmental risks for properties',
        'general_greeting': 
            'general greeting, small talk, or off-topic question',
    }
    
    def __init__(self):
        try:
            # Load multilingual sentence-transformer model (embedding-based)
            # This handles Arabic, French, English seamlessly
            from estatemind.assistants.shared_models import INTENT_MODEL, get_sentence_model
            self.model = get_sentence_model(INTENT_MODEL)
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            # Each intent is the centroid of its description and the hand-labelled
            # examples in data/chatbot_intents.json. Chosen by leave-one-out accuracy
            # on the examples (centroid 0.78, description only 0.76, nearest example
            # 0.59); the held-out evaluation set was not used to choose.
            from .intent_data import examples
            labelled = examples()
            self.intent_embeddings = {}
            for intent, description in self.INTENT_DESCRIPTIONS.items():
                texts = [description, *labelled.get(intent, [])]
                vectors = self.model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
                self.intent_embeddings[intent] = vectors.mean(dim=0)
            
            self.is_loaded = True
            logger.info(f'Intent classifier loaded on device: {self.device}')
        except Exception as e:
            logger.error(f'Failed to load intent classifier: {e}')
            self.is_loaded = False
            self.model = None
            self.intent_embeddings = {}
    
    def classify(self, user_message: str, 
                 session_context: Optional[Dict] = None) -> Dict:
        """
        Classifies user message into one of 8 intents.
        Uses session context to resolve ambiguous queries.
        
        Args:
            user_message: The user's query
            session_context: Previous conversation context with extracted_facts
        
        Returns:
            {
                'intent': str,
                'confidence': float,
                'entities': dict,
                'is_ambiguous': bool,
                'secondary_intent': str,
                'secondary_confidence': float,
                'method': 'embedding_similarity'
            }
        """
        
        if not self.is_loaded:
            logger.warning('Intent classifier not loaded, returning fallback')
            return self._fallback_classify(user_message)
        
        try:
            # Short-circuit obvious greetings and introductions so they do not
            # get misrouted into the market/investment branches.
            if is_greeting(user_message):
                return {
                    'intent': 'general_greeting',
                    'confidence': 0.98,
                    'entities': {},
                    'is_ambiguous': False,
                    'secondary_intent': 'market_inquiry',
                    'secondary_confidence': 0.01,
                    'method': 'rule_based_greeting_override',
                }

            # Encode the user message
            query_embedding = self.model.encode(user_message, convert_to_tensor=True)
            
            # Compute cosine similarity with each intent embedding
            intent_scores = {}
            for intent, intent_embedding in self.intent_embeddings.items():
                # Compute cosine similarity
                similarity = util.pytorch_cos_sim(query_embedding, intent_embedding).item()
                # Normalize to [0, 1] range (similarity is typically -1 to 1, but usually 0 to 1)
                normalized_score = (similarity + 1.0) / 2.0  # Map [-1, 1] to [0, 1]
                intent_scores[intent] = max(0.0, min(1.0, normalized_score))
            
            # Sort by score descending
            sorted_intents = sorted(
                intent_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            primary_intent, primary_score = sorted_intents[0]
            secondary_intent, secondary_score = sorted_intents[1]
            
            # Check if ambiguous (top 2 scores close together)
            is_ambiguous = (primary_score - secondary_score) < 0.15
            
            # Context resolution for ambiguous cases
            if is_ambiguous and session_context:
                resolved = self._resolve_with_context(
                    user_message, sorted_intents, session_context
                )
                primary_intent = resolved
            
            # Extract entities (location, property type, timeframe)
            entities = self._extract_entities(user_message)
            
            return {
                'intent': primary_intent,
                'confidence': primary_score,
                'entities': entities,
                'is_ambiguous': is_ambiguous,
                'secondary_intent': secondary_intent,
                'secondary_confidence': secondary_score,
                'method': 'embedding_similarity'
            }
            
        except Exception as e:
            logger.error(f'Intent classification error: {e}')
            return self._fallback_classify(user_message)
    
    
    def _resolve_with_context(self, message: str, sorted_intents: List, 
                              session_context: Dict) -> str:
        """
        When ambiguous, use session context to disambiguate.
        E.g., if user has been asking about Sousse, prefer 
        location-specific intents over general ones.
        """
        extracted = session_context.get('extracted_facts', {})
        primary_location = extracted.get('primary_location_interest')
        
        if primary_location:
            # Boost location-dependent intents
            for intent, score in sorted_intents:
                if intent in ['market_inquiry', 'investment_advice', 'climate_question']:
                    return intent
        
        return sorted_intents[0][0]
    
    def _extract_entities(self, message: str) -> Dict:
        """
        Extracts location, property type, timeframe from message.
        Uses rule-based patterns for Tunisia-specific entities.
        """
        from estatemind.market.core.models import Delegation, Region
        
        entities = {}
        message_lower = message.lower()
        
        entities.update(self._extract_location(message))

        # Property type
        property_patterns = {
            'apartment': ['apartment', 'appartement', 'flat', 'studio', 'appart'],
            'villa': ['villa', 'house', 'maison', 'dar'],
            'land': ['land', 'terrain', 'plot', 'lot'],
            'commercial': ['commercial', 'bureau', 'office', 'shop', 'magasin']
        }
        for ptype, patterns in property_patterns.items():
            if any(p in message_lower for p in patterns):
                entities['property_type'] = ptype
                break
        
        # Timeframe
        if any(w in message_lower for w in ['now', 'today', 'current', 'maintenant']):
            entities['timeframe'] = 'current'
        elif any(w in message_lower for w in ['next year', 'l\'année prochaine', '12 months', 'année']):
            entities['timeframe'] = '12_months'
        elif any(w in message_lower for w in ['long term', 'long-term', '5 years', '10 years']):
            entities['timeframe'] = 'long_term'
        
        return entities
    
    @staticmethod
    def _extract_location(message: str) -> Dict:
        """The place named in the message: the longest delegation name first, then a
        governorate. Whole words, ignoring case and accents ('Tunisia' is not Tunis;
        'BENI KHIAR' is Beni Khiar). Names come from the database, and from the
        delegations reference file for places the database doesn't have yet."""
        from estatemind.intelligence.valuation.inference.location import _reference, plain
        from estatemind.market.core.models import Delegation, Region

        text = f' {plain(message)} '
        delegations, governorates = {}, {}
        try:
            delegations = {plain(n): n for n in Delegation.objects.values_list('name', flat=True)}
            governorates = {plain(g): g for g in Region.objects.values_list('governorate', flat=True)}
        except Exception as e:
            logger.warning(f'Location lookup error: {e}')
        try:
            ref_governorates, ref_delegations = _reference()
            for key in ref_delegations:
                delegations.setdefault(key, key.title())
            for key, canonical in ref_governorates.items():
                governorates.setdefault(key, governorates.get(canonical, canonical.title()))
        except Exception as e:
            logger.warning(f'Location reference unavailable: {e}')

        for table, kind in ((delegations, 'delegation'), (governorates, 'governorate')):
            found = [key for key in table if key and f' {key} ' in text]
            if found:
                key = max(found, key=len)
                # a delegation named like its governorate (e.g. 'Sfax') is answered at governorate level
                if kind == 'delegation' and key in governorates:
                    return {'location': governorates[key], 'location_type': 'governorate'}
                return {'location': table[key], 'location_type': kind}
        return {}

    def _fallback_classify(self, message: str) -> Dict:
        """
        Fallback when ML model not available.
        Uses simple keyword matching with lower confidence scores.
        """
        message_lower = message.lower()
        
        keyword_map = {
            'market_inquiry': ['market', 'price', 'trend', 'how much', 'coût'],
            'investment_advice': ['invest', 'buy', 'yield', 'rent', 'opportunity'],
            'valuation_request': ['valuation', 'worth', 'value', 'estimate'],
            'legal_question': ['tax', 'law', 'regulation', 'fee', 'registration'],
            'forecast_inquiry': ['forecast', 'predict', 'future', 'expect', 'grow', 'fastest'],
            'portfolio_question': ['portfolio', 'diversif', 'performance'],
            'climate_question': ['climate', 'flood', 'risk', 'environment'],
            'general_greeting': ['hello', 'hi', 'hey', 'thanks']
        }
        if is_greeting(message):
            entities = self._extract_entities(message)
            return {'intent': 'general_greeting', 'confidence': 0.9, 'entities': entities,
                    'is_ambiguous': False, 'secondary_intent': 'market_inquiry',
                    'secondary_confidence': 0.1, 'method': 'fallback_keyword_matching'}
        keyword_map.pop('general_greeting')
        
        scores = {}
        for intent, keywords in keyword_map.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            scores[intent] = score / len(keywords)
        
        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_intents[0][0]
        secondary = sorted_intents[1][0]
        
        entities = self._extract_entities(message)
        
        return {
            'intent': primary,
            'confidence': max(0.5, min(1.0, sorted_intents[0][1])),
            'entities': entities,
            'is_ambiguous': True,
            'secondary_intent': secondary,
            'secondary_confidence': max(0.3, sorted_intents[1][1]),
            'method': 'fallback_keyword_matching'
        }
