"""
Bronze -> Silver wrangler.

Takes raw ScrapedListing.raw_data dicts (as returned by scrapers) and
produces normalized_data dicts conforming to the canonical Silver schema.

Platform standards enforced here:
  - Property types: Apartment | House | Commercial | Land (4 types only).
    Villa -> House, Office/Farm -> Commercial.
  - All titles translated to English.
  - Governorate resolved via comprehensive city/neighborhood lookup.
    Properties with no resolvable governorate are rejected (return None).
  - Missing prices / surfaces / bedrooms imputed from governorate-tier
    benchmarks so the Gold layer never has zero values.

Canonical Silver schema fields
--------------------------------
record_id, source, listing_url, title, description, transaction_type,
property_type, price_tnd, surface_m2, price_per_m2, rooms, bedrooms,
bathrooms, governorate, city, delegation_hint, neighborhood, location_raw,
currency, image_url, condition.
"""

import hashlib
import logging
import re
import unicodedata

from scraper.scrapers.base import normalize_tunisian_data, _parse_price, _parse_surface

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_S_PLUS_RE  = re.compile(r'\bS\+?(\d)\b', re.IGNORECASE)
_PIECES_RE  = re.compile(r'(\d+)\s*pi[ee]ces?', re.IGNORECASE)
_CHAMBRE_RE = re.compile(r'(\d+)\s*(?:chambre|bedroom|bed|ch\.?)\b', re.IGNORECASE)
_SALLE_RE   = re.compile(r'(\d+)\s*(?:salle[s]?\s*de\s*bain|sdb|bathroom|bath)\b', re.IGNORECASE)

# Detect category/search-result pages (not real listings).
_CATEGORY_PAGE_RE = re.compile(r'^\d[\d\s]*\s+annonces?\s+(a|a)\b', re.IGNORECASE)

# ---------------------------------------------------------------------------
# 4-type canonical map
# ---------------------------------------------------------------------------

_TYPE_CANONICAL = {
    'apartment':  'apartment',
    'house':      'house',
    'villa':      'house',
    'land':       'land',
    'commercial': 'commercial',
    'office':     'commercial',
    'farm':       'commercial',
}

# ---------------------------------------------------------------------------
# Source display names
# ---------------------------------------------------------------------------

_SOURCE_DISPLAY = {
    'tunisie_annonce':  'Tunisie Annonce',
    'tunisieannonce':   'Tunisie Annonce',
    'mubawab':          'Mubawab',
    'tecnocasa':        'TecnoCasa',
    'tayara':           'Tayara',
    'direct owner':     'Direct Owner',
    'local agency':     'Local Agency',
}


def _display_source(raw: str) -> str:
    return _SOURCE_DISPLAY.get(raw.strip().lower(), raw.strip()) or 'Unknown'


# ---------------------------------------------------------------------------
# Comprehensive city / neighbourhood -> (governorate, delegation) lookup
# ---------------------------------------------------------------------------

def _n(s: str) -> str:
    """Normalise for lookup: lowercase + strip accents."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', s.lower())
        if unicodedata.category(c) != 'Mn'
    ).strip()


# Maps _n(city_name) -> (Governorate, Delegation_name_or_None)
_CITY_LOOKUP: dict[str, tuple[str, str | None]] = {
    # ── Greater Tunis — Tunis governorate ──────────────────────────────
    'tunis':                    ('Tunis', 'Tunis Ville'),
    'tunis ville':              ('Tunis', 'Tunis Ville'),
    'tunis centre':             ('Tunis', 'Tunis Ville'),
    'centre ville':             ('Tunis', 'Tunis Ville'),
    'medina':                   ('Tunis', 'Medina'),
    'bab souika':               ('Tunis', 'Bab Souika'),
    'bab bhar':                 ('Tunis', 'Tunis Ville'),
    'bab el fellah':            ('Tunis', 'Tunis Ville'),
    'le bardo':                 ('Tunis', 'Le Bardo'),
    'bardo':                    ('Tunis', 'Le Bardo'),
    'mutuelle ville':           ('Tunis', 'Le Bardo'),
    'la mutuelle':              ('Tunis', 'Le Bardo'),
    'le kram':                  ('Tunis', 'Le Kram'),
    'kram':                     ('Tunis', 'Le Kram'),
    'la goulette':              ('Tunis', 'La Goulette'),
    'goulette':                 ('Tunis', 'La Goulette'),
    'la marsa':                 ('Tunis', 'La Marsa'),
    'marsa':                    ('Tunis', 'La Marsa'),
    'marsa ennassim':           ('Tunis', 'La Marsa'),
    'marsa maalga':             ('Tunis', 'La Marsa'),
    'cite les pins':            ('Tunis', 'La Marsa'),
    'sidi bou said':            ('Tunis', 'La Marsa'),
    'sidi bousaid':             ('Tunis', 'La Marsa'),
    'el aouina':                ('Tunis', 'El Aouina'),
    'aouina':                   ('Tunis', 'El Aouina'),
    'berge du lac':             ('Tunis', 'Tunis Ville'),
    'berges du lac':            ('Tunis', 'Tunis Ville'),
    'les berges du lac':        ('Tunis', 'Tunis Ville'),
    'lac 2':                    ('Tunis', 'Tunis Ville'),
    'lac':                      ('Tunis', 'Tunis Ville'),
    'belvedere':                ('Tunis', 'Tunis Ville'),
    'el ouardia':               ('Tunis', 'El Ouardia'),
    'el ouerdia':               ('Tunis', 'El Ouardia'),
    'ouerdia':                  ('Tunis', 'El Ouardia'),
    'cite el khadra':           ('Tunis', 'Cite El Khadra'),
    'el khadra':                ('Tunis', 'Cite El Khadra'),
    'sidi hassine':             ('Tunis', 'Sidi Hassine'),
    'djebel jelloud':           ('Tunis', 'Djebel Jelloud'),
    'sejoumi':                  ('Tunis', 'Sejoumi'),
    'el omrane':                ('Tunis', 'El Omrane Superieur'),
    'el omrane superieur':      ('Tunis', 'El Omrane Superieur'),
    'ezzouhour':                ('Tunis', 'Ezzouhour'),
    'hrairia':                  ('Tunis', 'Hrairia'),
    'hraira':                   ('Tunis', 'Hrairia'),
    'ezzitouna':                ('Tunis', 'Tunis Ville'),
    # ── Greater Tunis — Ariana governorate ────────────────────────────
    'ariana':                   ('Ariana', 'Ariana Ville'),
    'ariana ville':             ('Ariana', 'Ariana Ville'),
    'cite ennasr':              ('Ariana', 'Ariana Ville'),
    'cite ennasr 1':            ('Ariana', 'Ariana Ville'),
    'cite ennasr 2':            ('Ariana', 'Ariana Ville'),
    'ennasr':                   ('Ariana', 'Ariana Ville'),
    'cite el ghazala':          ('Ariana', 'Ariana Ville'),
    'cite el ghazala 1':        ('Ariana', 'Ariana Ville'),
    'cite el ghazala 2':        ('Ariana', 'Ariana Ville'),
    'el ghazala':               ('Ariana', 'Ariana Ville'),
    'el menzah':                ('Ariana', 'Ariana Ville'),
    'el menzah 1':              ('Ariana', 'Ariana Ville'),
    'el menzah 2':              ('Ariana', 'Ariana Ville'),
    'el menzah 3':              ('Ariana', 'Ariana Ville'),
    'el menzah 4':              ('Ariana', 'Ariana Ville'),
    'el menzah 5':              ('Ariana', 'Ariana Ville'),
    'el menzah 6':              ('Ariana', 'Ariana Ville'),
    'el menzah 7':              ('Ariana', 'Ariana Ville'),
    'el menzah 8':              ('Ariana', 'Ariana Ville'),
    'el menzah 9':              ('Ariana', 'La Soukra'),
    'el menzah 9a':             ('Ariana', 'La Soukra'),
    'el menzah 9b':             ('Ariana', 'La Soukra'),
    'el menzah 9c':             ('Ariana', 'La Soukra'),
    'menzah':                   ('Ariana', 'Ariana Ville'),
    "jardins d'el menzah":      ('Ariana', 'Ariana Ville'),
    'jardins el menzah':        ('Ariana', 'Ariana Ville'),
    'jardins menzah':           ('Ariana', 'Ariana Ville'),
    'la soukra':                ('Ariana', 'La Soukra'),
    'soukra':                   ('Ariana', 'La Soukra'),
    'chotrana':                 ('Ariana', 'La Soukra'),
    'chotrana 1':               ('Ariana', 'La Soukra'),
    'chotrana 2':               ('Ariana', 'La Soukra'),
    'chotrana 3':               ('Ariana', 'La Soukra'),
    'raoued':                   ('Ariana', 'Raoued'),
    'sidi thabet':              ('Ariana', 'Sidi Thabet'),
    'mnihla':                   ('Ariana', 'Mnihla'),
    'ettadhamen':               ('Ariana', 'Ettadhamen'),
    'ain zaghouan':             ('Ariana', 'Raoued'),
    'ain zaghouan nord':        ('Ariana', 'Raoued'),
    'kalaat landlous':          ('Ariana', 'Kalaat el-Andalous'),
    # ── Greater Tunis — Ben Arous governorate ─────────────────────────
    'ben arous':                ('Ben Arous', 'Ben Arous Ville'),
    'ben arous ville':          ('Ben Arous', 'Ben Arous Ville'),
    'ezzahra':                  ('Ben Arous', 'Ezzahra'),
    'hammam lif':               ('Ben Arous', 'Hammam Lif'),
    'hammam chatt':             ('Ben Arous', 'Hammam Chatt'),
    'rades':                    ('Ben Arous', 'Rades'),
    'el mourouj':               ('Ben Arous', 'El Mourouj'),
    'mourouj':                  ('Ben Arous', 'El Mourouj'),
    'mourouj 6':                ('Ben Arous', 'El Mourouj'),
    'bou mhel':                 ('Ben Arous', 'Bou Mhel el Bassatine'),
    'bou mhel el bassatine':    ('Ben Arous', 'Bou Mhel el Bassatine'),
    'fouchana':                 ('Ben Arous', 'Fouchana'),
    'mhamdia':                  ('Ben Arous', 'Mhamdia'),
    'nouvelle medina':          ('Ben Arous', 'Ben Arous Ville'),
    'douar hicher':             ('Manouba', 'Douar Hicher'),
    # ── Greater Tunis — Manouba governorate ───────────────────────────
    'manouba':                  ('Manouba', 'Manouba Ville'),
    'la manouba':               ('Manouba', 'Manouba Ville'),
    'manouba ville':            ('Manouba', 'Manouba Ville'),
    'tebourba':                 ('Manouba', 'Tebourba'),
    'oued ellil':               ('Manouba', 'Oued Ellil'),
    'denden':                   ('Manouba', 'Denden'),
    'mornaguia':                ('Manouba', 'Mornaguia'),
    # ── Nabeul ────────────────────────────────────────────────────────
    'nabeul':                   ('Nabeul', 'Nabeul Ville'),
    'nabeul ville':             ('Nabeul', 'Nabeul Ville'),
    'hammamet':                 ('Nabeul', 'Hammamet'),
    'hammamet nord':            ('Nabeul', 'Hammamet'),
    'hammamet sud':             ('Nabeul', 'Hammamet'),
    'hammamet centre':          ('Nabeul', 'Hammamet'),
    'zone hoteliere':           ('Nabeul', 'Hammamet'),
    'korba':                    ('Nabeul', 'Korba'),
    'kelibia':                  ('Nabeul', 'Kelibia'),
    'grombalia':                ('Nabeul', 'Grombalia'),
    'soliman':                  ('Nabeul', 'Soliman'),
    'menzel bouzelfa':          ('Nabeul', 'Menzel Bouzelfa'),
    'menzel temime':            ('Nabeul', 'Menzel Temime'),
    'bou argoub':               ('Nabeul', 'Bou Argoub'),
    # ── Zaghouan ──────────────────────────────────────────────────────
    'zaghouan':                 ('Zaghouan', 'Zaghouan Ville'),
    'zaghouan ville':           ('Zaghouan', 'Zaghouan Ville'),
    'zriba':                    ('Zaghouan', 'Zriba'),
    'nadhour':                  ('Zaghouan', 'Nadhour'),
    # ── Bizerte ───────────────────────────────────────────────────────
    'bizerte':                  ('Bizerte', 'Bizerte Nord'),
    'bizerte nord':             ('Bizerte', 'Bizerte Nord'),
    'bizerte sud':              ('Bizerte', 'Bizerte Sud'),
    'ras jebel':                ('Bizerte', 'Ras Jebel'),
    'menzel bourguiba':         ('Bizerte', 'Menzel Bourguiba'),
    'menzel jemil':             ('Bizerte', 'Menzel Jemil'),
    'mateur':                   ('Bizerte', 'Mateur'),
    # ── Beja ──────────────────────────────────────────────────────────
    'beja':                     ('Beja', 'Beja Ville'),
    'beja ville':               ('Beja', 'Beja Ville'),
    'medjez el bab':            ('Beja', 'Medjez el Bab'),
    'testour':                  ('Beja', 'Testour'),
    'teboursouk':               ('Beja', 'Teboursouk'),
    # ── Jendouba ──────────────────────────────────────────────────────
    'jendouba':                 ('Jendouba', 'Jendouba Ville'),
    'tabarka':                  ('Jendouba', 'Tabarka'),
    'ain draham':               ('Jendouba', 'Ain Draham'),
    'bou salem':                ('Jendouba', 'Bou Salem'),
    # ── Kef ───────────────────────────────────────────────────────────
    'kef':                      ('Kef', 'Kef Ville'),
    'le kef':                   ('Kef', 'Kef Ville'),
    'el kef':                   ('Kef', 'Kef Ville'),
    'kef ville':                ('Kef', 'Kef Ville'),
    'tajerouine':               ('Kef', 'Tajerouine'),
    'dahmani':                  ('Kef', 'Dahmani'),
    # ── Siliana ───────────────────────────────────────────────────────
    'siliana':                  ('Siliana', 'Siliana Ville'),
    'makthar':                  ('Siliana', 'Makthar'),
    'rouhia':                   ('Siliana', 'Rouhia'),
    # ── Sousse ────────────────────────────────────────────────────────
    'sousse':                   ('Sousse', 'Sousse Medina'),
    'sousse ville':             ('Sousse', 'Sousse Medina'),
    'sousse medina':            ('Sousse', 'Sousse Medina'),
    'hammam sousse':            ('Sousse', 'Hammam Sousse'),
    'sahloul':                  ('Sousse', 'Sahloul'),
    'sahloul 4':                ('Sousse', 'Sahloul'),
    'akouda':                   ('Sousse', 'Akouda'),
    'kalaa kbira':              ('Sousse', 'Kalaa Kbira'),
    'kalaa sghra':              ('Sousse', 'Kalaa Sghra'),
    'kantaoui':                 ('Sousse', 'Hammam Sousse'),
    'port el kantaoui':         ('Sousse', 'Hammam Sousse'),
    'msaken':                   ('Sousse', 'Msaken'),
    # ── Monastir ──────────────────────────────────────────────────────
    'monastir':                 ('Monastir', 'Monastir Ville'),
    'monastir ville':           ('Monastir', 'Monastir Ville'),
    'skanes':                   ('Monastir', 'Monastir Ville'),
    'ksar hellal':              ('Monastir', 'Ksar Hellal'),
    'moknine':                  ('Monastir', 'Moknine'),
    'jammel':                   ('Monastir', 'Jammel'),
    'bekalta':                  ('Monastir', 'Bekalta'),
    'teboulba':                 ('Monastir', 'Teboulba'),
    # ── Mahdia ────────────────────────────────────────────────────────
    'mahdia':                   ('Mahdia', 'Mahdia Ville'),
    'mahdia ville':             ('Mahdia', 'Mahdia Ville'),
    'el jem':                   ('Mahdia', 'El Jem'),
    'ksour essef':              ('Mahdia', 'Ksour Essef'),
    'chebba':                   ('Mahdia', 'Chebba'),
    'rejiche':                  ('Mahdia', 'Rejiche'),
    # ── Sfax ──────────────────────────────────────────────────────────
    'sfax':                     ('Sfax', 'Sfax Ville'),
    'sfax ville':               ('Sfax', 'Sfax Ville'),
    'sfax sud':                 ('Sfax', 'Sfax Sud'),
    'sfax nord':                ('Sfax', 'Sfax Nord'),
    'chihia':                   ('Sfax', 'Chihia'),
    'el ain':                   ('Sfax', 'El Ain'),
    'mahres':                   ('Sfax', 'Mahres'),
    # ── Kairouan ──────────────────────────────────────────────────────
    'kairouan':                 ('Kairouan', 'Kairouan Ville'),
    'kairouan ville':           ('Kairouan', 'Kairouan Ville'),
    'sbeitla':                  ('Kairouan', 'Sbeitla'),
    'haffouz':                  ('Kairouan', 'Haffouz'),
    # ── Kasserine ─────────────────────────────────────────────────────
    'kasserine':                ('Kasserine', 'Kasserine Ville'),
    'thala':                    ('Kasserine', 'Thala'),
    'feriana':                  ('Kasserine', 'Feriana'),
    'foussana':                 ('Kasserine', 'Foussana'),
    # ── Sidi Bouzid ───────────────────────────────────────────────────
    'sidi bouzid':              ('Sidi Bouzid', 'Sidi Bouzid Ville'),
    'jelma':                    ('Sidi Bouzid', 'Jelma'),
    'regueb':                   ('Sidi Bouzid', 'Regueb'),
    'meknassi':                 ('Sidi Bouzid', 'Meknassi'),
    # ── Gabes ─────────────────────────────────────────────────────────
    'gabes':                    ('Gabes', 'Gabes Ville'),
    'gabes ville':              ('Gabes', 'Gabes Ville'),
    'mareth':                   ('Gabes', 'Mareth'),
    'matmata':                  ('Gabes', 'Matmata'),
    'zanouch':                  ('Gabes', 'Zanouch'),
    # ── Medenine ──────────────────────────────────────────────────────
    'medenine':                 ('Medenine', 'Medenine Ville'),
    'medenine ville':           ('Medenine', 'Medenine Ville'),
    'djerba':                   ('Medenine', 'Djerba - Houmt Souk'),
    'houmt souk':               ('Medenine', 'Djerba - Houmt Souk'),
    'djerba houmt souk':        ('Medenine', 'Djerba - Houmt Souk'),
    'midoun':                   ('Medenine', 'Djerba - Midoun'),
    'djerba midoun':            ('Medenine', 'Djerba - Midoun'),
    'zarzis':                   ('Medenine', 'Zarzis'),
    'ben gardane':              ('Medenine', 'Ben Gardane'),
    # ── Tataouine ─────────────────────────────────────────────────────
    'tataouine':                ('Tataouine', 'Tataouine Ville'),
    'ghomrassen':               ('Tataouine', 'Ghomrassen'),
    'remada':                   ('Tataouine', 'Remada'),
    # ── Gafsa ─────────────────────────────────────────────────────────
    'gafsa':                    ('Gafsa', 'Gafsa Ville'),
    'metlaoui':                 ('Gafsa', 'Metlaoui'),
    'moulares':                 ('Gafsa', 'Moulares'),
    # ── Tozeur ────────────────────────────────────────────────────────
    'tozeur':                   ('Tozeur', 'Tozeur Ville'),
    'nefta':                    ('Tozeur', 'Nefta'),
    'degache':                  ('Tozeur', 'Degache'),
    # ── Kebili ────────────────────────────────────────────────────────
    'kebili':                   ('Kebili', 'Kebili Ville'),
    'kebili ville':             ('Kebili', 'Kebili Ville'),
    'douz':                     ('Kebili', 'Douz'),
    'souk lahad':               ('Kebili', 'Souk Lahad'),
}

# Default delegation name per governorate (used when no specific match found)
_DEFAULT_DELEGATION: dict[str, str] = {
    'Tunis':       'Tunis Ville',
    'Ariana':      'Ariana Ville',
    'Ben Arous':   'Ben Arous Ville',
    'Manouba':     'Manouba Ville',
    'Nabeul':      'Nabeul Ville',
    'Zaghouan':    'Zaghouan Ville',
    'Bizerte':     'Bizerte Nord',
    'Beja':        'Beja Ville',
    'Jendouba':    'Jendouba Ville',
    'Kef':         'Kef Ville',
    'Siliana':     'Siliana Ville',
    'Sousse':      'Sousse Medina',
    'Monastir':    'Monastir Ville',
    'Mahdia':      'Mahdia Ville',
    'Sfax':        'Sfax Ville',
    'Kairouan':    'Kairouan Ville',
    'Kasserine':   'Kasserine Ville',
    'Sidi Bouzid': 'Sidi Bouzid Ville',
    'Gabes':       'Gabes Ville',
    'Medenine':    'Medenine Ville',
    'Tataouine':   'Tataouine Ville',
    'Gafsa':       'Gafsa Ville',
    'Tozeur':      'Tozeur Ville',
    'Kebili':      'Kebili Ville',
}


def _lookup_city(raw: str) -> tuple[str, str | None] | None:
    """
    Return (governorate, delegation_hint) for a city/neighbourhood name, or None.
    Tries exact match, then strips common prefixes ('cite ', 'quartier ', etc.).
    """
    if not raw:
        return None
    key = _n(raw)
    if key in _CITY_LOOKUP:
        return _CITY_LOOKUP[key]
    for prefix in ('cite ', 'cite el ', 'cite en', 'quartier ', 'hay ', 'zone '):
        if key.startswith(prefix):
            stripped = key[len(prefix):]
            if stripped in _CITY_LOOKUP:
                return _CITY_LOOKUP[stripped]
    return None


# ---------------------------------------------------------------------------
# Governorate text inference (fallback when city lookup fails)
# ---------------------------------------------------------------------------

_GOVERNORATES = [
    ('Ben Arous',   ['ben arous', 'benarous', 'ezzahra', 'hammam lif', 'bou mhel', 'mourouj', 'hammam chatt']),
    ('Ariana',      ['ariana', 'soukra', 'raoued', 'mnihla', 'ettadhamen', 'chotrana',
                     'menzah', 'ennasr', 'ghazala']),
    ('Tunis',       ['tunis', 'la marsa', 'marsa', 'carthage', 'mutuelle ville',
                     'aouina', 'berge du lac', 'bardo', 'goulette']),
    ('Manouba',     ['manouba', 'la manouba', 'mornaguia', 'denden', 'oued ellil']),
    ('Nabeul',      ['nabeul', 'hammamet', 'kelibia', 'korba', 'soliman', 'grombalia']),
    ('Zaghouan',    ['zaghouan']),
    ('Bizerte',     ['bizerte', 'bizerta', 'ras jebel', 'menzel bourguiba']),
    ('Beja',        ['beja']),
    ('Jendouba',    ['jendouba', 'tabarka', 'bou salem', 'ain draham']),
    ('Kef',         ['kef', 'le kef', 'el kef', 'tajerouine', 'dahmani']),
    ('Siliana',     ['siliana', 'makthar', 'rouhia']),
    ('Sousse',      ['sousse', 'sahloul', 'kantaoui', 'hammam sousse', 'akouda', 'kalaa kbira']),
    ('Monastir',    ['monastir', 'skanes', 'ksar hellal', 'msaken', 'moknine', 'jammel']),
    ('Mahdia',      ['mahdia', 'el jem', 'ksour essef']),
    ('Sfax',        ['sfax']),
    ('Kairouan',    ['kairouan', 'sbeitla', 'haffouz']),
    ('Kasserine',   ['kasserine', 'thala', 'feriana', 'foussana']),
    ('Sidi Bouzid', ['sidi bouzid', 'jelma', 'regueb', 'meknassi']),
    ('Gabes',       ['gabes', 'mareth', 'matmata', 'zanouch']),
    ('Medenine',    ['medenine', 'djerba', 'houmt souk', 'zarzis', 'ben gardane', 'midoun']),
    ('Tataouine',   ['tataouine', 'ghomrassen', 'remada']),
    ('Gafsa',       ['gafsa', 'metlaoui', 'moulares']),
    ('Tozeur',      ['tozeur', 'nefta', 'degache']),
    ('Kebili',      ['kebili', 'douz', 'souk lahad']),
]


def _infer_governorate(text: str) -> str:
    t = _n(text)
    for gov, aliases in _GOVERNORATES:
        if any(alias in t for alias in aliases):
            return gov
    return ''


# ---------------------------------------------------------------------------
# English title builder
# ---------------------------------------------------------------------------

# Ordered list of (pattern, replacement) — most specific first.
_TITLE_SUBS = [
    (r'\bhaut[- ]?standing\b',                          'Luxury'),
    (r'\bbelle[- ]?opportunit[ee]\b',                   'Great Opportunity'),
    (r"\ba ne pas rater\b",                             'Must-See'),
    (r"\ba ne pas ratez\b",                             'Must-See'),
    (r'\ba saisir\b',                                   'Must-See'),
    (r'\bau bord du lac\b',                             'Lakeside'),
    (r'\bau bord (du|de la)\b',                         'Waterfront'),
    (r'\bcentre[- ]?ville\b',                           'City Center'),
    (r'\bplein[- ]?centre\b',                           'City Center'),
    (r'\bau c[oe]ur (de |d\')?',                        'in the Heart of '),
    (r'\brez[- ]?de[- ]?chauss[ee]e\b',                 'Ground Floor'),
    (r'\brdc\b',                                        'Ground Floor'),
    (r'\bstation\b',                                    ''),
    # Type words (already encoded in property_type field)
    (r'\bvilla\b',        ''),
    (r'\bappartement\b',  ''),
    (r'\bappart\b',       ''),
    (r'\bterrain\b',      ''),
    (r'\bmaison\b',       ''),
    (r'\bbureau\b',       ''),
    (r'\bferme\b',        ''),
    (r'\blocal\b',        ''),
    (r'\bimmobilier\b',   ''),
    # Keep these as descriptors
    (r'\bstudio\b',           'Studio'),
    (r'\bduplex\b',           'Duplex'),
    (r'\btriplex\b',          'Triplex'),
    (r'\bresidence\b',        'Residence'),
    (r'\blotissement\b',      'Subdivision'),
    (r'\bprojet\b',           'Project'),
    # Condition / quality
    (r'\bjamais habite\b',    'Never Inhabited'),
    (r'\brenove[e]?\b',       'Renovated'),
    (r'\bmeuble[e]?\b',       'Furnished'),
    (r'\bclimatise[e]?\b',    'Air-Conditioned'),
    (r'\bspacieux\b',         'Spacious'),
    (r'\bspacieuse\b',        'Spacious'),
    (r'\bindependant[e]?\b',  'Independent'),
    (r'\blumineux\b',         'Bright'),
    (r'\blumineuse\b',        'Bright'),
    (r'\bmoderne\b',          'Modern'),
    (r'\bluxueux\b',          'Luxury'),
    (r'\bluxueuse\b',         'Luxury'),
    (r'\bluxe\b',             'Luxury'),
    (r'\belegance\b',         'Elegance'),
    (r'\bocca\b',             'Opportunity'),
    (r'\boccasion\b',         'Opportunity'),
    (r'\bopportunite\b',      'Opportunity'),
    (r'\brare\b',             'Rare'),
    (r'\bunique\b',           'Unique'),
    (r'\bneuf\b',             'New'),
    (r'\bnouveau\b',          'New'),
    (r'\bnouvelle\b',         'New'),
    (r'\bneuve\b',            'New'),
    (r'\bgrande?\b',          'Large'),
    (r'\bpetite?\b',          'Small'),
    (r'\bancien[ne]?\b',      'Old'),
    (r'\bnord\b',             'North'),
    (r'\bsud\b',              'South'),
    # French noise to remove
    (r'\bnu\b',   ''),
    (r'\bde la\b',''),  (r"\bl'",    ''),
    (r"\bd'el\b", 'El '),(r"\bd'",   ''),
    (r'\bdu\b',   ''),  (r'\bdes\b', ''),
    (r'\bau\b',   ''),  (r'\baux\b', ''),
    (r'\bde\b',   ''),  (r'\ben\b',  ''),
    (r'\bun[e]?\b',''), (r'\ble\b',  ''),
    (r'\bla\b',   ''),  (r'\bles\b', ''),
    (r'\bdans\b', ''),  (r'\bpour\b',''),
    (r'\bpas\b',  ''),  (r'\bne\b',  ''),
    (r'\bet\b',   ''),  (r'\bou\b',  ''),
    (r'\bpar\b',  ''),  (r'\bsur\b', ''),
    (r'\bvente\b',''),  (r'\bnul\b', ''),
    (r'\ba vendre\b',''),
    (r'\ba louer\b', ''),
    (r'\bhs[pt]\b',  ''),
    # Punctuation cleanup
    (r'[:;]+', ' '),
    (r'[—–]',  '-'),
    (r'[\(\)]', ' '),
]

_TYPE_EN = {
    'apartment':  'Apartment',
    'house':      'House',
    'commercial': 'Commercial Space',
    'land':       'Land Plot',
}


def _build_english_title(raw: str, ptype: str, governorate: str = '', location: str = '') -> str:
    """
    Convert a French-dominant real estate listing title to clean English.
    Format: {TypeEN} {Spec} {Descriptor} at {Location}, {Governorate}
    """
    t = _n(raw)  # strip accents + lowercase for pattern matching

    # Split off location: take everything after last ' a ' (normalised 'a' with accent)
    loc_part  = location or ''
    desc_part = raw
    if ' a ' in t:
        idx = t.rfind(' a ')
        if not loc_part:
            loc_part = raw[idx + 3:].strip()
        desc_part = raw[:idx].strip()
    elif ' - ' in raw:
        parts = raw.rsplit(' - ', 1)
        desc_part = parts[0].strip()
        if not loc_part:
            loc_part = parts[1].strip()

    # Extract S+N spec before translation
    spec = ''
    m = re.search(r'\bS\+?(\d)\b', desc_part, re.IGNORECASE)
    if m:
        spec = f'S+{m.group(1)}'
        desc_part = (desc_part[:m.start()] + desc_part[m.end():]).strip()

    # Apply translations on accent-normalised version
    d = _n(desc_part)
    for pattern, replacement in _TITLE_SUBS:
        d = re.sub(pattern, ' ' + replacement + ' ', d, flags=re.IGNORECASE)

    # Collapse whitespace and capitalise
    d = re.sub(r'\s+', ' ', d).strip(' -,.')
    words = d.split()
    noise = {'a', 'an', 'the', 'at', 'in', 'of', 'for', 'with', 'and', 'or', 'by'}
    d = ' '.join(w.capitalize() if (i == 0 or w.lower() not in noise) else w
                 for i, w in enumerate(words))

    # Build final title parts
    type_en = _TYPE_EN.get(ptype, 'Property')
    parts = [type_en]
    if spec:
        parts.append(spec)

    # Only include descriptor if it adds real information
    cleaned = d.strip()
    type_in_d = cleaned.lower().replace(type_en.lower(), '').replace(ptype, '')
    if len(type_in_d.strip()) > 3:
        # Remove repeated type word if present
        cleaned = re.sub(re.escape(type_en), '', cleaned, flags=re.IGNORECASE).strip(' -,')
        if cleaned:
            parts.append(cleaned)

    # Location suffix
    if loc_part:
        loc_str = loc_part.strip()
        if governorate and _n(governorate) not in _n(loc_str):
            parts.append(f'at {loc_str}, {governorate}')
        else:
            parts.append(f'at {loc_str}')
    elif governorate:
        parts.append(f'in {governorate}')

    result = ' '.join(p for p in parts if p).strip()
    return result or f'{type_en} in {governorate}' if governorate else type_en


# ---------------------------------------------------------------------------
# Price / area benchmarks for professional imputation
# ---------------------------------------------------------------------------

_GOV_TIER: dict[str, int] = {
    'Tunis': 1, 'Ariana': 1, 'Ben Arous': 1,
    'Nabeul': 2, 'Sousse': 2, 'Monastir': 2, 'Sfax': 2, 'Bizerte': 2, 'Manouba': 2,
    'Mahdia': 3, 'Zaghouan': 3, 'Kairouan': 3,
    'Beja': 4, 'Jendouba': 4, 'Kef': 4, 'Siliana': 4,
    'Kasserine': 5, 'Sidi Bouzid': 5, 'Gabes': 5, 'Medenine': 5,
    'Tataouine': 5, 'Gafsa': 5, 'Tozeur': 5, 'Kebili': 5,
}

_BENCH_PRICE_SALE: dict[tuple, float] = {
    (1, 'apartment'): 370_000, (2, 'apartment'): 245_000, (3, 'apartment'): 155_000,
    (4, 'apartment'): 105_000, (5, 'apartment'):  75_000,
    (1, 'house'):     680_000, (2, 'house'):     470_000, (3, 'house'):     295_000,
    (4, 'house'):     190_000, (5, 'house'):     135_000,
    (1, 'commercial'):260_000, (2, 'commercial'):175_000, (3, 'commercial'):110_000,
    (4, 'commercial'): 78_000, (5, 'commercial'): 55_000,
    (1, 'land'):      200_000, (2, 'land'):      125_000, (3, 'land'):       72_000,
    (4, 'land'):       46_000, (5, 'land'):       28_000,
}
_BENCH_PRICE_RENT: dict[tuple, float] = {
    (1, 'apartment'): 1_450, (2, 'apartment'): 980, (3, 'apartment'): 620,
    (4, 'apartment'):   430, (5, 'apartment'): 310,
    (1, 'house'):      2_300, (2, 'house'):   1_550, (3, 'house'):     960,
    (4, 'house'):        680, (5, 'house'):     460,
    (1, 'commercial'): 2_100, (2, 'commercial'):1_350, (3, 'commercial'):820,
    (4, 'commercial'):   560, (5, 'commercial'): 370,
    (1, 'land'):         620, (2, 'land'):      380, (3, 'land'):       230,
    (4, 'land'):         160, (5, 'land'):       100,
}
_BENCH_SURFACE: dict[str, float] = {
    'apartment': 90.0, 'house': 185.0, 'commercial': 115.0, 'land': 350.0,
}
_BENCH_BEDROOMS: dict[str, int] = {
    'apartment': 2, 'house': 3, 'commercial': 0, 'land': 0,
}
_MIN_SALE: dict[str, float] = {
    'apartment': 12_000, 'house': 18_000, 'commercial': 8_000, 'land': 2_000,
}
_MAX_RENT: dict[str, float] = {
    'apartment': 9_000, 'house': 14_000, 'commercial': 12_000, 'land': 2_500,
}


def _benchmark_price(ptype: str, tx: str, gov: str) -> float:
    tier  = _GOV_TIER.get(gov, 3)
    table = _BENCH_PRICE_RENT if tx == 'rent' else _BENCH_PRICE_SALE
    return table.get((tier, ptype), table.get((3, ptype), 150_000))


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _extract_rooms(text: str) -> int | None:
    m = _S_PLUS_RE.search(text)
    if m:
        return int(m.group(1)) + 1
    m = _PIECES_RE.search(text)
    return int(m.group(1)) if m else None


def _extract_bedrooms(text: str) -> int | None:
    m = _CHAMBRE_RE.search(text)
    return int(m.group(1)) if m else None


def _extract_bathrooms(text: str) -> int | None:
    m = _SALLE_RE.search(text)
    return int(m.group(1)) if m else None


def _infer_condition(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ['neuf', 'new', 'jamais habite', 'standing', 'haut standing']):
        return 'New'
    if any(k in t for k in ['excellent', 'tres bon', 'parfait']):
        return 'Excellent'
    if any(k in t for k in ['bon etat', 'bien entretenu', 'good']):
        return 'Good'
    if any(k in t for k in ['moyen', 'acceptable', 'passable']):
        return 'Fair'
    if any(k in t for k in ['renover', 'renovation', 'travaux', 'refaire']):
        return 'Needs Renovation'
    return 'Good'


def _build_record_id(source: str, url: str, title: str) -> str:
    raw = f"{source}|{url}|{title}"
    return hashlib.sha1(raw.encode('utf-8', errors='replace')).hexdigest()


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Main wrangler class
# ---------------------------------------------------------------------------

class DataWrangler:
    """
    Bronze raw_data -> Silver normalized_data.

    Steps:
      1.  Reject category pages.
      2.  Apply normalize_tunisian_data.
      3.  Canonicalize type to 4-type system.
      4.  Extract location from title (after 'a') and resolve governorate +
          delegation via _CITY_LOOKUP.  Discard if no governorate found.
      5.  Enrich bedrooms / bathrooms / rooms from text.
      6.  Validate price ranges; reject implausible sale/rent amounts.
      7.  Impute missing price / surface / bedrooms from tier benchmarks.
      8.  Build clean English title.
      9.  Return canonical Silver dict including delegation_hint.
    """

    MIN_PRICE    = 100
    MAX_PRICE    = 50_000_000
    MIN_SURFACE  = 10
    MAX_SURFACE  = 5_000
    MAX_BEDROOMS = 15
    MAX_BATHROOMS = 10

    def wrangle(self, raw: dict) -> dict | None:
        try:
            return self._wrangle(raw)
        except Exception as exc:
            logger.warning("Wrangler error on %s: %s", raw.get('listing_url', '?'), exc)
            return None

    def _wrangle(self, raw: dict) -> dict | None:
        # Step 1 — reject category pages
        title_raw = str(raw.get('title') or '').strip()
        if _CATEGORY_PAGE_RE.match(title_raw):
            return None

        # Step 2 — base normalisation
        data = normalize_tunisian_data(raw)

        title       = str(data.get('title') or '').strip()
        description = str(data.get('description') or '').strip()
        combined    = f"{title} {description}"

        # Step 3 — canonical 4-type
        raw_type      = str(data.get('property_type') or 'apartment').lower()
        property_type = _TYPE_CANONICAL.get(raw_type, 'apartment')

        # Step 4 — location resolution
        # Extract location from title: text after last ' a ' (accents normalised)
        title_normalized = _n(title)
        title_location = ''
        if ' a ' in title_normalized:
            idx = title_normalized.rfind(' a ')
            title_location = title[idx + 3:].strip()

        city         = str(data.get('city') or '').strip()
        location_raw = str(data.get('location_raw') or '').strip()
        governorate  = str(data.get('governorate') or '').strip()

        gov_from_lookup   = None
        deleg_from_lookup = None

        # Priority: title location > scraper city > location_raw > inference
        for candidate in [title_location, city, location_raw]:
            if candidate:
                result = _lookup_city(candidate)
                if result:
                    gov_from_lookup, deleg_from_lookup = result
                    break

        if gov_from_lookup:
            governorate = gov_from_lookup
            if not city and title_location:
                city = title_location
        elif not governorate:
            governorate = _infer_governorate(combined) or _infer_governorate(location_raw)

        # Discard if no governorate can be determined
        if not governorate:
            logger.debug("No governorate for '%s' — discarding", title[:60])
            return None

        # Resolve delegation hint
        if not deleg_from_lookup:
            if city:
                r = _lookup_city(city)
                if r:
                    deleg_from_lookup = r[1]
            if not deleg_from_lookup:
                deleg_from_lookup = _DEFAULT_DELEGATION.get(governorate)

        # Step 5 — enrich from text
        price_tnd  = _safe_float(data.get('price_tnd')) or _parse_price(str(data.get('price') or ''))
        surface_m2 = _safe_float(data.get('surface_m2')) or _parse_surface('', combined)

        bedrooms  = _safe_int(data.get('bedrooms'))  or _extract_bedrooms(combined)
        bathrooms = _safe_int(data.get('bathrooms')) or _extract_bathrooms(combined)
        rooms     = _safe_int(data.get('rooms'))     or _extract_rooms(combined)

        tx_type = str(data.get('transaction_type') or 'sale').lower()
        if tx_type not in ('sale', 'rent'):
            tx_type = 'sale'

        # Step 6 — validate ranges
        if price_tnd is not None and not (self.MIN_PRICE <= price_tnd <= self.MAX_PRICE):
            price_tnd = None
        if tx_type == 'sale' and price_tnd is not None:
            if price_tnd < _MIN_SALE.get(property_type, 10_000):
                price_tnd = None
        if tx_type == 'rent' and price_tnd is not None:
            if price_tnd > _MAX_RENT.get(property_type, 10_000):
                price_tnd = None
        if surface_m2 is not None and not (self.MIN_SURFACE <= surface_m2 <= self.MAX_SURFACE):
            surface_m2 = None
        if bedrooms is not None:
            bedrooms = max(0, min(bedrooms, self.MAX_BEDROOMS))
        if bathrooms is not None:
            bathrooms = max(0, min(bathrooms, self.MAX_BATHROOMS))

        if not title and price_tnd is None:
            return None

        # Step 7 — imputation
        if price_tnd is None:
            price_tnd = _benchmark_price(property_type, tx_type, governorate)
        if surface_m2 is None:
            surface_m2 = _BENCH_SURFACE.get(property_type, 90.0)
        if bedrooms is None and property_type in ('apartment', 'house'):
            bedrooms = max(1, rooms - 1) if rooms else _BENCH_BEDROOMS.get(property_type, 2)
        if bathrooms is None and property_type in ('apartment', 'house'):
            bathrooms = max(1, (bedrooms or 2) // 2)

        price_per_m2 = round(price_tnd / surface_m2, 2) if price_tnd and surface_m2 > 0 else None
        condition    = _infer_condition(_n(description))

        source      = str(data.get('source') or raw.get('source') or '')
        listing_url = str(data.get('listing_url') or raw.get('listing_url') or '')
        record_id   = _build_record_id(source, listing_url, title)

        # Step 8 — English title
        english_title = _build_english_title(
            title, property_type, governorate, title_location or city
        )

        return {
            'record_id':        record_id,
            'source':           _display_source(source),
            'listing_url':      listing_url,
            'title':            english_title or title,
            'description':      description,
            'transaction_type': tx_type,
            'property_type':    property_type,
            'price_tnd':        price_tnd,
            'surface_m2':       surface_m2,
            'price_per_m2':     price_per_m2,
            'rooms':            rooms,
            'bedrooms':         bedrooms,
            'bathrooms':        bathrooms,
            'governorate':      governorate,
            'city':             city or title_location,
            'delegation_hint':  deleg_from_lookup,
            'neighborhood':     str(data.get('neighborhood') or '').strip(),
            'location_raw':     location_raw,
            'currency':         'TND',
            'image_url':        data.get('image_url') or None,
            'condition':        condition,
        }
