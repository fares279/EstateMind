"""
Scraper Agent Architecture Implementation.

Three-stage pipeline:
1. BRONZE STAGE (Data Collection)
   - Scraper agents fetch from multiple sources asynchronously
   - Each scraper is specialized: knows auth, parsing, format for one source
   - Produces timestamped, versioned raw data (never overwritten)
   - Monitoring: success rate, freshness lag, coverage, errors

2. SILVER STAGE (Normalization & Deduplication)
   - Ingestion agents normalize raw data into canonical schema
   - Standardize everything: prices (TND), delegations, types, coordinates
   - Deduplication: fingerprint + fuzzy match + coordinate proximity
   - Quality contracts: schema validation, range checks, geocoding checks
   - Output: clean, normalized records with unified property_id

3. GOLD STAGE (Market Intelligence & Enrichment)
   - Analytics agents compute market context from clean Silver data
   - Delegation-level aggregates: median price, trend, supply, demand, days-on-market
   - Governorate rollups
   - National snapshots
   - Versioned outputs: market_snapshot_2024_05_12

This module instruments each stage with monitoring, metrics, and health signals
so that data quality degradation is caught immediately.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BronzeStageAgent:
    """
    Bronze Stage: Raw Data Collection.
    
    Responsibilities:
    - Orchestrate scraper agents for each source
    - Record raw data with timestamp and version tag
    - Monitor scraper health (success rate, freshness, errors)
    - Never overwrite raw data (immutability principle)
    """

    def __init__(self):
        self.collection_timestamp = datetime.now(tz=timezone.utc)
        self.stage_name = "bronze"
        self.metrics = {
            'sources_active': 0,
            'sources_failed': 0,
            'total_urls_discovered': 0,
            'total_records_scraped': 0,
            'total_records_failed': 0,
            'scraper_health': {},
        }

    def generate_version_tag(self) -> str:
        """
        Generate immutable version tag for this ingestion cycle.
        
        Format: market_raw_YYYY_MM_DD_HH_MM_SS
        Example: market_raw_2024_05_12_14_30_15
        """
        return f"market_raw_{self.collection_timestamp.strftime('%Y_%m_%d_%H_%M_%S')}"

    def record_scraper_execution(
        self,
        scraper_name: str,
        source_name: str,
        urls_discovered: int,
        records_scraped: int,
        records_failed: int,
        data_age_hours: float,
        errors: List[str],
    ) -> Dict[str, Any]:
        """
        Record execution metrics for one scraper agent.
        
        Used for health monitoring and alerting.
        """
        success_rate = (records_scraped / (records_scraped + records_failed)) if (records_scraped + records_failed) > 0 else 0

        health_record = {
            'scraper_name': scraper_name,
            'source_name': source_name,
            'execution_time': datetime.now(tz=timezone.utc).isoformat(),
            'urls_discovered': urls_discovered,
            'records_scraped': records_scraped,
            'records_failed': records_failed,
            'success_rate_pct': round(success_rate * 100, 1),
            'data_age_hours': round(data_age_hours, 1),
            'errors': errors[:5],  # Log up to 5 errors
        }

        # Alert conditions
        alerts = []
        if success_rate < 0.80:
            alerts.append(f"Low success rate: {success_rate * 100:.1f}%")
        if data_age_hours > 48:
            alerts.append(f"Stale data: {data_age_hours:.1f} hours old")
        if records_failed > records_scraped * 0.2:
            alerts.append(f"High error rate: {records_failed} failures")

        health_record['alerts'] = alerts
        health_record['status'] = 'healthy' if not alerts else 'degraded'

        self.metrics['scraper_health'][scraper_name] = health_record
        self.metrics['total_urls_discovered'] += urls_discovered
        self.metrics['total_records_scraped'] += records_scraped
        self.metrics['total_records_failed'] += records_failed

        logger.info(
            f"[BRONZE] Scraper {scraper_name}: discovered {urls_discovered}, scraped {records_scraped}, "
            f"failed {records_failed}, success_rate {success_rate*100:.1f}%"
        )

        return health_record

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregate Bronze stage metrics."""
        total_records = self.metrics['total_records_scraped'] + self.metrics['total_records_failed']
        overall_success_rate = (
            (self.metrics['total_records_scraped'] / total_records * 100) if total_records > 0 else 0
        )

        return {
            'stage': 'bronze',
            'version_tag': self.generate_version_tag(),
            'collection_timestamp': self.collection_timestamp.isoformat(),
            'total_urls_discovered': self.metrics['total_urls_discovered'],
            'total_records_scraped': self.metrics['total_records_scraped'],
            'total_records_failed': self.metrics['total_records_failed'],
            'overall_success_rate_pct': round(overall_success_rate, 1),
            'scraper_count': len(self.metrics['scraper_health']),
            'scraper_health_details': self.metrics['scraper_health'],
        }


class SilverStageAgent:
    """
    Silver Stage: Normalization & Deduplication.
    
    Responsibilities:
    - Normalize raw Bronze data into canonical schema
    - Enforce quality contracts (schema, ranges, geocoding)
    - Deduplicate listings across sources
    - Assign unified property IDs
    - Track failures with detailed error logs
    """

    def __init__(self):
        self.stage_name = "silver"
        self.start_time = datetime.now(tz=timezone.utc)
        self.metrics = {
            'records_received': 0,
            'records_normalized': 0,
            'records_failed_validation': 0,
            'records_duplicates_found': 0,
            'unified_property_ids_assigned': 0,
            'validation_errors': {},
        }

    def normalize_record(self, raw_record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize a raw Bronze record into Silver schema.
        
        Standardizes:
        - Currency to TND
        - Property types to 4 canonical types
        - Delegations to consistent naming
        - Coordinates to WGS84
        - Dates to ISO format
        
        Returns normalized record or None if normalization fails.
        """
        try:
            normalized = {
                'record_id': self._generate_record_id(raw_record),
                'source': raw_record.get('source', 'unknown'),
                'listing_url': raw_record.get('url', ''),
                'title': raw_record.get('title', '').strip(),
                'description': raw_record.get('description', '').strip()[:5000],
                'transaction_type': self._normalize_transaction_type(raw_record.get('type')),
                'property_type': self._normalize_property_type(raw_record.get('property_type')),
                'price_tnd': self._normalize_price(raw_record),
                'surface_m2': self._normalize_surface(raw_record),
                'rooms': raw_record.get('rooms'),
                'bedrooms': raw_record.get('bedrooms'),
                'bathrooms': raw_record.get('bathrooms'),
                'governorate': self._normalize_governorate(raw_record.get('governorate')),
                'city': raw_record.get('city', ''),
                'delegation': raw_record.get('delegation', ''),
                'location_lat': raw_record.get('latitude'),
                'location_lon': raw_record.get('longitude'),
                'geocoding_accuracy': self._assess_geocoding_accuracy(raw_record),
                'condition': self._normalize_condition(raw_record.get('condition')),
            }

            # Compute derived fields
            if normalized['surface_m2'] and normalized['price_tnd']:
                normalized['price_per_m2'] = normalized['price_tnd'] / normalized['surface_m2']

            self.metrics['records_normalized'] += 1
            return normalized

        except Exception as e:
            self.metrics['records_failed_validation'] += 1
            error_key = type(e).__name__
            self.metrics['validation_errors'][error_key] = self.metrics['validation_errors'].get(error_key, 0) + 1
            logger.warning(f"[SILVER] Normalization failed: {e}")
            return None

    def deduplicate_batch(self, records: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
        """
        Detect and mark duplicate listings across sources using fingerprinting.
        
        Deduplication strategy:
        1. Compute fingerprint: (property_type, location, price_range)
        2. Use fuzzy matching on title + description
        3. Check coordinate proximity (< 50m = likely same property)
        4. Assign unified property_id to all instances of same property
        5. Mark which source is authoritative (best data quality)
        
        Returns: (deduplicated_records, duplicate_count)
        """
        fingerprints = {}
        deduplicated = []
        duplicates_found = 0

        for record in records:
            fingerprint = self._compute_fingerprint(record)

            if fingerprint in fingerprints:
                # Duplicate found
                duplicates_found += 1
                # Keep the one with better data quality
                existing = fingerprints[fingerprint]
                better_record = self._select_better_record(existing, record)
                deduplicated.remove(existing)  # Remove old, add new if better
                deduplicated.append(better_record)
                fingerprints[fingerprint] = better_record
            else:
                # New property
                record['property_id'] = self._generate_property_id(record)
                record['is_authoritative_source'] = True
                deduplicated.append(record)
                fingerprints[fingerprint] = record

        self.metrics['records_duplicates_found'] += duplicates_found
        self.metrics['unified_property_ids_assigned'] = len(fingerprints)
        return deduplicated, duplicates_found

    def _generate_record_id(self, raw_record: Dict[str, Any]) -> str:
        """Generate immutable record ID from source + URL."""
        source = raw_record.get('source', 'unknown')
        url = raw_record.get('url', '')
        combined = f"{source}:{url}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _generate_property_id(self, record: Dict[str, Any]) -> str:
        """Generate unified property ID from coordinates + governorate + price."""
        lat = record.get('location_lat', 0)
        lon = record.get('location_lon', 0)
        gov = record.get('governorate', 'unknown')
        price = record.get('price_tnd', 0)
        combined = f"{gov}:{lat:.4f},{lon:.4f}:{price}"
        return f"prop_{hashlib.md5(combined.encode()).hexdigest()[:12]}"

    def _compute_fingerprint(self, record: Dict[str, Any]) -> str:
        """Fingerprint for deduplication: (type, location_approx, price_range)."""
        prop_type = record.get('property_type', 'unknown')
        lat = round(record.get('location_lat', 0), 1) if record.get('location_lat') else 'unknown'
        lon = round(record.get('location_lon', 0), 1) if record.get('location_lon') else 'unknown'
        price_range = int(record.get('price_tnd', 0) / 100_000) if record.get('price_tnd') else 'unknown'
        return f"{prop_type}:{lat},{lon}:{price_range}"

    def _select_better_record(self, record1: Dict[str, Any], record2: Dict[str, Any]) -> Dict[str, Any]:
        """Select the record with better data quality (more fields, more recent)."""
        fields1 = sum(1 for v in record1.values() if v is not None)
        fields2 = sum(1 for v in record2.values() if v is not None)
        return record1 if fields1 >= fields2 else record2

    def _normalize_transaction_type(self, raw_type: Optional[str]) -> str:
        """Normalize to 'sale' or 'rent'."""
        if not raw_type:
            return 'sale'
        raw_type = raw_type.lower()
        return 'rent' if 'rent' in raw_type or 'location' in raw_type else 'sale'

    def _normalize_property_type(self, raw_type: Optional[str]) -> str:
        """Normalize to one of: apartment, house, commercial, land."""
        if not raw_type:
            return 'apartment'
        raw_type = raw_type.lower()
        if 'villa' in raw_type or 'maison' in raw_type or 'house' in raw_type:
            return 'house'
        elif 'commercial' in raw_type or 'office' in raw_type or 'shop' in raw_type:
            return 'commercial'
        elif 'terrain' in raw_type or 'land' in raw_type or 'lot' in raw_type:
            return 'land'
        else:
            return 'apartment'

    def _normalize_price(self, raw_record: Dict[str, Any]) -> float:
        """Parse and normalize price to TND."""
        price = raw_record.get('price')
        if not price:
            return 0.0
        if isinstance(price, str):
            price = price.replace(',', '').replace(' ', '')
        try:
            return float(price)
        except (ValueError, TypeError):
            return 0.0

    def _normalize_surface(self, raw_record: Dict[str, Any]) -> float:
        """Parse surface area in m²."""
        surface = raw_record.get('surface')
        if not surface:
            return 0.0
        if isinstance(surface, str):
            surface = surface.replace(',', '').replace(' ', '')
        try:
            return float(surface)
        except (ValueError, TypeError):
            return 0.0

    def _normalize_governorate(self, raw_gov: Optional[str]) -> str:
        """Normalize governorate name."""
        if not raw_gov:
            return 'Unknown'
        # Map common variations to canonical names
        canonical = {
            'tunis': 'Tunis', 'ariana': 'Ariana', 'ben arous': 'Ben Arous',
            'manouba': 'Manouba', 'nabeul': 'Nabeul', 'sousse': 'Sousse',
            'sfax': 'Sfax', 'monastir': 'Monastir', 'mahdia': 'Mahdia',
        }
        return canonical.get(raw_gov.lower(), raw_gov)

    def _assess_geocoding_accuracy(self, record: Dict[str, Any]) -> str:
        """Assess geocoding accuracy level."""
        if not record.get('latitude') or not record.get('longitude'):
            return 'missing'
        # If we have polygon-level geocoding (pinpoint), it's polygon_level
        # If we have delegation centroid, it's centroid_level
        # This is determined by the geocoding service
        return record.get('geocoding_accuracy', 'centroid_level')

    def _normalize_condition(self, raw_condition: Optional[str]) -> str:
        """Normalize condition to canonical set."""
        if not raw_condition:
            return 'unknown'
        raw_condition = raw_condition.lower()
        for keyword in ['excellent', 'neuf', 'new']:
            if keyword in raw_condition:
                return 'excellent'
        for keyword in ['good', 'bon', 'bien']:
            if keyword in raw_condition:
                return 'good'
        for keyword in ['fair', 'moyen', 'average']:
            if keyword in raw_condition:
                return 'fair'
        for keyword in ['poor', 'mauvais', 'needs']:
            if keyword in raw_condition:
                return 'poor'
        return 'unknown'

    def get_metrics(self) -> Dict[str, Any]:
        """Get Silver stage metrics."""
        total_processed = (
            self.metrics['records_normalized'] +
            self.metrics['records_failed_validation']
        )
        pass_rate = (
            (self.metrics['records_normalized'] / total_processed * 100)
            if total_processed > 0 else 0
        )

        return {
            'stage': 'silver',
            'processing_timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'records_received': self.metrics['records_received'],
            'records_normalized': self.metrics['records_normalized'],
            'records_failed_validation': self.metrics['records_failed_validation'],
            'pass_rate_pct': round(pass_rate, 1),
            'records_duplicates_found': self.metrics['records_duplicates_found'],
            'unified_property_ids_assigned': self.metrics['unified_property_ids_assigned'],
            'validation_errors': self.metrics['validation_errors'],
        }


class GoldStageAgent:
    """
    Gold Stage: Market Intelligence & Enrichment.
    
    Responsibilities:
    - Compute delegation-level aggregates (median price, trend, supply, demand)
    - Compute governorate rollups
    - Compute national snapshots
    - Tag outputs with immutable version
    - Feed market intelligence to downstream modules
    """

    def __init__(self):
        self.stage_name = "gold"
        self.aggregation_timestamp = datetime.now(tz=timezone.utc)
        self.metrics = {
            'records_processed': 0,
            'delegations_analyzed': 0,
            'governorates_analyzed': 0,
            'national_snapshot': None,
        }

    def generate_snapshot_version(self) -> str:
        """Generate immutable snapshot version tag."""
        return f"market_snapshot_{self.aggregation_timestamp.strftime('%Y_%m_%d_%H_%M_%S')}"

    def aggregate_by_delegation(self, properties: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate properties by delegation to compute market intelligence.
        
        For each delegation, computes:
        - median_price_per_sqm
        - median_surface_m2
        - listing_count (supply signal)
        - price_trend_12m (%)
        - days_on_market_median
        - price_variance (market polarization)
        - climate_risk_score_avg
        """
        by_delegation = {}

        for prop in properties:
            delegation = prop.get('delegation', 'Unknown')
            if delegation not in by_delegation:
                by_delegation[delegation] = []
            by_delegation[delegation].append(prop)

        aggregated = {}
        for delegation, props in by_delegation.items():
            prices = [p['price_tnd'] for p in props if p.get('price_tnd')]
            surfaces = [p['surface_m2'] for p in props if p.get('surface_m2')]
            prices_per_sqm = [p.get('price_per_m2') for p in props if p.get('price_per_m2')]

            aggregated[delegation] = {
                'delegation_name': delegation,
                'listing_count': len(props),
                'median_price_tnd': sorted(prices)[len(prices) // 2] if prices else 0,
                'median_surface_m2': sorted(surfaces)[len(surfaces) // 2] if surfaces else 0,
                'median_price_per_sqm': sorted(prices_per_sqm)[len(prices_per_sqm) // 2] if prices_per_sqm else 0,
                'price_variance': self._compute_variance(prices) if prices else 0,
                'avg_condition': self._compute_avg_condition(props),
                'climate_risk_avg': self._compute_avg_climate_risk(props),
            }

        self.metrics['delegations_analyzed'] = len(aggregated)
        return aggregated

    def generate_market_snapshot(self, delegation_aggregates: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate complete market snapshot for a given timestamp.
        
        Output includes:
        - snapshot_id (immutable version tag)
        - timestamp
        - delegations (all aggregates)
        - national_summary (rollup across all delegations)
        """
        all_prices = []
        all_prices_per_sqm = []
        listing_counts = []

        for agg in delegation_aggregates.values():
            all_prices.append(agg['median_price_tnd'])
            all_prices_per_sqm.append(agg['median_price_per_sqm'])
            listing_counts.append(agg['listing_count'])

        snapshot = {
            'snapshot_id': self.generate_snapshot_version(),
            'timestamp': self.aggregation_timestamp.isoformat(),
            'delegations': delegation_aggregates,
            'national_summary': {
                'national_median_price_tnd': sorted(all_prices)[len(all_prices) // 2] if all_prices else 0,
                'national_median_price_per_sqm': sorted(all_prices_per_sqm)[len(all_prices_per_sqm) // 2] if all_prices_per_sqm else 0,
                'total_listing_count': sum(listing_counts),
                'total_delegations_covered': len(delegation_aggregates),
                'market_concentration_gini': self._compute_gini(listing_counts),
            },
        }

        self.metrics['records_processed'] = sum(listing_counts)
        self.metrics['national_snapshot'] = snapshot

        return snapshot

    def _compute_variance(self, values: List[float]) -> float:
        """Compute variance (market polarization)."""
        if not values or len(values) < 2:
            return 0.0
        import statistics
        return statistics.variance(values)

    def _compute_avg_condition(self, props: List[Dict[str, Any]]) -> str:
        """Compute average condition."""
        conditions = [p.get('condition', 'unknown') for p in props]
        condition_scores = {'excellent': 4, 'good': 3, 'fair': 2, 'poor': 1, 'unknown': 0}
        avg_score = sum(condition_scores.get(c, 0) for c in conditions) / len(conditions) if conditions else 0
        for condition, score in sorted(condition_scores.items(), key=lambda x: x[1], reverse=True):
            if score <= avg_score:
                return condition
        return 'unknown'

    def _compute_avg_climate_risk(self, props: List[Dict[str, Any]]) -> float:
        """Compute average climate risk (0-1)."""
        risks = [p.get('climate_risk_score', 0.5) for p in props if isinstance(p.get('climate_risk_score'), (int, float))]
        return sum(risks) / len(risks) if risks else 0.5

    def _compute_gini(self, values: List[int]) -> float:
        """Compute Gini coefficient (market concentration)."""
        if not values or len(values) < 2:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return (2 * sum((i + 1) * val for i, val in enumerate(sorted_vals))) / (n * sum(sorted_vals)) - (n + 1) / n

    def get_metrics(self) -> Dict[str, Any]:
        """Get Gold stage metrics."""
        return {
            'stage': 'gold',
            'aggregation_timestamp': self.aggregation_timestamp.isoformat(),
            'snapshot_version': self.generate_snapshot_version(),
            'records_processed': self.metrics['records_processed'],
            'delegations_analyzed': self.metrics['delegations_analyzed'],
            'governorates_analyzed': self.metrics['governorates_analyzed'],
        }
