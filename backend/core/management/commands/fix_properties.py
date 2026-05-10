"""
fix_properties — one-shot data-quality command for EstateMind.

Actions (all run inside a single transaction):
  1. Delete category/search-result pages ("N annonces à Ville").
  2. Merge duplicate region records (Beja/Béja, Gabes/Gabès, etc.).
  3. Retroactively fix region, delegation, and English title for every property.
  4. Canonicalize property types -> Apartment | House | Commercial | Land.
  5. Normalize source display names.
  6. Impute price=0 / area_sqm=0 using per-region+type DB medians,
     falling back to Tunisia national benchmarks.
  7. Impute missing bedrooms/bathrooms from type medians.
  8. Recompute price_per_sqm for all records.

Usage:
    python manage.py fix_properties
    python manage.py fix_properties --dry-run
"""

import logging
import re
from statistics import median

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

_CATEGORY_RE = re.compile(r'^\d[\d\s]*\s+annonces?\s+(à|a)\b', re.IGNORECASE)

# Canonical type mapping
_TYPE_MAP = {
    'villa': 'house', 'office': 'commercial', 'farm': 'commercial',
}

# Source display-name normalisation
_SOURCE_DISPLAY = {
    'tunisie_annonce':  'Tunisie Annonce',
    'tunisieannonce':   'Tunisie Annonce',
    'mubawab':          'Mubawab',
    'tecnocasa':        'TecnoCasa',
    'tayara':           'Tayara',
    'direct owner':     'Direct Owner',
    'local agency':     'Local Agency',
}

# Region name consolidation: alias -> canonical name in DB
_REGION_MERGE = {
    'Béja':       'Beja',
    'Gabès':      'Gabes',
    'Kébili':     'Kebili',
    'Médenine':   'Medenine',
    'Le Kef':     'Kef',
    'La Manouba': 'Manouba',
}

# Governorate economic tier (1=highest prices, 5=lowest)
_GOV_TIER = {
    'Tunis': 1, 'Ariana': 1, 'Ben Arous': 1,
    'Nabeul': 2, 'Sousse': 2, 'Monastir': 2, 'Sfax': 2, 'Bizerte': 2, 'Manouba': 2,
    'Mahdia': 3, 'Zaghouan': 3, 'Kairouan': 3,
    'Beja': 4, 'Jendouba': 4, 'Kef': 4, 'Siliana': 4,
    'Kasserine': 5, 'Sidi Bouzid': 5, 'Gabes': 5, 'Medenine': 5,
    'Tataouine': 5, 'Gafsa': 5, 'Tozeur': 5, 'Kebili': 5,
}

_BENCH_PRICE_SALE = {
    (1, 'apartment'): 370_000, (2, 'apartment'): 245_000, (3, 'apartment'): 155_000,
    (4, 'apartment'): 105_000, (5, 'apartment'):  75_000,
    (1, 'house'):     680_000, (2, 'house'):     470_000, (3, 'house'):     295_000,
    (4, 'house'):     190_000, (5, 'house'):     135_000,
    (1, 'commercial'):260_000, (2, 'commercial'):175_000, (3, 'commercial'):110_000,
    (4, 'commercial'): 78_000, (5, 'commercial'): 55_000,
    (1, 'land'):      200_000, (2, 'land'):      125_000, (3, 'land'):       72_000,
    (4, 'land'):       46_000, (5, 'land'):       28_000,
}
_BENCH_PRICE_RENT = {
    (1, 'apartment'): 1_450, (2, 'apartment'): 980, (3, 'apartment'): 620,
    (4, 'apartment'):   430, (5, 'apartment'): 310,
    (1, 'house'):      2_300, (2, 'house'):   1_550, (3, 'house'):     960,
    (4, 'house'):        680, (5, 'house'):     460,
    (1, 'commercial'): 2_100, (2, 'commercial'):1_350, (3, 'commercial'):820,
    (4, 'commercial'):   560, (5, 'commercial'): 370,
    (1, 'land'):         620, (2, 'land'):      380, (3, 'land'):       230,
    (4, 'land'):         160, (5, 'land'):       100,
}
_BENCH_SURFACE  = {'apartment': 90.0, 'house': 185.0, 'commercial': 115.0, 'land': 350.0}
_BENCH_BEDROOMS = {'apartment': 2, 'house': 3, 'commercial': 0, 'land': 0}


def _bench_price(pt, tx, gov):
    tier  = _GOV_TIER.get(gov, 3)
    table = _BENCH_PRICE_RENT if tx == 'rent' else _BENCH_PRICE_SALE
    return table.get((tier, pt), table.get((3, pt), 150_000))


# ── Detect titles that still need translation ────────────────────────────────
# English titles produced by _build_english_title always start with one of these.
_EN_TYPE_PREFIXES = ('Apartment ', 'House ', 'Land Plot ', 'Commercial Space ', 'Property ')

# French-language markers (checked on accent-stripped / lowercased text)
_FRENCH_TRIGGER = re.compile(
    r'\b(annonce|appartement|appart|maison|villa|terrain|vente|location|louer|vendre|'
    r'chambre|salle|etage|bain|cuisine|salon|duplex|triplex|bureau|ferme|residence|'
    r'haut standing|au bord|centre ?ville|neuf|moderne|renove|meuble|lumineux|'
    r'spacieux|luxueux|occasion|opportunite|pieces?)\b',
    re.IGNORECASE,
)


def _needs_translation(title: str) -> bool:
    """Return True if the title is not already in canonical English format."""
    import unicodedata
    # Already canonicalised
    if any(title.startswith(p) for p in _EN_TYPE_PREFIXES):
        return False
    # Strip accents and check for French vocabulary
    stripped = ''.join(
        c for c in unicodedata.normalize('NFD', title)
        if unicodedata.category(c) != 'Mn'
    )
    return bool(_FRENCH_TRIGGER.search(stripped))


def _extract_title_location(title: str) -> str:
    """
    Extract the location clause from a title.
    Handles both French (' à ') and English (' at ') patterns.
    Returns the location string after the separator, or '' if not found.
    """
    from scraper.pipeline.wrangler import _n
    norm = _n(title)

    # English canonical form: "Type ... at Location, Governorate"
    if ' at ' in norm:
        idx = norm.rfind(' at ')
        return title[idx + 4:].strip()

    # French: "... à Location"
    if ' a ' in norm:
        idx = norm.rfind(' a ')
        return title[idx + 3:].strip()

    # Dash separator: "desc - Location"
    if ' - ' in title:
        parts = title.rsplit(' - ', 1)
        return parts[-1].strip()

    return ''


class Command(BaseCommand):
    help = 'Clean, canonicalize, and retroactively fix all Property records.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be written.\n'))

        from core.models import Property, Region, Delegation
        from scraper.pipeline.wrangler import (
            _lookup_city, _DEFAULT_DELEGATION, _build_english_title,
            _n, _infer_governorate,
        )

        stats = {
            'deleted_category':   0,
            'region_merged':      0,
            'region_fixed':       0,
            'delegation_fixed':   0,
            'title_translated':   0,
            'type_fixed':         0,
            'source_fixed':       0,
            'price_imputed':      0,
            'surface_imputed':    0,
            'bedrooms_imputed':   0,
            'bathrooms_imputed':  0,
            'ppm2_recalculated':  0,
        }

        # Region cache: governorate name -> Region ORM object
        _region_cache: dict[str, object] = {}
        _deleg_cache:  dict[tuple, object] = {}

        def _get_or_create_region(gov_name: str):
            if gov_name in _region_cache:
                return _region_cache[gov_name]
            obj, _ = Region.objects.get_or_create(governorate=gov_name)
            _region_cache[gov_name] = obj
            return obj

        def _get_or_create_delegation(deleg_name: str, region):
            key = (deleg_name.lower(), region.pk)
            if key in _deleg_cache:
                return _deleg_cache[key]
            obj = Delegation.objects.filter(
                name__iexact=deleg_name, region=region
            ).first()
            if not obj:
                obj, _ = Delegation.objects.get_or_create(name=deleg_name, region=region)
            _deleg_cache[key] = obj
            return obj

        with transaction.atomic():
            # ── 1. Delete category/search-result pages ────────────────────────
            all_props = list(Property.objects.select_related('region', 'delegation').all())
            ids_to_delete = [
                p.pk for p in all_props
                if _CATEGORY_RE.match(p.title or '')
            ]
            stats['deleted_category'] = len(ids_to_delete)
            self.stdout.write(f'Category pages to delete: {len(ids_to_delete)}')
            if not dry and ids_to_delete:
                Property.objects.filter(pk__in=ids_to_delete).delete()
                all_props = [p for p in all_props if p.pk not in set(ids_to_delete)]

            # ── 2. Merge duplicate regions ────────────────────────────────────
            for alias, canonical_name in _REGION_MERGE.items():
                try:
                    alias_region = Region.objects.filter(governorate=alias).first()
                    if not alias_region:
                        continue
                    canonical_region = (
                        Region.objects.filter(governorate=canonical_name).first()
                        or Region.objects.filter(governorate__iexact=canonical_name).first()
                    )
                    if not canonical_region:
                        self.stdout.write(f'Renaming region "{alias}" -> "{canonical_name}"')
                        if not dry:
                            alias_region.governorate = canonical_name
                            alias_region.save()
                        continue
                    count = Property.objects.filter(region=alias_region).count()
                    self.stdout.write(
                        f'Merging region "{alias}" -> "{canonical_name}" ({count} properties)'
                    )
                    stats['region_merged'] += count
                    if not dry:
                        Property.objects.filter(region=alias_region).update(region=canonical_region)
                        Delegation.objects.filter(region=alias_region).update(region=canonical_region)
                        alias_region.delete()
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f'Region merge failed for {alias}: {exc}'))

            # Reload after region merge
            if not dry:
                all_props = list(Property.objects.select_related('region', 'delegation').all())

            # ── 3. Retroactively fix region, delegation, and title ────────────
            retro_update = []
            for p in all_props:
                changed = False
                title = p.title or ''

                # Determine location candidate(s) from title
                loc_from_title = _extract_title_location(title)

                gov_result  = None
                deleg_hint  = None

                # Priority: title-derived location > full title scan > location_raw
                # (location_raw is often a broad city name set by the scraper,
                #  while the title location is more specific and reliable)
                for candidate in [loc_from_title, title]:
                    if candidate:
                        r = _lookup_city(candidate)
                        if r:
                            gov_result, deleg_hint = r
                            break

                # Fallback: text-scan (title, then location_raw as last resort)
                if not gov_result:
                    gov_result = (_infer_governorate(loc_from_title)
                                  or _infer_governorate(title)
                                  or _infer_governorate(p.location_raw or ''))

                # Use existing governorate if lookup gave nothing new
                current_gov = p.region.governorate if p.region else ''
                target_gov  = gov_result or current_gov

                if not target_gov:
                    # Cannot determine governorate — leave unchanged
                    pass
                else:
                    # Fix region FK if it differs
                    if not dry:
                        new_region = _get_or_create_region(target_gov)
                    else:
                        new_region = Region.objects.filter(governorate=target_gov).first()

                    if new_region and (not p.region or p.region.governorate != target_gov):
                        p.region = new_region
                        stats['region_fixed'] += 1
                        changed = True

                    # Fix delegation FK
                    if not deleg_hint:
                        deleg_hint = _DEFAULT_DELEGATION.get(target_gov)
                    if deleg_hint and new_region:
                        current_deleg_name = p.delegation.name if p.delegation else ''
                        if current_deleg_name.lower() != deleg_hint.lower():
                            if not dry:
                                new_deleg = _get_or_create_delegation(deleg_hint, new_region)
                            else:
                                new_deleg = Delegation.objects.filter(
                                    name__iexact=deleg_hint, region=new_region
                                ).first()
                            if new_deleg and p.delegation != new_deleg:
                                p.delegation = new_deleg
                                stats['delegation_fixed'] += 1
                                changed = True
                    elif not p.delegation and new_region:
                        # Assign default delegation even if no specific hint
                        default_name = _DEFAULT_DELEGATION.get(target_gov)
                        if default_name:
                            if not dry:
                                new_deleg = _get_or_create_delegation(default_name, new_region)
                            else:
                                new_deleg = Delegation.objects.filter(
                                    name__iexact=default_name, region=new_region
                                ).first()
                            if new_deleg:
                                p.delegation = new_deleg
                                stats['delegation_fixed'] += 1
                                changed = True

                # Translate French title to English
                if _needs_translation(title) and target_gov:
                    new_title = _build_english_title(
                        title, p.property_type, target_gov, loc_from_title
                    )
                    if new_title and new_title != title:
                        p.title = new_title[:255]
                        stats['title_translated'] += 1
                        changed = True

                if changed:
                    retro_update.append(p)

            self.stdout.write(
                f'Retroactive fixes — region: {stats["region_fixed"]}, '
                f'delegation: {stats["delegation_fixed"]}, '
                f'title: {stats["title_translated"]}'
            )
            if not dry and retro_update:
                retro_fields = ['title', 'region', 'delegation']
                for i in range(0, len(retro_update), 500):
                    batch = retro_update[i:i + 500]
                    Property.objects.bulk_update(batch, retro_fields)

            # Reload with fresh FKs
            if not dry:
                all_props = list(Property.objects.select_related('region', 'delegation').all())

            # ── 4. Build DB median lookup for imputation ──────────────────────
            price_groups: dict[tuple, list] = {}
            area_groups:  dict[tuple, list] = {}
            for p in all_props:
                gov = p.region.governorate if p.region else ''
                key = (gov, p.property_type, p.transaction_type)
                if p.price and p.price > 0:
                    price_groups.setdefault(key, []).append(p.price)
                if p.area_sqm and p.area_sqm > 0:
                    area_groups.setdefault(key, []).append(p.area_sqm)

            def _db_median_price(gov, pt, tx):
                key = (gov, pt, tx)
                vals = price_groups.get(key, [])
                if vals:
                    return median(vals)
                nat = [v for (g, p2, t2), vlist in price_groups.items()
                       if p2 == pt and t2 == tx for v in vlist]
                if nat:
                    return median(nat)
                return _bench_price(pt, tx, gov)

            def _db_median_area(gov, pt, tx):
                key = (gov, pt, tx)
                vals = area_groups.get(key, [])
                if vals:
                    return median(vals)
                nat = [v for (g, p2, t2), vlist in area_groups.items()
                       if p2 == pt for v in vlist]
                if nat:
                    return median(nat)
                return _BENCH_SURFACE.get(pt, 90.0)

            # ── 5. Fix type / source / imputation / ppm2 ─────────────────────
            to_update = []
            for p in all_props:
                changed = False
                gov = p.region.governorate if p.region else ''

                # Canonicalize property type
                new_type = _TYPE_MAP.get(p.property_type, p.property_type)
                if new_type not in ('apartment', 'house', 'commercial', 'land'):
                    new_type = 'apartment'
                if new_type != p.property_type:
                    p.property_type = new_type
                    stats['type_fixed'] += 1
                    changed = True

                # Normalize source name
                new_source = _SOURCE_DISPLAY.get(
                    (p.source or '').strip().lower(), p.source or ''
                )
                if new_source and new_source != p.source:
                    p.source = new_source[:100]
                    stats['source_fixed'] += 1
                    changed = True

                pt = p.property_type
                tx = p.transaction_type or 'sale'

                # Impute price
                if not p.price or p.price == 0.0:
                    p.price = _db_median_price(gov, pt, tx)
                    stats['price_imputed'] += 1
                    changed = True

                # Impute area
                if not p.area_sqm or p.area_sqm == 0.0:
                    p.area_sqm = _db_median_area(gov, pt, tx)
                    stats['surface_imputed'] += 1
                    changed = True

                # Impute bedrooms
                if p.bedrooms is None and pt in ('apartment', 'house'):
                    p.bedrooms = _BENCH_BEDROOMS.get(pt, 2)
                    stats['bedrooms_imputed'] += 1
                    changed = True

                # Impute bathrooms
                if p.bathrooms is None and pt in ('apartment', 'house'):
                    p.bathrooms = max(1, (p.bedrooms or 2) // 2)
                    stats['bathrooms_imputed'] += 1
                    changed = True

                # Recompute price_per_sqm
                if p.price and p.area_sqm and p.area_sqm > 0:
                    new_ppm2 = round(p.price / p.area_sqm, 2)
                    if new_ppm2 != p.price_per_sqm:
                        p.price_per_sqm = new_ppm2
                        stats['ppm2_recalculated'] += 1
                        changed = True

                if changed:
                    to_update.append(p)

            self.stdout.write(f'Properties to update (type/source/impute): {len(to_update)}')
            if not dry and to_update:
                fields = ['property_type', 'source', 'price', 'area_sqm',
                          'price_per_sqm', 'bedrooms', 'bathrooms']
                for i in range(0, len(to_update), 500):
                    batch = to_update[i:i + 500]
                    Property.objects.bulk_update(batch, fields)

            if dry:
                transaction.set_rollback(True)

        # ── Report ────────────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== fix_properties results ==='))
        for k, v in stats.items():
            self.stdout.write(f'  {k:<25} {v}')
        if dry:
            self.stdout.write(self.style.WARNING('\n(dry run — no changes committed)'))
        else:
            self.stdout.write(self.style.SUCCESS('\nDone. All changes committed.'))
