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


def _chunk_bounds(n_words: int, max_words: int, overlap: int) -> List[tuple]:
    """(start, end) word indices of each chunk."""
    if n_words <= max_words:
        return [(0, n_words)]
    bounds = []
    start = 0
    while start < n_words:
        end = min(start + max_words, n_words)
        bounds.append((start, end))
        if end == n_words:
            break
        start = max(end - overlap, start + 1)
    return bounds


def _chunk(text: str, max_words: int = 80, overlap: int = 20) -> List[str]:
    # Sized for the embedding model's input window (128 tokens for the
    # multilingual MiniLM); longer chunks are silently truncated when embedded.
    words = text.split()
    if len(words) <= max_words:
        return [text]
    return [' '.join(words[a:b]) for a, b in _chunk_bounds(len(words), max_words, overlap)]


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

    official = load_official_texts(max_words, overlap)
    chunks.extend(official)
    logger.info("Prepared %d chunks from %d articles and %d from official texts",
                len(chunks) - len(official), len(raw_articles), len(official))
    return chunks


OFFICIAL_DIR = Path(__file__).parent.parent / 'data' / 'official'
_ARABIC_LETTER = re.compile(r'[؀-ۿ]')
_GLYPH_NAMES = re.compile(r'(?:isolated|initial|medial|final)')


def _official_text(pdf_path: Path) -> str | None:
    """Text of an official PDF, or None when it does not extract as readable text.
    Arabic PDFs extract in display form (presentation glyphs, words right to left):
    NFKC turns the glyphs into letters and each line's word order is reversed."""
    import unicodedata
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning('pypdf is not installed; official texts skipped')
        return None
    raw = '\n'.join((page.extract_text() or '') for page in PdfReader(str(pdf_path)).pages)
    if len(_GLYPH_NAMES.findall(raw)) > 20:  # glyph names instead of text: unusable without OCR
        return None
    lines = []
    # NFKC maps presentation glyphs to letters; tatweel (U+0640) only stretches words
    for line in unicodedata.normalize('NFKC', raw).replace('ـ', '').splitlines():
        words = line.split()
        if not words:
            continue
        lines.append(' '.join(reversed(words)) if _ARABIC_LETTER.search(line) else ' '.join(words))
    text = ' '.join(lines)
    return text if len(text.split()) >= 50 else None


def _span(text: str, span: dict | None) -> str | None:
    """The part of `text` between the manifest's span markers (start included, end
    excluded), so only the verified part of a document is indexed. None if a marker
    is missing: better to skip the text than to index the wrong part."""
    if not span:
        return text
    start = text.find(span['start']) if span.get('start') else 0
    end = text.find(span['end'], max(start, 0)) if span.get('end') else len(text)
    if start < 0 or end < 0:
        return None
    return text[start:end]


def load_official_texts(max_words: int, overlap: int) -> List[Dict[str, Any]]:
    """Chunks from official texts (data/official/*.pdf, described in manifest.json:
    title, source URL, publisher, hash, and for codes a `span` and `cite_articles`)."""
    manifest_path = OFFICIAL_DIR / 'manifest.json'
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    chunks: List[Dict[str, Any]] = []
    for stem, info in manifest.items():
        pdf = OFFICIAL_DIR / f'{stem}.pdf'
        text = _official_text(pdf) if pdf.exists() else None
        text = _span(text, info.get('span')) if text else None
        if not text:
            logger.info('Official text %s not readable or span not found; skipped', stem)
            continue
        words = text.split()
        # word index of each "Article N" heading, for codes
        headings = [(i, words[i + 1] + (f' {words[i + 2]}' if i + 2 < len(words) and words[i + 2] in ('bis', 'ter', 'quater') else ''))
                    for i in range(len(words) - 1)
                    if words[i] == 'Article' and words[i + 1].isdigit()] if info.get('cite_articles') else []
        for chunk_idx, (a, b) in enumerate(_chunk_bounds(len(words), max_words, overlap)):
            chunk_text = ' '.join(words[a:b])
            ref = info['title']
            if headings:
                # the article the passage starts in, through the last one that begins in it
                before = [n for i, n in headings if i <= a]
                inside = [n for i, n in headings if a < i < b]
                covered = before[-1:] + inside
                if covered:
                    ref = (f"{info['title']}, art. {covered[0]}" if covered[0] == covered[-1]
                           else f"{info['title']}, art. {covered[0]} à {covered[-1]}")
            chunk_id = hashlib.md5(f"official_{stem}_{chunk_idx}".encode()).hexdigest()[:16]
            chunks.append({'id': chunk_id, 'text': chunk_text, 'metadata': {
                'chunk_id': chunk_id, 'article_index': -1, 'article_ref': ref,
                'law_name': info['title'], 'source': info.get('publisher', 'Official text'),
                'source_url': info['source_url'], 'keywords': '', 'chunk_index': chunk_idx,
            }})
    return chunks


def load_domain_corpus(domain: str) -> List[Dict[str, Any]]:
    """Chunks for a domain's collection. The corpus is not split by domain, so
    every domain gets the full set."""
    return load_and_prepare()
