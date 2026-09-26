"""
Base classes, shared utilities, and normalization logic for all scrapers.

RequestManager   — HTTP session with UA rotation, proxy support, exponential backoff
BaseScraper      — Abstract base every site scraper inherits from
normalize_tunisian_data — Canonical normalizer: Arabic→French, price/surface parsing,
                          property-type and transaction-type inference
build_external_id — Deterministic SHA-1 deduplication key
"""

import hashlib
import logging
import random
import re
import time
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/17.4 Safari/605.1.15',
]

ARABIC_TO_FRENCH_GOVERNORATES: dict[str, str] = {
    'تونس': 'Tunis', 'أريانة': 'Ariana', 'بن عروس': 'Ben Arous',
    'منوبة': 'Manouba', 'نابل': 'Nabeul', 'زغوان': 'Zaghouan',
    'بنزرت': 'Bizerte', 'باجة': 'Beja', 'جندوبة': 'Jendouba',
    'الكاف': 'Kef', 'سليانة': 'Siliana', 'سوسة': 'Sousse',
    'المنستير': 'Monastir', 'المهدية': 'Mahdia', 'صفاقس': 'Sfax',
    'القيروان': 'Kairouan', 'القصرين': 'Kasserine', 'سيدي بوزيد': 'Sidi Bouzid',
    'قابس': 'Gabes', 'مدنين': 'Medenine', 'تطاوين': 'Tataouine',
    'قفصة': 'Gafsa', 'توزر': 'Tozeur', 'قبلي': 'Kebili',
}

# Maps raw/mixed-case text fragments → EstateMind canonical property_type codes.
# Platform standard: Apartment | House | Commercial | Land  (4 types, no others).
PROPERTY_TYPE_MAP: dict[str, str] = {
    'appartement': 'apartment', 'appart': 'apartment',
    'apartment':   'apartment', 'studio': 'apartment', 'flat': 'apartment',
    'villa':       'house',     # villa → House
    'maison':      'house',     'house':    'house',
    'duplex':      'house',     'triplex':  'house',   'riad': 'house',
    'terrain':     'land',      'land':     'land',
    'lot':         'land',      'parcelle': 'land',
    'commercial':  'commercial', 'local commercial': 'commercial',
    'bureau':      'commercial', 'office':   'commercial',  # office → Commercial
    'ferme':       'commercial', 'farm':     'commercial',  # farm   → Commercial
    'hangar':      'commercial', 'entrepot': 'commercial',
    'entrepôt':    'commercial',
}

LISTING_HINTS = frozenset([
    'annonce', 'listing', 'item', 'immobilier', 'appartement',
    'maison', 'terrain', 'vendre', 'vente', 'rent', 'sale', 'louer',
])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_external_id(source: str, url: str, title: str = '', row_idx: int = 0) -> str:
    """Deterministic SHA-1 hash used as the deduplication key."""
    raw = f"{source}|{url}|{title}|{row_idx}"
    return hashlib.sha1(raw.encode('utf-8', errors='replace')).hexdigest()


def _clean(text: str | None) -> str:
    if not text:
        return ''
    t = str(text).strip()
    if t.lower() in ('nan', 'none', 'null', '-', '—', 'n/a'):
        return ''
    return ' '.join(t.split())


def _parse_price(raw: str | None) -> float | None:
    """Parse Tunisian price strings: handles DT, TND, MD, Mille, comma/dot separators."""
    if not raw:
        return None
    s = str(raw).strip().replace('\xa0', ' ').replace(' ', ' ')
    is_mille = 'mille' in s.lower()
    # Remove currency labels
    s = re.sub(r'(?i)(dt|tnd|md|mille|dinars?)', ' ', s)
    # Extract first numeric-looking token
    m = re.search(r'(\d[\d\s,.]*)', s)
    if not m:
        return None
    token = m.group(1).strip()
    # Detect decimal style: if last separator is comma and it looks like decimals
    if re.search(r',\d{1,2}$', token):
        token = token.replace(' ', '').replace('.', '').replace(',', '.')
    else:
        token = token.replace(' ', '').replace(',', '')
    try:
        val = float(token)
        return val * 1000 if is_mille else val
    except ValueError:
        return None


def _parse_surface(surface_raw: str | None, description: str = '') -> float | None:
    """Extract surface in m² from a raw string or description fallback."""
    for text in filter(None, [surface_raw, description]):
        m = re.search(r'(\d{2,4})\s*(?:m²|m2|m²|\bm\b)', str(text), re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    return None


def _infer_property_type(text: str) -> str:
    """Return internal property_type code from free text."""
    t = text.lower()
    for key, val in PROPERTY_TYPE_MAP.items():
        if key in t:
            return val
    return 'apartment'


def _infer_transaction_type(text: str) -> str:
    """Return 'rent' or 'sale' from free text."""
    t = text.lower()
    rent_kw = ['louer', 'a louer', 'à louer', 'location', 'rent', '/louer/']
    sale_kw = ['vendre', 'a vendre', 'à vendre', 'vente', 'sale', '/vente/', '/vendre/']
    for kw in rent_kw:
        if kw in t:
            return 'rent'
    for kw in sale_kw:
        if kw in t:
            return 'sale'
    return 'sale'


def _split_location(raw: str) -> tuple[str, str, str]:
    """
    Split a raw location string into (governorate, city, neighborhood).
    Handles 'Tunis, La Marsa, Ain Zaghouan' style strings.
    """
    if not raw:
        return '', '', ''
    parts = [p.strip() for p in re.split(r'[,/\-–]', raw) if p.strip()]
    governorate = parts[0] if len(parts) > 0 else ''
    city = parts[1] if len(parts) > 1 else governorate
    neighborhood = parts[2] if len(parts) > 2 else ''
    return governorate, city, neighborhood


def normalize_tunisian_data(raw: dict) -> dict:
    """
    Transform a raw scraper dict into the canonical Silver-layer schema.

    Input keys (from scrapers): source, listing_url, title, description,
        governorate, city, neighborhood, location_raw, property_type,
        transaction_type, price, surface_area, bedrooms, bathrooms, image_url.

    Output adds: price_tnd, surface_m2, property_type (EN code),
        transaction_type, governorate (FR), city, neighborhood, location_raw.
    """
    out = {k: v for k, v in raw.items()}

    # Normalize Arabic governorate names
    gov = _clean(out.get('governorate', ''))
    out['governorate'] = ARABIC_TO_FRENCH_GOVERNORATES.get(gov, gov)

    # Parse price
    out['price_tnd'] = _parse_price(str(out.get('price') or ''))

    # Parse surface
    out['surface_m2'] = _parse_surface(
        str(out.get('surface_area') or out.get('surface_m2') or ''),
        out.get('description', ''),
    )

    # Property type → internal EN code
    pt_raw = _clean(out.get('property_type', ''))
    if not pt_raw:
        pt_raw = _clean(out.get('title', ''))
    out['property_type'] = _infer_property_type(pt_raw)

    # Transaction type
    if not out.get('transaction_type'):
        text = ' '.join([
            out.get('title', ''), out.get('description', ''),
            out.get('source_url', out.get('listing_url', '')),
        ])
        out['transaction_type'] = _infer_transaction_type(text)

    # Ensure bedrooms/bathrooms are ints
    for field in ('bedrooms', 'bathrooms', 'rooms'):
        raw_val = out.get(field)
        if raw_val is not None:
            try:
                out[field] = int(float(str(raw_val)))
            except (ValueError, TypeError):
                out[field] = None

    # Build location_raw if missing
    if not out.get('location_raw'):
        parts = [out.get('governorate', ''), out.get('city', ''), out.get('neighborhood', '')]
        out['location_raw'] = ', '.join(p for p in parts if p)

    # Split location_raw if individual fields are missing
    if not out.get('city') and out.get('location_raw'):
        gov, city, nbh = _split_location(out['location_raw'])
        if not out.get('governorate'):
            out['governorate'] = gov
        if not out.get('city'):
            out['city'] = city
        if not out.get('neighborhood'):
            out['neighborhood'] = nbh

    out['currency'] = 'TND'
    return out


def is_listing_url(url: str) -> bool:
    """Heuristic: does the URL look like an individual property listing?"""
    lower = url.lower()
    return any(hint in lower for hint in LISTING_HINTS)


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

class RequestManager:
    """
    Managed HTTP session with:
    - Random User-Agent rotation
    - Optional proxy rotation
    - Exponential backoff on 429/503 and transient errors
    """

    def __init__(
        self,
        proxies: list[str] | None = None,
        max_retries: int = 4,
        backoff_factor: float = 1.0,
    ):
        self.user_agents = USER_AGENTS
        self.proxies = proxies or []
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = requests.Session()

    def _headers(self) -> dict:
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept-Language': 'fr-FR,fr;q=0.9,ar;q=0.7,en;q=0.5',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }

    def _proxy_conf(self) -> dict | None:
        if not self.proxies:
            return None
        proxy = random.choice(self.proxies)
        return {'http': proxy, 'https': proxy}

    def get(self, url: str, timeout: int = 25, **kwargs) -> requests.Response | None:
        proxy = self._proxy_conf()
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    url,
                    headers=self._headers(),
                    proxies=proxy,
                    timeout=timeout,
                    **kwargs,
                )
                resp.raise_for_status()
                return resp
            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else 0
                if code in (429, 503):
                    wait = self.backoff_factor * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning("HTTP %s on %s, retry %d in %.1fs", code, url, attempt + 1, wait)
                    time.sleep(wait)
                else:
                    logger.error("HTTP %s on %s — aborting", code, url)
                    return None
            except requests.exceptions.ConnectionError as exc:
                wait = self.backoff_factor * (2 ** attempt) + random.uniform(0, 1)
                logger.warning("ConnectionError on %s (attempt %d): %s, retry in %.1fs", url, attempt + 1, exc, wait)
                time.sleep(wait)
            except requests.exceptions.Timeout:
                logger.warning("Timeout on %s (attempt %d)", url, attempt + 1)
                time.sleep(self.backoff_factor * (2 ** attempt))
            except requests.exceptions.RequestException as exc:
                logger.error("Unrecoverable request error on %s: %s", url, exc)
                return None
        logger.error("All %d retries exhausted for %s", self.max_retries, url)
        return None


# ---------------------------------------------------------------------------
# Abstract base scraper
# ---------------------------------------------------------------------------

class BaseScraper(ABC):
    """
    Every site-specific scraper inherits from this class.
    Subclasses implement discover_urls() and scrape_listing().
    scrape_all() orchestrates the full crawl with polite delays.
    """

    SOURCE_NAME: str = ''
    BASE_URL: str = ''

    def __init__(
        self,
        max_listings: int = 100,
        request_manager: RequestManager | None = None,
    ):
        self.max_listings = max_listings
        self.http = request_manager or RequestManager()
        self.log = logging.getLogger(f"scraper.{self.SOURCE_NAME or self.__class__.__name__}")

    @abstractmethod
    def discover_urls(self) -> list[str]:
        """Return up to self.max_listings individual listing URLs."""
        ...

    @abstractmethod
    def scrape_listing(self, url: str) -> dict | None:
        """Scrape one listing URL. Return raw dict or None on failure."""
        ...

    def scrape_all(self) -> list[dict]:
        """Full crawl: discover → scrape each URL → return raw records."""
        urls = self.discover_urls()
        if not urls:
            self.log.warning("No URLs discovered from %s", self.BASE_URL)
            return []
        urls = urls[:self.max_listings]
        self.log.info("[%s] Discovered %d URLs, scraping now…", self.SOURCE_NAME, len(urls))
        results = []
        for i, url in enumerate(urls, 1):
            raw = self.scrape_listing(url)
            if raw:
                raw.setdefault('source', self.SOURCE_NAME)
                raw.setdefault('listing_url', url)
                results.append(raw)
            # Polite crawl delay
            time.sleep(random.uniform(0.8, 2.0))
            if i % 10 == 0:
                self.log.info("[%s] Progress: %d/%d scraped", self.SOURCE_NAME, i, len(urls))
        self.log.info("[%s] Done — %d records collected", self.SOURCE_NAME, len(results))
        return results

    @staticmethod
    def extract_candidate_links(html: str, base_url: str) -> list[str]:
        """
        Extract all <a href> links from raw HTML, resolve relative URLs,
        and filter to likely listing pages.
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        links = []
        for tag in soup.find_all('a', href=True):
            href = tag['href'].strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:')):
                continue
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in ('http', 'https'):
                continue
            links.append(absolute)
        return list(dict.fromkeys(links))  # preserve order, deduplicate
