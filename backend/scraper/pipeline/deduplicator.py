"""
Deduplicator — prevents the same listing from being stored or imported twice.

Strategy (in order of precedence):
1. external_id match   — exact SHA-1 key collision → definite duplicate
2. source_url match    — same listing URL, different scrape run → duplicate
3. Fuzzy triple match  — same (price, surface, governorate) within tolerances
   (used only when external_id and url checks both miss)
"""

import logging

logger = logging.getLogger(__name__)


class Deduplicator:
    """
    Checks whether a scraped listing is a duplicate of an already-stored one.
    All lookups are against the scraper_ScrapedListing table only; the Gold
    (core_property) table is NOT queried here — that is the loader's job.
    """

    def __init__(self):
        # Lazy import to avoid model import at module load time
        from scraper.models import ScrapedListing
        self._model = ScrapedListing

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def find_duplicate(self, external_id: str, source_url: str, normalized: dict | None = None):
        """
        Return an existing ScrapedListing if this record is a duplicate,
        else return None.

        Parameters
        ----------
        external_id   : SHA-1 key for this record
        source_url    : listing page URL
        normalized    : Silver-layer dict (used for fuzzy check fallback)
        """
        # 1. Exact external_id match
        existing = self._by_external_id(external_id)
        if existing:
            logger.debug("Duplicate by external_id: %s", external_id[:10])
            return existing

        # 2. Same URL
        existing = self._by_url(source_url)
        if existing:
            logger.debug("Duplicate by URL: %s", source_url[:80])
            return existing

        # 3. Fuzzy match (only when Silver data is available)
        if normalized:
            existing = self._fuzzy(normalized)
            if existing:
                logger.debug("Duplicate by fuzzy match: %s", source_url[:80])
                return existing

        return None

    def is_duplicate(self, external_id: str, source_url: str, normalized: dict | None = None) -> bool:
        return self.find_duplicate(external_id, source_url, normalized) is not None

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _by_external_id(self, external_id: str):
        return self._model.objects.filter(external_id=external_id).first()

    def _by_url(self, url: str):
        if not url:
            return None
        return self._model.objects.filter(source_url=url).first()

    def _fuzzy(self, norm: dict):
        """
        Fuzzy triple: price within 2%, surface within 5 m², same governorate.
        Only fires when price and surface are both present.
        """
        price = norm.get('price_tnd')
        surface = norm.get('surface_m2')
        governorate = (norm.get('governorate') or '').strip().lower()

        if not price or not surface or not governorate:
            return None

        price_lo = price * 0.98
        price_hi = price * 1.02
        surf_lo = surface - 5
        surf_hi = surface + 5

        qs = self._model.objects.filter(
            normalized_data__isnull=False,
        )
        for listing in qs.iterator(chunk_size=500):
            nd = listing.normalized_data or {}
            p = nd.get('price_tnd')
            s = nd.get('surface_m2')
            g = (nd.get('governorate') or '').strip().lower()
            if (
                p is not None
                and s is not None
                and price_lo <= p <= price_hi
                and surf_lo <= s <= surf_hi
                and g == governorate
            ):
                return listing
        return None
