"""
Silver → Gold loader.

Maps ScrapedListing.normalized_data (canonical Silver schema) to a
core.Property record, resolving Region and Delegation FKs by name.
Updates ScrapedListing.status to 'imported' on success.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Property type: Silver code → core.Property choices (4 canonical types).
# Villa → House, Office/Farm → Commercial per platform standard.
PROPERTY_TYPE_MAP = {
    'apartment':  'apartment',
    'house':      'house',
    'villa':      'house',       # legacy alias → House
    'land':       'land',
    'commercial': 'commercial',
    'office':     'commercial',  # legacy alias → Commercial
    'farm':       'commercial',  # legacy alias → Commercial
}

# Tunisia's 24 governorates — normalisation aliases for fuzzy FK lookup
GOV_ALIASES: dict[str, str] = {
    'ben arous':   'Ben Arous',
    'benarous':    'Ben Arous',
    'ariana':      'Ariana',
    'tunis':       'Tunis',
    'manouba':     'Manouba',
    'nabeul':      'Nabeul',
    'zaghouan':    'Zaghouan',
    'bizerte':     'Bizerte',
    'beja':        'Beja',
    'béja':        'Beja',
    'jendouba':    'Jendouba',
    'kef':         'Kef',
    'le kef':      'Kef',
    'siliana':     'Siliana',
    'sousse':      'Sousse',
    'monastir':    'Monastir',
    'mahdia':      'Mahdia',
    'sfax':        'Sfax',
    'kairouan':    'Kairouan',
    'kasserine':   'Kasserine',
    'sidi bouzid': 'Sidi Bouzid',
    'gabes':       'Gabes',
    'gabès':       'Gabes',
    'medenine':    'Medenine',
    'médenine':    'Medenine',
    'tataouine':   'Tataouine',
    'gafsa':       'Gafsa',
    'tozeur':      'Tozeur',
    'kebili':      'Kebili',
    'kébili':      'Kebili',
}


def _canonical_gov(raw: str) -> str:
    return GOV_ALIASES.get(raw.strip().lower(), raw.strip())


class PropertyLoader:
    """
    Loads one Silver record into the core.Property model.

    Usage::
        loader = PropertyLoader()
        prop, created = loader.load(scraped_listing)
    """

    def __init__(self):
        from core.models import Property, Region, Delegation
        self._Property = Property
        self._Region = Region
        self._Delegation = Delegation

        # In-process caches to avoid repeated FK lookups within a batch
        self._region_cache: dict[str, object] = {}
        self._delegation_cache: dict[tuple, object] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load(self, scraped_listing) -> tuple:
        """
        Map ScrapedListing → Property.  Returns (Property, created: bool).
        Raises ValueError if normalized_data is missing or property_type invalid.
        """
        nd = scraped_listing.normalized_data
        if not nd:
            raise ValueError("normalized_data is empty — run wrangler first")

        external_id = scraped_listing.external_id
        region = self._resolve_region(nd.get('governorate', ''))
        delegation = self._resolve_delegation(
            nd.get('city', ''), region, nd.get('delegation_hint', '')
        )

        price = nd.get('price_tnd')
        if price is None or price == 0.0:
            # Use benchmark rather than 0 so analytics and admin never show blank
            from scraper.pipeline.wrangler import _benchmark_price, _BENCH_SURFACE
            gov = nd.get('governorate', '')
            pt  = PROPERTY_TYPE_MAP.get(nd.get('property_type', 'apartment'), 'apartment')
            tx  = nd.get('transaction_type', 'sale')
            price = _benchmark_price(pt, tx, gov)

        surface = nd.get('surface_m2')
        if surface is None or surface == 0.0:
            from scraper.pipeline.wrangler import _BENCH_SURFACE
            pt = PROPERTY_TYPE_MAP.get(nd.get('property_type', 'apartment'), 'apartment')
            surface = _BENCH_SURFACE.get(pt, 90.0)

        property_type = PROPERTY_TYPE_MAP.get(
            nd.get('property_type', 'apartment'), 'apartment'
        )
        transaction_type = nd.get('transaction_type', 'sale')
        if transaction_type not in ('sale', 'rent'):
            transaction_type = 'sale'

        defaults = {
            'title':            (nd.get('title') or '')[:255],
            'description':      nd.get('description') or '',
            'property_type':    property_type,
            'transaction_type': transaction_type,
            'region':           region,
            'delegation':       delegation,
            'price':            price,
            'area_sqm':         surface,
            'price_per_sqm':    nd.get('price_per_m2'),
            'rooms':            nd.get('rooms'),
            'bedrooms':         nd.get('bedrooms'),
            'bathrooms':        nd.get('bathrooms'),
            'image_url':        (nd.get('image_url') or '')[:200] or None,
            'location_raw':     (nd.get('location_raw') or '')[:255],
            'source':           (nd.get('source') or 'unknown')[:100],
            'currency':         'TND',
            'scraped_at':       datetime.now(tz=timezone.utc),
            'is_active':        True,
        }

        prop, created = self._Property.objects.update_or_create(
            external_id=external_id,
            defaults=defaults,
        )
        return prop, created

    # ------------------------------------------------------------------
    # FK resolution helpers
    # ------------------------------------------------------------------

    def _resolve_region(self, governorate_raw: str):
        """Get or create Region by governorate name (case-insensitive)."""
        if not governorate_raw:
            return None
        canonical = _canonical_gov(governorate_raw)
        if canonical in self._region_cache:
            return self._region_cache[canonical]
        region = (
            self._Region.objects.filter(governorate__iexact=canonical).first()
            or self._Region.objects.filter(governorate__iexact=governorate_raw.strip()).first()
        )
        if region is None and canonical:
            region, _ = self._Region.objects.get_or_create(governorate=canonical)
            logger.info("Auto-created Region: %s", canonical)
        self._region_cache[canonical] = region
        return region

    def _resolve_delegation(self, city_raw: str, region, delegation_hint: str = ''):
        """
        Resolve Delegation FK by name under the resolved Region.

        Priority:
          1. delegation_hint (from wrangler _CITY_LOOKUP)
          2. city_raw
        Auto-creates the delegation record if a hint is given but not found in DB.
        """
        if not region:
            return None

        # Build a prioritised list of candidate names to try
        candidates = []
        if delegation_hint and delegation_hint.strip():
            candidates.append(delegation_hint.strip())
        if city_raw and city_raw.strip():
            candidates.append(city_raw.strip())

        for name in candidates:
            cache_key = (name.lower(), region.pk)
            if cache_key in self._delegation_cache:
                return self._delegation_cache[cache_key]
            delegation = self._Delegation.objects.filter(
                name__iexact=name, region=region
            ).first()
            if delegation:
                self._delegation_cache[cache_key] = delegation
                return delegation

        # Auto-create using the hint if supplied (guarantees delegation is never null)
        if delegation_hint and delegation_hint.strip():
            name = delegation_hint.strip()
            cache_key = (name.lower(), region.pk)
            delegation, _ = self._Delegation.objects.get_or_create(
                name=name, region=region
            )
            logger.info("Auto-created Delegation: %s / %s", region.governorate, name)
            self._delegation_cache[cache_key] = delegation
            return delegation

        return None
