"""
Response quality monitoring: evaluates responses on 4 dimensions
(relevance, groundedness, length, attribution).
Runs asynchronously without blocking response delivery.
"""

import logging
from typing import Dict
import re

logger = logging.getLogger(__name__)


class ResponseQualityMonitor:
    """
    Automatically evaluates chatbot response quality on 4 dimensions.
    Runs asynchronously — does not block response delivery.
    Results are logged and used to identify degradation patterns.
    """
    
    # Quality thresholds
    MIN_SENTENCES = 2
    MAX_SENTENCES = 5
    RELEVANCE_THRESHOLD = 0.65
    GROUNDEDNESS_THRESHOLD = 0.80
    
    def evaluate(self, 
                 query: str,
                 response: str,
                 retrieved_context: Dict,
                 intent: str,
                 grounding_result: Dict = None) -> Dict:
        """
        Evaluates response on 4 dimensions.
        
        Returns:
        {
            'relevance': 0.88,
            'groundedness': 1.0,
            'length_appropriate': True,
            'has_source_attribution': True,
            'overall': 0.93,
            'quality_label': 'GOOD'
        }
        """
        
        scores = {}
        
        # Dimension 1: Relevance
        scores['relevance'] = self._score_relevance(query, response)
        
        # Dimension 2: Groundedness
        if grounding_result:
            scores['groundedness'] = grounding_result.get('grounding_score', 1.0)
        else:
            scores['groundedness'] = 1.0
        
        # Dimension 3: Length appropriateness
        sentence_count = len([s for s in response.split('.') if s.strip() and len(s.strip()) > 5])
        scores['length_appropriate'] = self.MIN_SENTENCES <= sentence_count <= self.MAX_SENTENCES
        scores['sentence_count'] = sentence_count
        
        # Dimension 4: Source attribution
        has_attribution = self._check_source_attribution(response)
        scores['has_source_attribution'] = has_attribution
        
        # Overall quality score
        scores['overall'] = (
            scores['relevance'] * 0.35 +
            scores['groundedness'] * 0.40 +
            (1.0 if scores['length_appropriate'] else 0.5) * 0.15 +
            (1.0 if has_attribution else 0.7) * 0.10
        )
        
        scores['quality_label'] = (
            'GOOD' if scores['overall'] >= 0.85 else
            'ACCEPTABLE' if scores['overall'] >= 0.70 else
            'POOR'
        )
        
        return scores
    
    def _score_relevance(self, query: str, response: str) -> float:
        """
        Lightweight relevance scoring using keyword overlap.
        Returns Jaccard similarity with scaling.
        """
        
        stopwords = {
            'is', 'the', 'a', 'an', 'in', 'of', 'for', 'and', 'or', 'to',
            'what', 'how', 'why', 'when', 'where', 'i', 'me', 'my', 'you',
            'your', 'it', 'its', 'be', 'are', 'was', 'were', 'have', 'has',
            'with', 'from', 'by', 'about', 'on', 'at', 'as', 'so', 'if',
            'than', 'le', 'la', 'les', 'de', 'et', 'un', 'une', 'des',
            'que', 'qui', 'est', 'sont', 'au', 'du', 'quoi', 'où'
        }
        
        # Extract content words (remove stopwords)
        query_words = set(
            w.lower().strip('.,!?;:') for w in query.split() 
            if w.lower().strip('.,!?;:') not in stopwords and len(w) > 2
        )
        response_words = set(
            w.lower().strip('.,!?;:') for w in response.split()
            if w.lower().strip('.,!?;:') not in stopwords and len(w) > 2
        )
        
        if not query_words:
            return 0.5
        
        # Jaccard overlap
        intersection = query_words & response_words
        union = query_words | response_words
        jaccard = len(intersection) / len(union) if union else 0
        
        # Penalty for very short responses (may be deflecting)
        if len(response.split()) < 10:
            jaccard *= 0.7
        
        # Penalty for very long responses (may be off-topic)
        if len(response.split()) > 150:
            jaccard *= 0.8
        
        return min(1.0, jaccard * 2.0)  # scale up since Jaccard is naturally low
    
    def _check_source_attribution(self, response: str) -> bool:
        """
        Checks if response cites its data sources.
        """
        
        attribution_patterns = [
            r'\[Source:',
            r'as of \d{4}-\d{2}-\d{2}',
            r'based on',
            r'according to',
            r'from our analysis',
            r'the data shows',
            r'recent market',
            r'according to our data'
        ]
        
        response_lower = response.lower()
        
        for pattern in attribution_patterns:
            if re.search(pattern, response_lower):
                return True
        
        return False
