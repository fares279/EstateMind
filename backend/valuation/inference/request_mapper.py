"""Map validated valuation payloads into serving-friendly feature structures."""

from __future__ import annotations

from typing import Any

import pandas as pd


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
        "latitude": _get_value(payload, "latitude", None),
        "longitude": _get_value(payload, "longitude", None),
    }
    present = sum(1 for field in KEY_FIELDS if str(mapped.get(field, "")).strip())
    mapped["input_completeness"] = round(present / len(KEY_FIELDS), 3)
    return mapped


def to_feature_frame(mapped: dict[str, Any]) -> pd.DataFrame:
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
            }
        ]
    )
