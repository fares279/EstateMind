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

_WORD_RE = re.compile(r"[^\W\d_]+")
_LATIN_VOWELS = set("aeiouyàâäéèêëîïôöùûü")


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ''))


def _plausible(word: str) -> bool:
    if not 2 <= len(word) <= 20 or re.search(r"(.)\1\1", word):
        return False
    latin = all(ch.isascii() or ch in _LATIN_VOWELS for ch in word)
    return not latin or any(ch in _LATIN_VOWELS for ch in word)


def is_readable(text: str, min_words: int = 3, min_share: float = 0.6) -> bool:
    """Enough real-looking words to analyse: at least `min_words` plausible words
    (no letter tripled, a vowel if Latin script, 2-20 letters) making up at least
    `min_share` of the words. Arabic script counts as plausible."""
    words = [w.lower() for w in _WORD_RE.findall(text or '')]
    good = [w for w in words if _plausible(w)]
    return len(good) >= min_words and len(good) >= min_share * len(words)


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
