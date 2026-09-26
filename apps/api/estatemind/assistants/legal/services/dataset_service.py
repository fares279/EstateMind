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


def _clean(text: str) -> str:
    return ' '.join(str(text).strip().split())


def _chunk(text: str, max_words: int = 700, overlap: int = 100) -> List[str]:
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


def load_and_prepare() -> List[Dict[str, Any]]:
    """Load dataset and return list of chunks ready for ChromaDB indexing."""
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

        for chunk_idx, chunk_text in enumerate(_chunk(text)):
            # art_idx guarantees uniqueness even when multiple articles share the same URL
            chunk_id = hashlib.md5(f"{art_idx}_{url}_{chunk_idx}".encode()).hexdigest()[:16]
            chunks.append({
                'id': chunk_id,
                'text': chunk_text,
                'metadata': {
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
