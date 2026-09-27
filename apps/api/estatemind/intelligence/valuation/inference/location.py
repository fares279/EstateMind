"""Location normalization shared by valuation training (ml/) and serving.

Listing locations are free text: the scraped 'governorate' field holds 320
distinct values for Tunisia's 24 governorates ('2', 'Ain Zaghouan Nord à La
Marsa', 'Benarous', ...). Models trained with LOCATION_NORMALIZATION = 'v1'
see normalized values, so serving must normalize the same way before building
features; older models were trained on the raw values.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from functools import lru_cache

from config.paths import DATA_DIR

LOCATION_NORMALIZATION = 'v1'
UNKNOWN = 'unknown'


def plain(text: str | None) -> str:
    """Lowercase, accents removed, punctuation collapsed to single spaces."""
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


@lru_cache(maxsize=1)
def _reference() -> tuple[dict[str, str], dict[str, str]]:
    """(governorate plain name -> plain name, delegation plain name -> governorate)."""
    governorates, delegations = {}, {}
    with open(DATA_DIR / 'delegations.csv', encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            gov = plain(row.get('Governorate'))
            if gov:
                governorates[gov] = gov
                delegations[plain(row.get('Delegation'))] = gov
    # Common spellings in listings
    governorates.update({'manouba': 'la manouba', 'kef': 'le kef', 'benarous': 'ben arous',
                         # accented letter dropped entirely by the scraper
                         'gabs': 'gabes', 'mdenine': 'medenine', 'kbili': 'kebili', 'bja': 'beja'})
    return governorates, delegations


def _hits(text: str, tables: tuple[dict[str, str], ...]) -> list[tuple[str, int]]:
    """(governorate, end position) for every governorate or delegation name in `text`."""
    padded = f' {text} '
    found: dict[str, tuple[str, int]] = {}  # one vote per name ('zaghouan' is a governorate and a delegation)
    for table in tables:
        for name, gov in table.items():
            start = padded.rfind(f' {name} ') if name else -1
            if start >= 0 and name not in found:
                found[name] = (gov, start + len(name))
    return list(found.values())


def normalize_governorate(governorate: str | None, city: str | None = None, location: str | None = None) -> str:
    """Official governorate (plain, e.g. 'ben arous') for a listing's location fields.

    Exact governorate or delegation names win. Otherwise every governorate and
    delegation name found in the three fields votes for its governorate; ties
    go to the name ending last in the earliest field that has one (addresses
    run from specific to general): 'Ain Zaghouan Nord a La Marsa' -> Tunis,
    while 'Sfax Medina' with city 'Sfax' -> Sfax, not the Tunis delegation Medina.
    """
    governorates, delegations = _reference()
    gov, cty, loc = plain(governorate), plain(city), plain(location)
    if gov in governorates:
        return governorates[gov]
    if cty in delegations:
        return delegations[cty]
    votes: dict[str, int] = {}
    position: dict[str, int] = {}
    for rank, text in enumerate((gov, cty, loc)):
        for g, end in _hits(text, (governorates, delegations)):
            votes[g] = votes.get(g, 0) + 1
            position[g] = max(position.get(g, -10**9), end - rank * 10_000)
    if not votes:
        return UNKNOWN
    return max(votes, key=lambda g: (votes[g], position[g]))


def normalize_city(city: str | None) -> str:
    return plain(city) or UNKNOWN
