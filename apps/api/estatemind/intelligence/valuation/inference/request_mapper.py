"""Map validated valuation payloads into serving-friendly feature structures."""

from __future__ import annotations

from typing import Any
import logging

import pandas as pd

logger = logging.getLogger(__name__)


KEY_FIELDS = (
    "property_type",
    "transaction_type",
    "governorate",
    "city",
    "size_m2",
    "condition",
    "description",
)

MODEL_PROPERTY_TYPE_MAP = {
    "apartment": "appartement",
    "house": "maison",
    "commercial": "commercial",
    "land": "terrain",
}


def _get_value(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _normalize_property_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"apartment", "appartement", "flat"}:
        return "apartment"
    if text in {"house", "maison", "villa"}:
        return "house"
    if text in {"commercial", "commerce", "shop"}:
        return "commercial"
    if text in {"land", "terrain", "lot"}:
        return "land"
    return text or "apartment"


def _fetch_climate_score(delegation: str, lat: float = None, lon: float = None) -> dict:
    """
    Fetch climate risk score for a property.
    
    Priority order:
    1. Kriging point score (if coordinates provided)
    2. Delegation composite score
    3. National average fallback (0.35, MODERATE)
    
    Returns dict with 'score', 'risk_label', 'method', 'freshness'.
    Never raises — uses fallback on any error.
    """
    
    # Priority 1: Point-level kriging if coordinates available
    if lat is not None and lon is not None:
        try:
            from estatemind.intelligence.climate.services import KrigingClimateService
            kriging = KrigingClimateService.get_instance()
            result = kriging.get_point_risk(lat, lon)
            if result.get('method') != 'national_average_fallback':
                return result
        except Exception as e:
            logger.warning(f'Kriging service unavailable: {e}')
    
    # Priority 2: Delegation-level composite score
    if delegation:
        try:
            from estatemind.market.core.models import DelegationClimateScore, Delegation
            d = Delegation.objects.filter(
                name__icontains=delegation
            ).first()
            
            if d:
                score = DelegationClimateScore.objects.get(delegation=d)
                
                # Check freshness — warn if stale
                if score.freshness_status() in ('STALE', 'CRITICAL'):
                    logger.warning(
                        f'Using stale climate score for {delegation}: '
                        f'{score.freshness_status()}, '
                        f'computed {score.computed_at}'
                    )
                
                return {
                    'score': score.composite_score,
                    'risk_label': score.risk_label,
                    'method': 'delegation_composite_score',
                    'freshness': score.freshness_status(),
                    'computed_at': score.computed_at.isoformat()
                }
        except DelegationClimateScore.DoesNotExist:
            logger.info(f'No climate score found for delegation: {delegation}')
        except Exception as e:
            logger.warning(f'Climate score lookup failed for {delegation}: {e}')
    
    # Priority 3: National average fallback
    logger.info(f'Using national average climate fallback for {delegation}')
    return {
        'score': 0.35,
        'risk_label': 'MODERATE',
        'method': 'national_average_fallback'
    }


def map_request(payload: Any) -> dict[str, Any]:
    property_type = _normalize_property_type(_get_value(payload, "property_type", "apartment"))
    bedrooms = _get_value(payload, "bedrooms", None)
    bedrooms = 0 if bedrooms in (None, "") else int(bedrooms)
    bathrooms = _get_value(payload, "bathrooms", None)
    bathrooms = 0 if bathrooms in (None, "") else int(bathrooms)
    size_m2 = float(_get_value(payload, "size_m2", 0) or 0)
    delegation = str(_get_value(payload, "delegation", "") or "").strip()
    city = str(_get_value(payload, "city", "") or "").strip() or delegation

    image_count = _get_value(payload, "image_count", None)
    if image_count is None:
        image_count = _get_value(payload, "uploaded_images_count", 0)
    
    # Fetch climate score
    lat = _get_value(payload, "latitude", None)
    lon = _get_value(payload, "longitude", None)
    climate_result = _fetch_climate_score(delegation, lat, lon)

    # Fetch delegation market average (TND/m²)
    market_avg_tnd_m2 = 2000  # National fallback
    try:
        from estatemind.market.core.models import Delegation
        delegation_obj = Delegation.objects.filter(name__icontains=delegation).first()
        if delegation_obj and delegation_obj.apt_avg_tnd:
            market_avg_tnd_m2 = delegation_obj.apt_avg_tnd
    except Exception as e:
        logger.warning(f"Failed to fetch delegation market average: {e}")

    mapped = {
        "property_type": property_type,
        "model_property_type": MODEL_PROPERTY_TYPE_MAP.get(property_type, property_type),
        "transaction_type": str(_get_value(payload, "transaction_type", "sale") or "sale").strip().lower(),
        "governorate": str(_get_value(payload, "governorate", "") or "").strip(),
        "delegation": delegation,
        "city": city,
        "neighborhood": str(_get_value(payload, "neighborhood", "") or "").strip(),
        "surface_m2": size_m2,
        "size_m2": size_m2,
        "rooms": bedrooms + (0 if property_type == "land" else 1),
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "condition": str(_get_value(payload, "condition", "") or "").strip().lower().replace("_", " "),
        "has_pool": bool(_get_value(payload, "has_pool", False)),
        "has_garden": bool(_get_value(payload, "has_garden", False)),
        "has_parking": bool(_get_value(payload, "has_parking", False)),
        "sea_view": bool(_get_value(payload, "sea_view", False)),
        "elevator": bool(_get_value(payload, "elevator", False)),
        "description": str(_get_value(payload, "description", "") or "").strip(),
        "image_count": int(image_count or 0),
        "latitude": lat,
        "longitude": lon,
        "climate_risk_score": climate_result['score'],
        "climate_risk_label_encoded": {
            'VERY_LOW': 0, 'LOW': 1, 'MODERATE': 2,
            'MODERATE_HIGH': 3, 'HIGH': 4, 'VERY_HIGH': 5
        }.get(climate_result.get('risk_label', 'MODERATE'), 2),
        "_climate_source": climate_result['method'],  # Prefixed with _ for audit, stripped before model
        "_market_avg_tnd_m2": market_avg_tnd_m2,  # Audit metadata, stripped before model
    }
    present = sum(1 for field in KEY_FIELDS if str(mapped.get(field, "")).strip())
    mapped["input_completeness"] = round(present / len(KEY_FIELDS), 3)
    return mapped


def to_feature_frame(mapped: dict[str, Any]) -> pd.DataFrame:
    # Strip audit metadata fields (prefixed with _) before passing to model
    climate_source = mapped.pop("_climate_source", "unknown")
    
    return pd.DataFrame(
        [
            {
                "property_type": mapped["property_type"],
                "transaction_type": mapped.get("transaction_type", "sale"),
                "governorate": mapped["governorate"],
                "city": mapped["city"],
                "delegation": mapped.get("delegation", ""),
                "surface_m2": mapped["surface_m2"],
                "rooms": mapped.get("rooms", 0),
                "bedrooms": mapped["bedrooms"],
                "bathrooms": mapped["bathrooms"],
                "condition": mapped["condition"],
                "has_pool": mapped["has_pool"],
                "has_garden": mapped["has_garden"],
                "has_parking": mapped["has_parking"],
                "sea_view": mapped["sea_view"],
                "elevator": mapped["elevator"],
                "description_length": len(mapped["description"]),
                "image_count": mapped["image_count"],
                "climate_risk_score": mapped.get("climate_risk_score", 0.35),
                "climate_risk_label_encoded": mapped.get("climate_risk_label_encoded", 2),
            }
        ]
    )
