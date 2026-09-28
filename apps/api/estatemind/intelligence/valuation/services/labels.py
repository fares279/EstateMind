"""User-facing wording for valuation internals: feature names, model names and
status codes. Anything not listed here is not shown to users."""
from __future__ import annotations

FEATURE_LABELS = {
    'size_m2': 'Size (m²)', 'surface_m2': 'Size (m²)', 'rooms': 'Rooms', 'bedrooms': 'Bedrooms',
    'bathrooms': 'Bathrooms', 'governorate': 'Governorate', 'city': 'Town', 'city_governorate': 'Town',
    'local_avg_price_m2': 'Local price level (per m²)', 'gov_avg_price_m2': 'Governorate price level (per m²)',
    'size_x_local_price': 'Size at the local price level', 'latitude': 'Map position', 'longitude': 'Map position',
    'property_type': 'Property type', 'transaction_type': 'Sale or rent', 'floor': 'Floor',
    'condition': 'Condition', 'year_built': 'Year built', 'sea_view': 'Sea view', 'has_pool': 'Swimming pool',
    'has_garden': 'Garden', 'has_parking': 'Parking', 'elevator': 'Elevator',
}

PROPERTY_TYPE_LABELS = {'appartement': 'Apartment', 'apartment': 'Apartment', 'maison': 'House', 'house': 'House',
                        'villa': 'House', 'terrain': 'Land', 'land': 'Land', 'global': 'All property types',
                        'commercial': 'Commercial'}

# Status and warning codes produced by the pipeline -> plain sentences.
# None = internal detail, not shown to users.
REASON_LABELS = {
    'ood:processor_unavailable': None,
    'reference_dataset_missing': None,
    'proxy_price_features_used': 'Local prices were estimated from area averages.',
    'short_description': None,
    'no_images': None,
    'insufficient_text': None,
}
_REASON_PREFIX_LABELS = {
    'ood:': 'Some details are unusual for the data the model was trained on, so the estimate is less certain.',
    'cv_analysis_error': None,
    'sentiment_analysis_error': None,
    'catboost_signal_adjustment': None,
    'cv_confidence': None,
    'cv_images_analyzed': None,
}


def feature_label(name: str) -> str:
    return FEATURE_LABELS.get(name, name.replace('_', ' ').capitalize())


def model_label(model_name: str | None, version: str | None = None, training_date=None) -> str:
    """'valuation:appartement' / 'bytype__appartement__catboost' -> 'CatBoost (Apartment model)'."""
    raw = (model_name or '').lower()
    scope = next((label for key, label in PROPERTY_TYPE_LABELS.items() if key in raw), None)
    if scope is None and version:
        scope = next((label for key, label in PROPERTY_TYPE_LABELS.items() if key in version.lower()), None)
    label = f"CatBoost ({scope} model)" if scope else 'CatBoost valuation model'
    # '<family>-artifact' rows are auto-registered by the registry sync, which stamps its
    # own run date: their real training date is unknown, so none is shown
    if training_date and not str(version or '').endswith('-artifact'):
        label += f", trained {training_date}"
    return label


def user_reasons(codes) -> list[str]:
    """Plain sentences for the codes users should see; internal codes are dropped.
    Free-text entries that already read as sentences (they contain a space and no
    code-like prefix) are kept."""
    out: list[str] = []
    for code in codes or []:
        code = str(code)
        if code in REASON_LABELS:
            text = REASON_LABELS[code]
        else:
            prefix = next((p for p in _REASON_PREFIX_LABELS if code.startswith(p)), None)
            if prefix is not None:
                text = _REASON_PREFIX_LABELS[prefix]
            elif ' ' in code.strip():
                text = code
            else:
                text = None  # an internal code nobody has worded: hide it
        if text and text not in out:
            out.append(text)
    return out
