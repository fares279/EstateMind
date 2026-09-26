"""Export investor zone CSVs from the current gold layer / delegation benchmarks."""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Export investor zone_market_stats.csv and zone_price_forecasts.csv from core delegation data.'

    def handle(self, *args, **options):
        from estatemind.market.core.models import Delegation

        base_dir = Path(__file__).resolve().parents[2] / 'data'
        base_dir.mkdir(parents=True, exist_ok=True)

        stats_path = base_dir / 'zone_market_stats.csv'
        forecasts_path = base_dir / 'zone_price_forecasts.csv'

        property_map = {
            'apartment': {
                'avg': 'apt_avg_tnd',
                'min': 'apt_min_tnd',
                'max': 'apt_max_tnd',
                'trend': 'apt_trend_pct',
            },
            'house': {
                'avg': 'house_avg_tnd',
                'min': 'house_min_tnd',
                'max': 'house_max_tnd',
                'trend': 'house_trend_pct',
            },
            'commercial': {
                'avg': 'comm_avg_tnd',
                'min': 'comm_min_tnd',
                'max': 'comm_max_tnd',
                'trend': 'comm_trend_pct',
            },
            'land': {
                'avg': 'land_avg_tnd',
                'min': 'land_min_tnd',
                'max': 'land_max_tnd',
                'trend': 'land_trend_pct',
            },
        }

        stats_rows = []
        forecast_rows = []

        for delegation in Delegation.objects.select_related('region').all():
            for property_type, fields in property_map.items():
                avg_value = getattr(delegation, fields['avg'])
                min_value = getattr(delegation, fields['min'])
                max_value = getattr(delegation, fields['max'])
                trend_value = getattr(delegation, fields['trend'])

                if avg_value is None:
                    continue

                stats_rows.append({
                    'delegation': delegation.name,
                    'governorate': delegation.region.governorate,
                    'property_type': property_type,
                    'snapshot_date': '2026-01-01',
                    'demand_intensity_score': 60.0,
                    'supply_demand_ratio': 1.0,
                    'median_days_on_market': 45.0,
                    'vacancy_rate_pct': 7.0,
                    'avg_proximity_school_km': 1.5,
                    'avg_proximity_hospital_km': 3.0,
                    'avg_proximity_transport_km': 1.0,
                    'price_change_mom_pct': 0.5,
                    'price_change_yoy_pct': trend_value or 0.0,
                    'zone_population': delegation.population or 0,
                    'transaction_velocity_score': 50.0,
                    'avg_price_per_m2_tnd': float(avg_value),
                    'median_price_per_m2_tnd': float(avg_value),
                })

                forecast_3m = float(avg_value) * (1 + (trend_value or 0.0) / 100 * 0.25)
                forecast_6m = float(avg_value) * (1 + (trend_value or 0.0) / 100 * 0.50)
                forecast_12m = float(avg_value) * (1 + (trend_value or 0.0) / 100)

                forecast_rows.append({
                    'delegation': delegation.name,
                    'governorate': delegation.region.governorate,
                    'property_type': property_type,
                    'forecast_generated_date': '2026-01-01',
                    'forecast_3m_pct': round((forecast_3m / float(avg_value) - 1) * 100, 2),
                    'forecast_6m_pct': round((forecast_6m / float(avg_value) - 1) * 100, 2),
                    'forecast_12m_pct': round((forecast_12m / float(avg_value) - 1) * 100, 2),
                    'forecast_direction': 'UP' if (trend_value or 0.0) >= 0 else 'DOWN',
                    'forecast_confidence': 'medium',
                    'trend_volatility_score': 25.0,
                    'forecast_reliability': 0.6,
                })

        with stats_path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(stats_rows[0].keys()) if stats_rows else [
                'delegation', 'governorate', 'property_type', 'snapshot_date',
                'demand_intensity_score', 'supply_demand_ratio', 'median_days_on_market',
                'vacancy_rate_pct', 'avg_proximity_school_km', 'avg_proximity_hospital_km',
                'avg_proximity_transport_km', 'price_change_mom_pct', 'price_change_yoy_pct',
                'zone_population', 'transaction_velocity_score', 'avg_price_per_m2_tnd',
                'median_price_per_m2_tnd',
            ])
            writer.writeheader()
            writer.writerows(stats_rows)

        with forecasts_path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(forecast_rows[0].keys()) if forecast_rows else [
                'delegation', 'governorate', 'property_type', 'forecast_generated_date',
                'forecast_3m_pct', 'forecast_6m_pct', 'forecast_12m_pct', 'forecast_direction',
                'forecast_confidence', 'trend_volatility_score', 'forecast_reliability',
            ])
            writer.writeheader()
            writer.writerows(forecast_rows)

        self.stdout.write(self.style.SUCCESS(f'Wrote {len(stats_rows)} stats rows and {len(forecast_rows)} forecast rows.'))
