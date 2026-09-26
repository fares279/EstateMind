"""
Intent classification service using sentence-transformers.
Handles 8 core intents with embedding-based similarity + fallback keyword matching.
Target accuracy: ≥92%
"""

import logging
from typing import Optional, Dict, List
from sentence_transformers import SentenceTransformer, util
import torch
import numpy as np

logger = logging.getLogger(__name__)


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
            self.model = SentenceTransformer(
                'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
                device='cuda' if torch.cuda.is_available() else 'cpu'
            )
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            # Pre-compute embeddings for intent descriptions
            self.intent_embeddings = {}
            for intent, description in self.INTENT_DESCRIPTIONS.items():
                embedding = self.model.encode(description, convert_to_tensor=True)
                self.intent_embeddings[intent] = embedding
            
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
            message_lower = user_message.lower().strip()

            # Short-circuit obvious greetings and introductions so they do not
            # get misrouted into the market/investment branches.
            greeting_markers = [
                'hello', 'hi', 'hey', 'bonjour', 'salut', 'salam', 'marhaba',
                'good morning', 'good afternoon', 'good evening', 'my name is',
                'thanks', 'thank you', 'shukran',
            ]
            if any(marker in message_lower for marker in greeting_markers):
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
        
        # Location extraction
        try:
            all_delegations = list(
                Delegation.objects.values_list('name', flat=True)
            )
            for delegation in all_delegations:
                if delegation.lower() in message_lower:
                    entities['location'] = delegation
                    entities['location_type'] = 'delegation'
                    break
        except Exception as e:
            logger.warning(f'Delegation lookup error: {e}')

        if 'location' not in entities:
            try:
                all_governorates = list(
                    Region.objects.values_list('governorate', flat=True)
                )
                for governorate in all_governorates:
                    if governorate.lower() in message_lower:
                        entities['location'] = governorate
                        entities['location_type'] = 'governorate'
                        break
            except Exception as e:
                logger.warning(f'Governorate lookup error: {e}')
        
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
            'forecast_inquiry': ['forecast', 'predict', 'future', 'expect'],
            'portfolio_question': ['portfolio', 'diversif', 'performance'],
            'climate_question': ['climate', 'flood', 'risk', 'environment'],
            'general_greeting': ['hello', 'hi', 'hey', 'thanks']
        }
        
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
