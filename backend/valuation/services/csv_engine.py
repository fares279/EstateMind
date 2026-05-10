"""
Data-driven price engine built from the preprocessed listings CSV.
Provides real market priors derived from actual Tunisian property data,
replacing hard-coded heuristic constants wherever possible.
"""
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── CSV location (copied from Scrapper agent) ─────────────────────────────────
_CSV_PATH = Path(__file__).resolve().parents[2] / 'valuation' / 'data' / 'listings.csv'

# ── Property type normalization ───────────────────────────────────────────────
# Django canonical → CSV canonical (lowercase)
_TYPE_MAP = {
    'apartment':   'appartement',
    'house':       'maison',
    'commercial':  None,           # No Commercial in CSV — use gov heuristic
    'land':        'terrain',
    'appartement': 'appartement',
    'maison':      'maison',
    'terrain':     'terrain',
    'villa':       'maison',
}


def _norm(value) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    if not value:
        return ''
    s = str(value)
    if s.lower() in ('nan', 'none', ''):
        return ''
    text = unicodedata.normalize('NFKD', s)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    return re.sub(r'\s+', ' ', text)


class _CSVEngine:
    """Lazy-loaded, module-singleton CSV price engine."""

    def __init__(self) -> None:
        self._loaded = False
        # (city_norm, gov_norm, ptype, txtype) -> median ppm2
        self._city_gov_ppm2: dict = {}
        # (gov_norm, ptype, txtype) -> median ppm2
        self._gov_ppm2: dict = {}
        # (ptype, txtype) -> median ppm2
        self._global_ppm2: dict = {}
        self._df = None

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        try:
            import pandas as pd
            import numpy as np
        except ImportError:
            logger.warning('pandas/numpy unavailable — CSV engine disabled')
            return

        if not _CSV_PATH.exists():
            logger.warning('Listings CSV not found at %s — CSV engine disabled', _CSV_PATH)
            return

        try:
            df = pd.read_csv(_CSV_PATH, low_memory=False)
        except Exception as exc:
            logger.warning('Failed to load listings CSV: %s', exc)
            return

        # Coerce numeric columns
        for col in ('price_tnd', 'surface_m2', 'price_per_m2'):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Normalize text columns
        for col in ('property_type', 'governorate', 'city', 'transaction_type'):
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str).str.strip()

        # Remove outliers: ppm2 must be between 100 and 25 000 TND
        if 'price_per_m2' in df.columns:
            df = df[(df['price_per_m2'] >= 100) & (df['price_per_m2'] <= 25_000)].copy()

        # Compute ppm2 from price+area when missing
        if 'price_per_m2' not in df.columns and {'price_tnd', 'surface_m2'}.issubset(df.columns):
            df['price_per_m2'] = df['price_tnd'] / df['surface_m2'].replace({0: np.nan})

        # Normalize property type to lowercase CSV canonical names
        df['ptype_norm'] = df['property_type'].str.lower().map(
            lambda x: _TYPE_MAP.get(x, x)
        )
        df['gov_norm']  = df['governorate'].map(_norm)
        df['city_norm'] = df['city'].map(_norm) if 'city' in df.columns else ''
        df['tx_norm']   = df['transaction_type'].str.lower().str.strip().map(
            lambda x: 'rent' if 'rent' in x else 'sale'
        )

        # Build lookup tables
        for (cn, gn, pt, tx), grp in df.groupby(
            ['city_norm', 'gov_norm', 'ptype_norm', 'tx_norm'], observed=True
        ):
            vals = grp['price_per_m2'].dropna()
            if len(vals) >= 3:
                self._city_gov_ppm2[(cn, gn, pt, tx)] = float(vals.median())

        for (gn, pt, tx), grp in df.groupby(
            ['gov_norm', 'ptype_norm', 'tx_norm'], observed=True
        ):
            vals = grp['price_per_m2'].dropna()
            if len(vals) >= 5:
                self._gov_ppm2[(gn, pt, tx)] = float(vals.median())

        for (pt, tx), grp in df.groupby(['ptype_norm', 'tx_norm'], observed=True):
            vals = grp['price_per_m2'].dropna()
            if len(vals) >= 10:
                self._global_ppm2[(pt, tx)] = float(vals.median())

        self._df = df
        logger.info(
            'CSV engine ready: %d rows | %d city priors | %d gov priors',
            len(df), len(self._city_gov_ppm2), len(self._gov_ppm2),
        )

    def get_ppm2(
        self,
        city: str,
        governorate: str,
        property_type: str,
        transaction_type: str,
    ) -> Optional[float]:
        """Return data-driven median price/m² or None if unavailable."""
        self._load()
        ptype = _TYPE_MAP.get(property_type.lower().strip())
        if ptype is None:
            return None  # Commercial: no CSV data
        tx    = 'rent' if transaction_type.lower().strip() == 'rent' else 'sale'
        cn    = _norm(city)
        gn    = _norm(governorate)

        val = self._city_gov_ppm2.get((cn, gn, ptype, tx))
        if val:
            return val
        val = self._gov_ppm2.get((gn, ptype, tx))
        if val:
            return val
        return self._global_ppm2.get((ptype, tx))

    def find_comparables(self, ref: dict, limit: int = 4) -> list:
        """Return comparable listings from the CSV dataset."""
        self._load()
        if self._df is None or self._df.empty:
            return []

        ptype    = _TYPE_MAP.get(ref.get('property_type', 'apartment').lower().strip(), 'appartement')
        gov_norm = _norm(ref.get('governorate', ''))
        city_ref = _norm(ref.get('delegation') or ref.get('city') or '')
        size_m2  = float(ref.get('size_m2') or 100)
        tx       = 'rent' if (ref.get('transaction_type') or 'sale').lower() == 'rent' else 'sale'

        df = self._df
        mask = (df['ptype_norm'] == ptype) & (df['tx_norm'] == tx)
        if gov_norm:
            mask &= df['gov_norm'] == gov_norm
        subset = df[mask].copy()

        # Size window ±60%
        subset = subset[
            subset['surface_m2'].between(size_m2 * 0.40, size_m2 * 1.60)
        ]
        subset = subset[subset['price_tnd'] > 0]

        if subset.empty:
            return []

        def _sim(row) -> int:
            score = 60
            s = float(row.get('surface_m2') or 0)
            if s > 0:
                score -= min(abs(s - size_m2) / max(size_m2, 1) * 25, 20)
            if city_ref and _norm(str(row.get('city', ''))) == city_ref:
                score += 20
            return max(0, min(99, int(score)))

        subset = subset.copy()
        subset['_sim'] = subset.apply(_sim, axis=1)
        subset = subset.sort_values(['_sim', 'price_per_m2'], ascending=[False, True]).head(limit)

        results = []
        for _, row in subset.iterrows():
            price = int(round(float(row.get('price_tnd', 0) or 0)))
            area  = float(row.get('surface_m2', size_m2) or size_m2)
            ppm2  = int(round(price / max(area, 1))) if price > 0 else None
            city_name = str(row.get('city', '') or '').strip()
            gov_name  = str(row.get('governorate', '') or '').strip()
            delta = area - size_m2
            diff  = f"{'Larger' if delta > 0 else 'Smaller'} by {abs(delta):.0f} m²" if abs(delta) > 5 else 'Similar size'
            results.append({
                'title':        f"{city_name}, {gov_name}" if city_name else (gov_name or 'Comparable listing'),
                'price':        price,
                'price_per_m2': ppm2,
                'size_m2':      round(area, 1),
                'bedrooms':     int(row.get('bedrooms') or 0) or None,
                'bathrooms':    int(row.get('bathrooms') or 0) or None,
                'governorate':  gov_name,
                'city':         city_name,
                'condition':    None,
                'source':       'market_data',
                'similarity':   int(row.get('_sim', 50)),
                'difference':   diff,
            })
        return results


# ── Module-level singleton ─────────────────────────────────────────────────────
_engine = _CSVEngine()


def get_ppm2(city: str, governorate: str, property_type: str, transaction_type: str) -> Optional[float]:
    """Return data-driven median price/m² from actual listings data."""
    return _engine.get_ppm2(city, governorate, property_type, transaction_type)


def find_comparables(ref: dict, limit: int = 4) -> list:
    """Return comparable listings from the market dataset."""
    return _engine.find_comparables(ref, limit)
