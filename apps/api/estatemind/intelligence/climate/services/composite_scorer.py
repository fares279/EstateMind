"""Composite climate risk per delegation.

Inputs come from data/climate_governorate_normals.csv: approximate climatological normals
per governorate (annual rainfall, days above 35 °C), a flood-exposure index from river
basins and documented major floods, and forest cover. They are curated approximations for
comparing places, not measured hazard maps. Coastal exposure uses each delegation's
distance to the coastline (market.core.coastline).

Previously: flood took two fixed values by coastal flag; the heat table used names that
did not match the database (Manouba, Kebili, Kassarine, Kef) and missed eight
governorates; there was no drought / water-stress factor; and "resilience" was invented
from population alone. The composite rose toward the north and Tozeur came out VERY_LOW.
"""
import csv
import logging
import math
from functools import lru_cache
from typing import Any, Dict

logger = logging.getLogger(__name__)

NORMALS_SOURCE = ('Approximate climatological normals and documented floods per governorate '
                  '(data/climate_governorate_normals.csv); not a measured hazard map.')

# Known coastal erosion hotspots (sandy tourist coasts), otherwise a coastal default.
EROSION_HOTSPOTS = {'hammamet': 0.70, 'nabeul': 0.60, 'sousse medina': 0.60, 'hammam sousse': 0.60,
                    'monastir': 0.55, 'mahdia': 0.55, 'djerba midoun': 0.60, 'djerba houmt souk': 0.55,
                    'bizerte nord': 0.60, 'kelibia': 0.55, 'la marsa': 0.50, 'raoued': 0.60}


@lru_cache(maxsize=1)
def _normals() -> dict[str, dict]:
    from config.paths import DATA_DIR
    from estatemind.intelligence.valuation.inference.location import plain

    with open(DATA_DIR / 'climate_governorate_normals.csv', encoding='utf-8') as fh:
        return {plain(r['governorate']): {k: (float(v) if k not in ('governorate', 'note') else v) for k, v in r.items()}
                for r in csv.DictReader(fh)}


class ClimateCompositeScorer:
    """Six factors, weighted; infrastructure (urban services) mitigates slightly."""

    WEIGHTS = {
        'flood_risk': 0.25,
        'heat_stress': 0.25,
        'water_stress': 0.20,
        'coastal_erosion': 0.15,
        'wildfire_risk': 0.10,
        'infrastructure_resilience': 0.05,  # mitigating, subtracted
    }

    def _norms(self, delegation) -> dict:
        from estatemind.intelligence.valuation.inference.location import plain
        found = _normals().get(plain(delegation.region.governorate))
        if found is None:
            logger.warning('No climate normals for %s', delegation.region.governorate)
            return {'annual_rainfall_mm': 350.0, 'days_above_35c': 45.0, 'flood_exposure': 0.4,
                    'forest_cover': 0.1, 'note': 'national typical values (governorate not in the table)'}
        return found

    def compute(self, delegation) -> Dict[str, Any]:
        n = self._norms(delegation)
        factors = {
            'flood_risk': self._flood(delegation, n),
            'heat_stress': self._heat(delegation, n),
            'water_stress': self._water(n),
            'coastal_erosion': self._erosion(delegation),
            'wildfire_risk': self._wildfire(n),
            'infrastructure_resilience': self._resilience(delegation),
        }
        w = self.WEIGHTS
        score = sum(factors[k]['score'] * w[k] for k in w if k != 'infrastructure_resilience')
        score -= factors['infrastructure_resilience']['score'] * w['infrastructure_resilience']
        # rescale so a place at the maximum of every hazard reaches 1.0
        score = max(0.0, min(1.0, score / (1 - w['infrastructure_resilience'])))
        uncertainty = math.sqrt(sum((w[k] * factors[k]['uncertainty']) ** 2 for k in w))
        return {
            'composite_score': round(score, 4),
            'composite_uncertainty': round(uncertainty, 4),
            'ci_lower_95': round(max(0.0, score - 1.96 * uncertainty), 4),
            'ci_upper_95': round(min(1.0, score + 1.96 * uncertainty), 4),
            'risk_label': self._score_to_label(score),
            'factors': factors,
            'source': NORMALS_SOURCE,
        }

    def _flood(self, delegation, n) -> Dict[str, Any]:
        exposure = n['flood_exposure']
        # low-lying coasts add storm-surge and sebkha flooding
        score = min(1.0, exposure + (0.10 if delegation.is_coastal else 0.0))
        return {'score': round(score, 4), 'uncertainty': 0.12,
                'components': {'governorate_flood_exposure': exposure, 'coastal': bool(delegation.is_coastal)},
                'driver': 'Wadi and river flooding, from basins and documented major floods'}

    def _heat(self, delegation, n) -> Dict[str, Any]:
        days = n['days_above_35c']
        hot = min(1.0, days / 100.0)
        # places above 100k people cope better (air conditioning, services)
        vulnerability = 0.35 if delegation.population > 100_000 else 0.5 if delegation.population > 50_000 else 0.65
        score = 0.75 * hot + 0.25 * vulnerability
        return {'score': round(score, 4), 'uncertainty': 0.08,
                'components': {'days_above_35c': days, 'population_vulnerability': vulnerability},
                'driver': 'Extreme heat days and habitability cost'}

    def _water(self, n) -> Dict[str, Any]:
        rain = n['annual_rainfall_mm']
        score = max(0.0, min(1.0, 1 - (rain - 80) / (700 - 80)))
        return {'score': round(score, 4), 'uncertainty': 0.08,
                'components': {'annual_rainfall_mm': rain},
                'driver': 'Drought and water scarcity (from annual rainfall)'}

    def _erosion(self, delegation) -> Dict[str, Any]:
        from estatemind.intelligence.valuation.inference.location import plain
        if not delegation.is_coastal:
            return {'score': 0.0, 'uncertainty': 0.02, 'components': {'coastal': False},
                    'driver': 'No coastal exposure'}
        score = EROSION_HOTSPOTS.get(plain(delegation.name), 0.45)
        return {'score': score, 'uncertainty': 0.15, 'components': {'coastal': True},
                'driver': 'Coastal erosion and sea-level exposure'}

    def _wildfire(self, n) -> Dict[str, Any]:
        forest = n['forest_cover']
        # forests burn most where summers are also hot and dry
        score = min(1.0, forest * (0.7 + 0.3 * min(1.0, n['days_above_35c'] / 60)) * 1.4)
        return {'score': round(score, 4), 'uncertainty': 0.08,
                'components': {'forest_cover': forest},
                'driver': 'Wildfire (forest cover and summer heat)'}

    def _resilience(self, delegation) -> Dict[str, Any]:
        score = 0.8 if delegation.population > 100_000 else 0.55 if delegation.population > 50_000 else 0.3
        return {'score': score, 'uncertainty': 0.10,
                'components': {'population': delegation.population},
                'driver': 'Urban services (proxy: population size), mitigating'}

    def _score_to_label(self, score: float) -> str:
        for threshold, label in ((0.15, 'VERY_LOW'), (0.30, 'LOW'), (0.45, 'MODERATE'),
                                 (0.60, 'MODERATE_HIGH'), (0.75, 'HIGH')):
            if score < threshold:
                return label
        return 'VERY_HIGH'


def score_fields(score: Dict[str, Any]) -> Dict[str, Any]:
    """DelegationClimateScore field values for a compute() result."""
    from django.utils import timezone

    f = score['factors']
    fields = {k: score[k] for k in ('composite_score', 'composite_uncertainty', 'ci_lower_95', 'ci_upper_95',
                                    'risk_label')}
    for factor in ('flood_risk', 'heat_stress', 'water_stress', 'coastal_erosion', 'infrastructure_resilience',
                   'wildfire_risk'):
        fields[f'{factor}_score'] = f[factor]['score']
        fields[f'{factor}_uncertainty'] = f[factor]['uncertainty']
    fields.update(computed_at=timezone.now(), data_vintage=timezone.now().date(),
                  computation_method='composite_normals_v2')
    return fields
