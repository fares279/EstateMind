"""
Data Quality Validation Layer.

Implements schema contracts, data drift detection (PSI), geocoding quality metrics,
and validation rules for each pipeline stage (Bronze/Silver/Gold).

This module ensures that:
1. Every ingestion matches expected schema (fail-fast principle)
2. Data distribution shifts are detected via PSI monitoring
3. Geocoding quality is tracked and reported
4. Scraper health metrics are recorded for alerting
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class GeocodeAccuracy(Enum):
    """Geocoding accuracy levels."""
    POLYGON_LEVEL = "polygon_level"  # Pinpoint accuracy (±50m)
    CENTROID_LEVEL = "centroid_level"  # Delegation centroid (±5km)
    MISSING = "missing"  # No coordinates


@dataclass
class QualityReport:
    """Summary of data quality checks."""
    stage: str  # "bronze", "silver", "gold"
    records_processed: int
    records_passed: int
    records_failed: int
    errors: List[str]
    geocoding_accuracy: Optional[Dict[str, float]] = None
    psi_metrics: Optional[Dict[str, float]] = None

    @property
    def pass_rate(self) -> float:
        if self.records_processed == 0:
            return 0.0
        return self.records_passed / self.records_processed


class SilverSchemaValidator:
    """
    Schema validation for Silver layer (normalized data).
    
    Enforces canonical field types, value ranges, and nullability constraints.
    Implements fail-fast principle: if record fails validation, it's flagged
    for manual review rather than silently dropped.
    """

    # Canonical Silver schema constraints
    SCHEMA = {
        'record_id': {'type': str, 'required': True, 'max_length': 255},
        'source': {'type': str, 'required': True, 'enum': ['tayara', 'mubawab', 'tecnocasa', 'tunisie_annonce', 'bigdatis']},
        'listing_url': {'type': str, 'required': True, 'max_length': 500},
        'title': {'type': str, 'required': True, 'max_length': 300},
        'description': {'type': str, 'required': False, 'max_length': 5000},
        'transaction_type': {'type': str, 'required': True, 'enum': ['sale', 'rent']},
        'property_type': {'type': str, 'required': True, 'enum': ['apartment', 'house', 'commercial', 'land']},
        'price_tnd': {'type': (int, float), 'required': True, 'min': 5000, 'max': 50_000_000},
        'surface_m2': {'type': (int, float), 'required': True, 'min': 10, 'max': 100_000},
        'rooms': {'type': int, 'required': False, 'min': 0, 'max': 20},
        'bedrooms': {'type': int, 'required': False, 'min': 0, 'max': 15},
        'bathrooms': {'type': int, 'required': False, 'min': 0, 'max': 10},
        'governorate': {'type': str, 'required': True},  # Must be valid Tunisia governorate
        'city': {'type': str, 'required': False, 'max_length': 100},
        'delegation': {'type': str, 'required': False, 'max_length': 100},
        'location_lat': {'type': (int, float), 'required': False, 'min': 30.0, 'max': 37.5},
        'location_lon': {'type': (int, float), 'required': False, 'min': 8.0, 'max': 12.0},
        'geocoding_accuracy': {'type': str, 'required': False, 'enum': ['polygon_level', 'centroid_level', 'missing']},
        'price_per_m2': {'type': (int, float), 'required': False, 'min': 100, 'max': 50_000},
        'condition': {'type': str, 'required': False, 'enum': ['excellent', 'good', 'fair', 'poor', 'unknown']},
    }

    VALID_GOVERNORATES = {
        'Tunis', 'Ariana', 'Ben Arous', 'Manouba', 'Nabeul', 'Zaghouan',
        'Bizerte', 'Beja', 'Jendouba', 'Kef', 'Siliana', 'Sousse',
        'Monastir', 'Mahdia', 'Sfax', 'Kairouan', 'Kasserine', 'Sidi Bouzid',
        'Gabes', 'Medenine', 'Tataouine', 'Gafsa', 'Tozeur', 'Kebili',
    }

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a Silver record against schema constraints.
        
        Returns: (is_valid, list_of_errors)
        If invalid, errors list contains human-readable validation messages.
        """
        errors = []

        for field_name, constraints in self.SCHEMA.items():
            is_required = constraints.get('required', False)
            value = record.get(field_name)

            # Check required fields
            if is_required and value is None:
                errors.append(f"Field '{field_name}' is required but missing")
                continue

            if value is None:
                continue

            # Check field type
            expected_type = constraints.get('type')
            if expected_type and not isinstance(value, expected_type):
                errors.append(f"Field '{field_name}' has type {type(value)}, expected {expected_type}")

            # Check enumeration values
            enum_values = constraints.get('enum')
            if enum_values and value not in enum_values:
                errors.append(f"Field '{field_name}' value '{value}' not in allowed values: {enum_values}")

            # Check string max length
            if isinstance(value, str):
                max_length = constraints.get('max_length')
                if max_length and len(value) > max_length:
                    errors.append(f"Field '{field_name}' exceeds max length {max_length}")

            # Check numeric ranges
            if isinstance(value, (int, float)):
                min_val = constraints.get('min')
                max_val = constraints.get('max')
                if min_val is not None and value < min_val:
                    errors.append(f"Field '{field_name}' value {value} below minimum {min_val}")
                if max_val is not None and value > max_val:
                    errors.append(f"Field '{field_name}' value {value} exceeds maximum {max_val}")

        # Special validation: governorate must be valid Tunisia governorate
        gov = record.get('governorate')
        if gov and gov not in self.VALID_GOVERNORATES:
            errors.append(f"Governorate '{gov}' not recognized as valid Tunisia governorate")

        # Special validation: if coordinates provided, they must be within Tunisia bounds
        lat, lon = record.get('location_lat'), record.get('location_lon')
        if lat and lon:
            if not (30.0 <= lat <= 37.5 and 8.0 <= lon <= 12.0):
                errors.append(f"Coordinates ({lat}, {lon}) outside Tunisia geographic bounds")

        return len(errors) == 0, errors


class DataDriftDetector:
    """
    Population Stability Index (PSI) monitoring for data drift detection.
    
    Computes PSI on numeric features to detect distribution shifts that might
    indicate a change in data characteristics or scraper behavior.
    
    PSI = sum((expected_pct - actual_pct) * ln(expected_pct / actual_pct))
    PSI > 0.10 typically indicates significant drift requiring investigation.
    """

    PSI_THRESHOLD = 0.10  # Alert threshold
    HISTOGRAM_BINS = 10

    def __init__(self):
        """Initialize drift detector. Call train() to set baseline."""
        self.baseline_stats: Dict[str, Dict[str, np.ndarray]] = {}

    def train(self, records: List[Dict[str, Any]], features: List[str]) -> None:
        """
        Train detector on a baseline dataset.
        Computes mean, std, min, max for each feature.
        """
        for feature in features:
            values = [r.get(feature) for r in records if r.get(feature) is not None]
            if values:
                values = np.array(values, dtype=float)
                self.baseline_stats[feature] = {
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values),
                }

    def compute_psi(self, records: List[Dict[str, Any]], features: List[str]) -> Dict[str, float]:
        """
        Compute PSI for each feature comparing current records against baseline.
        
        Returns dict of {feature: psi_value}
        PSI > 0.10 indicates significant drift.
        """
        if not self.baseline_stats:
            raise ValueError("Detector not trained. Call train() first.")

        psi_scores = {}

        for feature in features:
            if feature not in self.baseline_stats:
                continue

            values = np.array(
                [r.get(feature) for r in records if r.get(feature) is not None],
                dtype=float
            )

            if len(values) == 0:
                psi_scores[feature] = 0.0
                continue

            baseline = self.baseline_stats[feature]
            min_val = min(baseline['min'], np.min(values))
            max_val = max(baseline['max'], np.max(values))

            # Create bins
            bins = np.linspace(min_val, max_val, self.HISTOGRAM_BINS + 1)

            # Histogram for baseline (from stats — approximate)
            baseline_hist, _ = np.histogram(
                np.random.normal(baseline['mean'], baseline['std'], size=1000),
                bins=bins
            )
            baseline_hist = baseline_hist + 1e-10  # Avoid log(0)
            baseline_pct = baseline_hist / np.sum(baseline_hist)

            # Histogram for current data
            current_hist, _ = np.histogram(values, bins=bins)
            current_hist = current_hist + 1e-10
            current_pct = current_hist / np.sum(current_hist)

            # Compute PSI
            psi = np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct))
            psi_scores[feature] = float(psi)

        return psi_scores


class GeocodingQualityMeter:
    """
    Tracks geocoding accuracy distribution.
    
    Computes:
    - % of listings with polygon-level accurate coordinates
    - % of listings with centroid-level coordinates
    - % of listings with missing coordinates
    
    This percentage becomes the quality ceiling for geospatial models downstream.
    """

    def measure(self, records: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Analyze geocoding accuracy of a batch of records.
        
        Returns: {
            'polygon_level_pct': float (0-100),
            'centroid_level_pct': float (0-100),
            'missing_pct': float (0-100),
        }
        """
        if not records:
            return {
                'polygon_level_pct': 0.0,
                'centroid_level_pct': 0.0,
                'missing_pct': 100.0,
            }

        polygon_count = 0
        centroid_count = 0
        missing_count = 0

        for record in records:
            accuracy = record.get('geocoding_accuracy', 'missing')
            if accuracy == 'polygon_level':
                polygon_count += 1
            elif accuracy == 'centroid_level':
                centroid_count += 1
            else:
                missing_count += 1

        total = len(records)
        return {
            'polygon_level_pct': (polygon_count / total) * 100,
            'centroid_level_pct': (centroid_count / total) * 100,
            'missing_pct': (missing_count / total) * 100,
        }


class ScraperHealthMonitor:
    """
    Monitors individual scraper agent health.
    
    Tracks:
    - Success rate (% of URLs successfully parsed)
    - Data freshness lag (age of data from source)
    - Coverage (% of expected fields present)
    - Error rate and error types
    """

    def compute_health_score(
        self,
        records_scraped: int,
        records_failed: int,
        avg_data_age_hours: float,
        field_coverage_pct: float,
    ) -> Dict[str, Any]:
        """
        Compute overall health score for a scraper (0-100).
        
        Components:
        - Success rate: 40% weight (target: >95%)
        - Data freshness: 30% weight (target: <24 hours)
        - Field coverage: 30% weight (target: >90%)
        """
        total_records = records_scraped + records_failed
        if total_records == 0:
            return {
                'health_score': 0.0,
                'status': 'unknown',
                'alerts': ['No records scraped yet'],
            }

        success_rate = (records_scraped / total_records) * 100
        success_score = min(success_rate / 95.0, 1.0) * 40  # Normalized to 40 points

        # Freshness score (target: data < 24 hours old)
        freshness_score = max(40 - (avg_data_age_hours / 24.0) * 30, 0)
        freshness_score = min(freshness_score, 30)  # Cap at 30 points

        # Coverage score (target: >90% of fields)
        coverage_score = min(field_coverage_pct / 90.0, 1.0) * 30  # Normalized to 30 points

        health_score = success_score + freshness_score + coverage_score

        # Determine status and alerts
        alerts = []
        if success_rate < 80:
            alerts.append(f"Low success rate: {success_rate:.1f}%")
        if avg_data_age_hours > 48:
            alerts.append(f"Data is stale: {avg_data_age_hours:.1f} hours old")
        if field_coverage_pct < 70:
            alerts.append(f"Low field coverage: {field_coverage_pct:.1f}%")

        if health_score >= 80:
            status = 'healthy'
        elif health_score >= 60:
            status = 'degraded'
        else:
            status = 'unhealthy'

        return {
            'health_score': round(health_score, 1),
            'status': status,
            'success_rate_pct': round(success_rate, 1),
            'avg_data_age_hours': round(avg_data_age_hours, 1),
            'field_coverage_pct': round(field_coverage_pct, 1),
            'alerts': alerts,
        }
