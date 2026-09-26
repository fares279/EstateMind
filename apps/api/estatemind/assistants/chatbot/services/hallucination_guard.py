"""
Hallucination guard: validates that all statistics in responses
are grounded in retrieved data sources.
"""

import re
import logging
from typing import Dict, Set, List

logger = logging.getLogger(__name__)


class HallucinationGuard:
    """
    Validates that all statistics in a generated response
    trace to retrieved data sources.
    
    This is not an LLM-based checker — it is a structural rule.
    Any number in a response must appear in the retrieved context.
    """
    
    def validate_response(self, response_text: str, 
                          retrieved_context: Dict) -> Dict:
        """
        Extracts all numbers from the response and checks
        that they appear in the retrieved context.
        
        Returns:
        {
            'is_grounded': True/False,
            'ungrounded_claims': [...],
            'grounded_statistics': [...],
            'grounding_score': 0.0–1.0
        }
        """
        
        # Extract all numbers with optional % or currency suffix
        number_pattern = r'\b\d+(?:[.,]\d+)?(?:\s*(?:%|TND|DT|m²|m²|dinars?))?\b'
        numbers_in_response = re.findall(number_pattern, response_text)
        
        if not numbers_in_response:
            # No statistics claimed — fully grounded by default
            return {
                'is_grounded': True,
                'ungrounded_claims': [],
                'grounded_statistics': [],
                'grounding_score': 1.0,
                'has_claims': False
            }
        
        # Flatten all retrieved values to a searchable set
        retrieved_values = self._extract_all_values(retrieved_context)
        
        grounded = []
        ungrounded = []
        
        for number in numbers_in_response:
            clean_number = re.sub(r'[^\d.,]', '', number)
            
            if self._is_value_grounded(clean_number, retrieved_values):
                grounded.append(number)
            else:
                ungrounded.append(number)
        
        total = len(numbers_in_response)
        grounding_score = len(grounded) / total if total > 0 else 1.0
        
        return {
            'is_grounded': len(ungrounded) == 0,
            'ungrounded_claims': ungrounded,
            'grounded_statistics': grounded,
            'grounding_score': grounding_score,
            'has_claims': True
        }
    
    def _extract_all_values(self, context: Dict) -> Set:
        """
        Recursively extracts all numeric values from the context dict
        so they can be matched against response numbers.
        """
        values = set()
        
        def _recurse(obj):
            if isinstance(obj, (int, float)):
                # Add multiple representations
                values.add(str(round(obj, 2)))
                values.add(str(round(obj, 1)))
                values.add(str(int(obj)))
                values.add(f"{obj:.0f}")
            elif isinstance(obj, bool):
                # Skip boolean values
                pass
            elif isinstance(obj, dict):
                for v in obj.values():
                    _recurse(v)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _recurse(item)
        
        _recurse(context)
        return values
    
    def _is_value_grounded(self, clean_number: str, retrieved_values: Set) -> bool:
        """
        Checks if a number from the response appears in retrieved values.
        Handles minor rounding differences (1850.0 vs 1850, vs 1850.5).
        """
        
        # Direct match
        if clean_number in retrieved_values:
            return True
        
        # Try parsing as float and check with tolerance
        try:
            num = float(clean_number.replace(',', '.'))
            
            # Check for close match (within 2% or 10 units)
            for retrieved in retrieved_values:
                try:
                    retrieved_num = float(retrieved)
                    
                    # Absolute difference threshold
                    if abs(num - retrieved_num) < 10:
                        return True
                    
                    # Percentage difference threshold (2%)
                    if retrieved_num != 0:
                        pct_diff = abs(num - retrieved_num) / abs(retrieved_num)
                        if pct_diff < 0.02:
                            return True
                    
                except (ValueError, TypeError):
                    continue
            
            return False
            
        except (ValueError, TypeError):
            return False
