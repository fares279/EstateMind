"""
Rolling conversation memory with automatic summarization.
Maintains compact representation of conversation context without
exploding context window size.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Manages conversation context with rolling summarization.
    
    Structure:
        recent_turns: last 5 turns (verbatim, for immediate context)
        rolling_summary: compressed summary of everything before recent_turns
        extracted_facts: persistent facts extracted from conversation
    """
    
    MAX_RECENT_TURNS = 5
    SUMMARIZE_AFTER = 8  # summarize when buffer exceeds this
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.recent_turns: List[Dict] = []
        self.rolling_summary: str = ""
        self.extracted_facts: Dict = {}
        self.turn_count = 0
    
    def add_turn(self, user_message: str, 
                 assistant_response: str,
                 intent: str,
                 entities: Dict):
        """
        Adds a new turn to the conversation memory.
        Automatically compresses old turns when buffer exceeds threshold.
        """
        
        turn = {
            'user': user_message,
            'assistant': assistant_response,
            'intent': intent,
            'entities': entities,
            'turn_index': self.turn_count
        }
        
        self.turn_count += 1
        self.recent_turns.append(turn)
        
        # Update persistent facts from entities
        self._update_extracted_facts(entities, intent)
        
        # Summarize if buffer is getting large
        if len(self.recent_turns) > self.SUMMARIZE_AFTER:
            self._compress_oldest_turns()
    
    def _compress_oldest_turns(self):
        """
        Takes the oldest 3 turns from recent_turns and
        incorporates them into the rolling summary.
        Keeps only the most recent 5 turns in memory.
        """
        turns_to_compress = self.recent_turns[:3]
        self.recent_turns = self.recent_turns[3:]
        
        # Build compression from the turns
        compression_parts = []
        for turn in turns_to_compress:
            entities = turn.get('entities', {})
            intent = turn.get('intent', 'unknown')
            
            if entities.get('location'):
                compression_parts.append(
                    f"User inquired about {entities['location']} "
                    f"({intent.replace('_', ' ')})"
                )
            else:
                compression_parts.append(
                    f"User asked: {intent.replace('_', ' ')}"
                )
        
        new_compression = '. '.join(compression_parts)
        
        if self.rolling_summary:
            self.rolling_summary = (
                f"{self.rolling_summary}. "
                f"Later: {new_compression}"
            )
        else:
            self.rolling_summary = new_compression
        
        logger.debug(f'Compressed {len(turns_to_compress)} turns. '
                    f'Remaining recent: {len(self.recent_turns)}')
    
    def _update_extracted_facts(self, entities: Dict, intent: str):
        """
        Extracts and persists durable facts across the conversation.
        Once a user expresses interest in Sousse, that persists
        until they express interest in a different location.
        """
        
        if entities.get('location'):
            self.extracted_facts['primary_location_interest'] = entities['location']
        
        if entities.get('property_type'):
            self.extracted_facts['preferred_property_type'] = entities['property_type']
        
        if entities.get('timeframe'):
            self.extracted_facts['investment_timeframe'] = entities['timeframe']
        
        # Intent sequence tracking
        if 'intent_sequence' not in self.extracted_facts:
            self.extracted_facts['intent_sequence'] = []
        self.extracted_facts['intent_sequence'].append(intent)
        
        # Keep only last 10 intents in sequence
        self.extracted_facts['intent_sequence'] = (
            self.extracted_facts['intent_sequence'][-10:]
        )
    
    def get_context_for_response(self) -> Dict:
        """
        Returns the full context package for the response generator.
        This is passed to the response generator alongside the current user query.
        """
        return {
            'rolling_summary': self.rolling_summary,
            'recent_turns': self.recent_turns,
            'extracted_facts': self.extracted_facts,
            'current_location_interest': self.extracted_facts.get(
                'primary_location_interest'
            ),
            'conversation_length': (
                len(self.recent_turns) + 
                (len(self.rolling_summary.split('.')) if self.rolling_summary else 0)
            ),
            'turn_count': self.turn_count
        }
    
    def resolve_ambiguous_reference(self, query: str) -> Dict:
        """
        When a query contains "there", "it", "that place", etc.,
        resolves the reference using conversation context.
        
        Example:
          Session context: user has been asking about Sousse
          Query: "What about the climate there?"
          Resolved: "What about the climate in Sousse?"
        """
        
        ambiguous_references = [
            'there', 'it', 'that place', 'that area', 'that city',
            'the market', 'that property', 'the coast', 'there',
            'là-bas', 'là', 'ce coin'  # French/Arabic
        ]
        
        query_lower = query.lower()
        has_ambiguous_reference = any(
            ref in query_lower for ref in ambiguous_references
        )
        
        if has_ambiguous_reference:
            location = self.extracted_facts.get('primary_location_interest')
            if location:
                enriched = query.replace('there', f'in {location}')
                enriched = enriched.replace('There', f'In {location}')
                enriched = enriched.replace('there,', f'in {location},')
                enriched = enriched.replace('là-bas', f'dans {location}')
                enriched = enriched.replace('là', f'dans {location}')
                
                return {
                    'resolved': True,
                    'resolved_location': location,
                    'enriched_query': enriched
                }
        
        return {'resolved': False, 'resolved_location': None, 'enriched_query': query}
    
    def serialize(self) -> Dict:
        """For Redis/cache storage between requests."""
        return {
            'recent_turns': self.recent_turns,
            'rolling_summary': self.rolling_summary,
            'extracted_facts': self.extracted_facts,
            'turn_count': self.turn_count
        }
    
    @classmethod
    def deserialize(cls, session_id: str, data: Dict) -> 'ConversationMemory':
        """Reconstructs memory from serialized dict."""
        memory = cls(session_id)
        memory.recent_turns = data.get('recent_turns', [])
        memory.rolling_summary = data.get('rolling_summary', '')
        memory.extracted_facts = data.get('extracted_facts', {})
        memory.turn_count = data.get('turn_count', 0)
        return memory
