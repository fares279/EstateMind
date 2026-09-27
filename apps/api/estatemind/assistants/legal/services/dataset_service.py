import json
import hashlib
import re
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

DATASET_PATH = Path(__file__).parent.parent / 'data' / 'clean_dataset_v2.json'

# URL path fragment → human-readable law name
_URL_LAW_MAP = [
    ('/codes/cs/',        'Code des Sociétés'),
    ('epargne-invest',    "Loi sur l'Épargne-Investissement"),
    ('/codes/cirppis/',   "Code de l'Impôt sur le Revenu"),
    ('/codes/rec/',       'Code du Recouvrement des Créances'),
    ('/codes/cii/',       "Code d'Incitation aux Investissements"),
    ('/codes/copc/',      'Code des Organismes de Placement Collectif'),
    ('/codes/cdet/',      "Code des Droits d'Enregistrement"),
]


def _law_name(url: str) -> str:
    url_lower = url.lower()
    for fragment, name in _URL_LAW_MAP:
        if fragment in url_lower:
            return name
    return 'Législation Tunisienne'


def _article_ref(text: str) -> str:
    m = re.search(r'(Art(?:icle)?\.?\s*\d+\s*[a-zA-Z]*(?:\s*bis)?)', text.strip(), re.IGNORECASE)
    return m.group(1).strip() if m else 'Article'


# Part of the scraped corpus went through a lossy re-encoding: é became è,
# ê/ô/î became two-character sequences, and in some articles è became ç.
# Real French only writes ç before a/o/u, so ç before anything else is a
# corrupted è. A genuine è is followed by consonant(s) and a silent final e
# (règle, première, hypothèque, règlement) or is one of a few -ès words; any
# other è is a corrupted é. Articles without a corruption signature are left
# untouched.
_MOJIBAKE_SEQUENCES = (('clàŠture', 'clôture'), ('àŠ', 'ê'), ('àī', 'ô'), ('àŪ', 'î'), ('àtat', 'État'))
_VOWELS = 'aeiouyàâäéèêëîïôöùûü'
_C = rf"[^{_VOWELS}\W\d_]"
# règle(s), mobilière(s), siège, hypothèque | règlement(s): consonant cluster
_GENUINE_E_GRAVE = re.compile(rf"è(?:qu|{_C}{{1,3}})es?\b|è{_C}{{2,3}}e(?:nt|ments?)\b", re.IGNORECASE)
_GENUINE_E_GRAVE_WORDS = {
    'après', 'auprès', 'dès', 'très', 'près', 'procès', 'accès', 'succès', 'excès', 'progrès', 'exprès',
    'achèvement', 'enlèvement', 'prélèvement', 'avènement', 'soulèvement', 'élèvement',
}
_FAKE_CEDILLA = re.compile(r'ç(?![aouAOU])')


def _is_genuine_e_grave(word: str, pos: int) -> bool:
    return word.lower() in _GENUINE_E_GRAVE_WORDS or bool(_GENUINE_E_GRAVE.match(word, pos))


def _fix_word(word: str) -> str:
    chars = list(word)
    for i, ch in enumerate(word):
        if ch == 'è' and not _is_genuine_e_grave(word, i):
            chars[i] = 'é'
    return ''.join(chars)


def _looks_corrupted(text: str) -> bool:
    if any(bad in text for bad, _ in _MOJIBAKE_SEQUENCES) or _FAKE_CEDILLA.search(text):
        return True
    return any(
        ch == 'è' and not _is_genuine_e_grave(w, i)
        for w in re.findall(r'\w+', text) for i, ch in enumerate(w)
    )


def repair_mojibake(text: str) -> str:
    text = text.replace('Ă ', 'à ')
    if not _looks_corrupted(text):
        return text
    for bad, good in _MOJIBAKE_SEQUENCES:
        text = text.replace(bad, good)
    text = _FAKE_CEDILLA.sub('è', text)
    return re.sub(r'\w+', lambda m: _fix_word(m.group(0)), text)


def _clean(text: str) -> str:
    return ' '.join(repair_mojibake(str(text)).strip().split())


def _chunk(text: str, max_words: int = 80, overlap: int = 20) -> List[str]:
    # Sized for the embedding model's input window (128 tokens for the
    # multilingual MiniLM); longer chunks are silently truncated when embedded.
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(' '.join(words[start:end]))
        if end == len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _chunk_settings() -> tuple[int, int]:
    from django.conf import settings
    cfg = getattr(settings, 'LEGAL_RAG', {})
    return cfg.get('CHUNK_WORDS', 80), cfg.get('CHUNK_OVERLAP_WORDS', 20)


def load_and_prepare() -> List[Dict[str, Any]]:
    """Load dataset and return list of chunks ready for ChromaDB indexing."""
    max_words, overlap = _chunk_settings()
    with open(DATASET_PATH, encoding='utf-8') as f:
        data = json.load(f)

    raw_articles = data.get('articles', [])
    logger.info("Loaded %d raw articles from dataset", len(raw_articles))

    chunks: List[Dict[str, Any]] = []
    for art_idx, item in enumerate(raw_articles):
        url = item.get('url', '')
        text = _clean(item.get('text', ''))
        if not text:
            continue

        article_ref = _article_ref(text)
        law_name = _law_name(url)
        keywords = ', '.join(item.get('keywords_found', []))
        source = item.get('source', 'JuriSite Tunisie')

        for chunk_idx, chunk_text in enumerate(_chunk(text, max_words, overlap)):
            # art_idx guarantees uniqueness even when multiple articles share the same URL
            chunk_id = hashlib.md5(f"{art_idx}_{url}_{chunk_idx}".encode()).hexdigest()[:16]
            chunks.append({
                'id': chunk_id,
                'text': chunk_text,
                'metadata': {
                    'chunk_id': chunk_id,
                    'article_index': art_idx,
                    'article_ref': article_ref,
                    'law_name': law_name,
                    'source': source,
                    'source_url': url,
                    'keywords': keywords,
                    'chunk_index': chunk_idx,
                },
            })

    logger.info("Prepared %d chunks from %d articles", len(chunks), len(raw_articles))
    return chunks


def load_domain_corpus(domain: str) -> List[Dict[str, Any]]:
    """Chunks for a domain's collection. The corpus is not split by domain, so
    every domain gets the full set."""
    return load_and_prepare()
