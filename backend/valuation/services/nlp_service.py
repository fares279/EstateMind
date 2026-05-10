"""
NLP heuristics for description and location analysis.
No external ML model required — pure Python / regex.
"""
import re

STOPWORDS = {
    'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'en',
    'au', 'aux', 'est', 'que', 'qui', 'par', 'sur', 'à', 'avec',
    'the', 'a', 'an', 'of', 'in', 'on', 'and', 'is', 'for', 'to',
}

POSITIVE_KW = [
    'piscine', 'pool', 'jardin', 'garden', 'vue mer', 'sea view', 'terrasse',
    'terrace', 'rénové', 'renove', 'renovated', 'neuf', 'new', 'moderne',
    'modern', 'luxe', 'luxury', 'lumineux', 'luminous', 'sécurisé', 'secure',
    'calme', 'quiet', 'ascenseur', 'elevator', 'parking', 'meublé', 'furnished',
    'équipé', 'equipped', 'climatisé', 'air conditioning',
]

NEGATIVE_KW = [
    'à rénover', 'travaux', 'dégradé', 'vétuste', 'urgente', 'urgent',
    'occasion', 'problème', 'humidité', 'fissure', 'ancien', 'vieux',
]

AMENITY_KW = {
    'pool':     ['piscine', 'pool', 'natation'],
    'garden':   ['jardin', 'garden', 'verdure', 'végétation'],
    'parking':  ['parking', 'garage', 'stationnement'],
    'sea_view': ['vue mer', 'sea view', 'mer', 'ocean', 'bord de mer'],
    'terrace':  ['terrasse', 'balcon', 'terrace', 'balcony'],
    'elevator': ['ascenseur', 'elevator', 'lift'],
}

_LOCATION_SENTIMENT = {
    'la marsa':     ('positive', 0.85),
    'carthage':     ('positive', 0.90),
    'sidi bou said':('positive', 0.88),
    'gammarth':     ('positive', 0.82),
    'les berges':   ('positive', 0.80),
    'ennasr':       ('positive', 0.75),
    'menzah':       ('positive', 0.73),
    'el menzah':    ('positive', 0.73),
    'soukra':       ('positive', 0.68),
    'ariana':       ('neutral',  0.55),
    'manouba':      ('neutral',  0.50),
    'sfax':         ('neutral',  0.55),
    'sousse':       ('positive', 0.65),
    'monastir':     ('positive', 0.62),
    'nabeul':       ('positive', 0.60),
    'hammamet':     ('positive', 0.72),
    'tunis':        ('positive', 0.65),
}


def analyze_description(description: str) -> dict:
    """Return text_analysis dict with quality, sentiment, key phrases."""
    text = (description or '').strip()
    if not text:
        return {
            'description_quality':    'None',
            'description_score':      0.0,
            'sentiment_label':        'neutral',
            'sentiment_score':        0.5,
            'sentiment_mode':         'neutral_fallback',
            'marketing_effectiveness':'Poor',
            'key_phrases':            [],
            'token_count':            0,
        }

    tokens = [w for w in re.split(r'\s+', text.lower()) if len(w) > 2 and w not in STOPWORDS]
    token_count = len(tokens)

    # Richness
    richness = min(token_count / 40.0, 1.0)

    # Amenity detection
    amenity_hits = 0
    key_phrases = []
    text_lower = text.lower()
    for amenity, keywords in AMENITY_KW.items():
        for kw in keywords:
            if kw in text_lower:
                amenity_hits += 1
                key_phrases.append(kw)
                break

    # Quality score
    quality_score = min(1.0, 0.35 + 0.35 * richness + 0.06 * amenity_hits)
    if quality_score >= 0.80:
        quality_label = 'Professional'
        marketing = 'Excellent'
    elif quality_score >= 0.60:
        quality_label = 'Good'
        marketing = 'Good'
    elif quality_score >= 0.40:
        quality_label = 'Basic'
        marketing = 'Fair'
    else:
        quality_label = 'Poor'
        marketing = 'Poor'

    # Sentiment
    pos_count = sum(1 for kw in POSITIVE_KW if kw in text_lower)
    neg_count = sum(1 for kw in NEGATIVE_KW if kw in text_lower)
    total = pos_count + neg_count or 1
    sentiment_score = max(0.1, min(0.9, 0.5 + (pos_count - neg_count) / (total * 4)))
    if sentiment_score >= 0.65:
        sentiment_label = 'positive'
    elif sentiment_score <= 0.35:
        sentiment_label = 'negative'
    else:
        sentiment_label = 'neutral'

    return {
        'description_quality':    quality_label,
        'description_score':      round(quality_score, 3),
        'sentiment_label':        sentiment_label,
        'sentiment_score':        round(sentiment_score, 3),
        'sentiment_mode':         'tfidf_heuristic',
        'marketing_effectiveness': marketing,
        'key_phrases':            list(set(key_phrases))[:6],
        'token_count':            token_count,
    }


def analyze_location(city: str, governorate: str) -> dict:
    """Return location sentiment based on city/governorate priors."""
    key = (city or '').lower().strip()
    gov = (governorate or '').lower().strip()

    for loc_key, (label, score) in _LOCATION_SENTIMENT.items():
        if loc_key in key or loc_key in gov:
            return {'label': label, 'score': score, 'location_key': loc_key}

    return {'label': 'neutral', 'score': 0.50, 'location_key': gov or 'unknown'}
