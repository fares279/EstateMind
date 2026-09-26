"""
Market service for simulation module.
Provides market snapshot data for delegations.
"""

from datetime import date
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def get_market_snapshot_for_delegation(delegation_name: str) -> Optional[Dict]:
    """
    Returns market snapshot for a given delegation.
    
    Returns:
        {
            'median_price_per_sqm': float,
            'trend_yoy_percent': float,
            'active_listings': int,
            'as_of_date': str (ISO format),
            'quality': str ('fresh', 'acceptable', 'stale')
        }
    """
    
    # Mock market data by delegation (multiple name variations for matching)
    market_data = {
        'sousse': {
            'median_price_per_sqm': 1850,
            'trend_yoy_percent': 8.5,
            'active_listings': 245,
            'quality': 'fresh'
        },
        'tunis': {
            'median_price_per_sqm': 2450,
            'trend_yoy_percent': 5.2,
            'active_listings': 412,
            'quality': 'fresh'
        },
        'sfax': {
            'median_price_per_sqm': 1200,
            'trend_yoy_percent': 3.1,
            'active_listings': 178,
            'quality': 'acceptable'
        },
        'hammamet': {
            'median_price_per_sqm': 2800,
            'trend_yoy_percent': 12.3,
            'active_listings': 189,
            'quality': 'fresh'
        },
        'monastir': {
            'median_price_per_sqm': 1650,
            'trend_yoy_percent': 6.7,
            'active_listings': 142,
            'quality': 'fresh'
        },
        'kairouan': {
            'median_price_per_sqm': 950,
            'trend_yoy_percent': 1.2,
            'active_listings': 87,
            'quality': 'acceptable'
        },
    }
    
    # Normalize delegation name for matching
    normalized_name = delegation_name.lower().strip()
    
    # Try exact match first, then partial match
    if normalized_name in market_data:
        key = normalized_name
    else:
        # Try to match using partial strings
        matched_key = None
        for key_option in market_data.keys():
            if key_option in normalized_name or normalized_name in key_option:
                matched_key = key_option
                break
        
        if not matched_key:
            return None
        key = matched_key
    
    data = market_data[key]
    return {
        'median_price_per_sqm': data['median_price_per_sqm'],
        'trend_yoy_percent': data['trend_yoy_percent'],
        'active_listings': data['active_listings'],
        'as_of_date': date.today().isoformat(),
        'quality': data['quality'],
        'source_tag': 'market_simulation_v1',
        'data_type': 'market_snapshot'
    }


def get_forecast_for_delegation(delegation_name: str, 
                               property_type: str = 'apartment',
                               months_ahead: int = 12) -> Optional[Dict]:
    """
    Returns price forecast for a delegation.
    
    Returns:
        {
            'price_change_percent': float,
            'confidence_level': str ('high', 'medium', 'low'),
            'months_ahead': int,
            'as_of_date': str,
            'factors': [...]
        }
    """
    
    forecast_data = {
        'Sousse': {'price_change': 8.5, 'confidence': 'high'},
        'Tunis': {'price_change': 5.2, 'confidence': 'high'},
        'Sfax': {'price_change': 3.1, 'confidence': 'medium'},
        'Hammamet': {'price_change': 12.3, 'confidence': 'high'},
        'Monastir': {'price_change': 6.7, 'confidence': 'medium'},
        'Kairouan': {'price_change': 1.2, 'confidence': 'low'},
    }
    
    for key, data in forecast_data.items():
        if key.lower() == delegation_name.lower():
            return {
                'price_change_percent': data['price_change'],
                'confidence_level': data['confidence'],
                'months_ahead': months_ahead,
                'property_type': property_type,
                'as_of_date': date.today().isoformat(),
                'factors': [
                    'tourist_demand',
                    'infrastructure_development',
                    'rental_yield',
                    'market_sentiment'
                ],
                'source_tag': 'market_forecast_v1',
                'data_type': 'forecast'
            }
    
    return None
