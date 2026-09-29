"""
Hallucination guard: validates that all statistics in responses
are grounded in retrieved data sources.
"""

import re
import logging
from typing import Dict, Set, List

logger = logging.getLogger(__name__)


# 394,989 / 3.5 / 3,5 / 12% / 1,850 TND ...
NUMBER = re.compile(r'\b\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:\s*(?:%|TND|DT|m²|dinars?))?|\b\d+(?:[.,]\d+)?(?:\s*(?:%|TND|DT|m²|dinars?))?')
THOUSANDS = re.compile(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?')


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
        
        numbers_in_response = []
        for m in NUMBER.finditer(response_text):
            before, after = response_text[max(0, m.start() - 2):m.start()], response_text[m.end():m.end() + 7]
            # units and scales, not statistics: '12-month outlook', 'score 39/100'
            if before.endswith('/') or re.match(r'-?\s?(month|year|day)s?\b', after):
                continue
            sign = '-' if before.endswith(('-', '−')) and not before[:1].isalnum() else ''
            numbers_in_response.append(sign + m.group(0))

        if not numbers_in_response:
            # No statistics claimed — fully grounded by default
            return {
                'is_grounded': True,
                'ungrounded_claims': [],
                'grounded_statistics': [],
                'grounding_score': 1.0,
                'has_claims': False
            }

        retrieved_values = self._extract_all_values(retrieved_context)
        grounded, ungrounded = [], []
        for number in numbers_in_response:
            (grounded if self._is_value_grounded(number, retrieved_values) else ungrounded).append(number)

        total = len(numbers_in_response)
        return {
            'is_grounded': not ungrounded,
            'ungrounded_claims': ungrounded,
            'grounded_statistics': grounded,
            'grounding_score': len(grounded) / total,
            'has_claims': True
        }

    def _extract_all_values(self, context: Dict) -> List[float]:
        """Every number in the retrieved context (booleans excluded)."""
        values: List[float] = []

        def _recurse(obj):
            if isinstance(obj, bool):
                return
            if isinstance(obj, (int, float)):
                values.append(float(obj))
            elif isinstance(obj, dict):
                for v in obj.values():
                    _recurse(v)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _recurse(item)

        _recurse(context)
        return values

    @staticmethod
    def _parse(number: str) -> tuple[float, int, bool]:
        """(value, decimals shown, is a percentage). '1,850' is 1850 (thousands
        separator); '3,5' is 3.5 (French decimal comma)."""
        negative = number.startswith('-')
        digits = re.match(r'[\d.,]+', number.lstrip('-')).group(0)
        if THOUSANDS.fullmatch(digits):
            digits = digits.replace(',', '')
        else:
            digits = digits.replace(',', '.')
        decimals = len(digits.split('.', 1)[1]) if '.' in digits else 0
        return (-1 if negative else 1) * float(digits), decimals, '%' in number

    def _is_value_grounded(self, number: str, retrieved_values: List[float]) -> bool:
        """A number is grounded when a retrieved value, rounded to the precision the
        response shows, equals it, or is within 0.5% of it. Percentages also match
        values stored as fractions (0.052 -> 5.2%).

        (This used to accept anything within 10 units of any retrieved value, so
        '5%' matched a stored 12, and it read '1,850' as 1.85.)"""
        try:
            num, decimals, is_pct = self._parse(number)
        except (AttributeError, ValueError):
            return False
        for value in retrieved_values:
            for candidate in ((value, value * 100) if is_pct else (value,)):
                if round(candidate, decimals) == num:
                    return True
                if candidate and abs(num - candidate) / abs(candidate) <= 0.005:
                    return True
        return False
