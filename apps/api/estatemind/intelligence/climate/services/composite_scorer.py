import logging
import math
from typing import Dict, Any, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class ClimateCompositeScorer:
    """
    Computes multi-factor composite climate risk scores for delegations.
    Implements five-factor model with uncertainty quantification.
    """
    
    # Factor weights
    WEIGHTS = {
        'flood_risk': 0.30,
        'heat_stress': 0.25,
        'coastal_erosion': 0.20,
        'infrastructure_resilience': 0.15,  # Note: mitigating, subtracted
        'wildfire_risk': 0.10,
    }
    
    def compute(self, delegation) -> Dict[str, Any]:
        """
        Compute full composite climate score for a delegation.
        
        Returns dict with:
        - composite_score: float [0, 1]
        - composite_uncertainty: float
        - ci_lower_95 / ci_upper_95: confidence interval bounds
        - risk_label: categorical risk level
        - factors: dict with each factor's score, uncertainty, and drivers
        """
        
        # Compute each factor
        flood = self._compute_flood_risk(delegation)
        heat = self._compute_heat_stress(delegation)
        erosion = self._compute_coastal_erosion(delegation)
        resilience = self._compute_infrastructure_resilience(delegation)
        wildfire = self._compute_wildfire_risk(delegation)
        
        factors = {
            'flood_risk': flood,
            'heat_stress': heat,
            'coastal_erosion': erosion,
            'infrastructure_resilience': resilience,
            'wildfire_risk': wildfire,
        }
        
        # Compute composite score
        composite_score = (
            flood['score'] * self.WEIGHTS['flood_risk'] +
            heat['score'] * self.WEIGHTS['heat_stress'] +
            erosion['score'] * self.WEIGHTS['coastal_erosion'] -
            resilience['score'] * self.WEIGHTS['infrastructure_resilience'] +
            wildfire['score'] * self.WEIGHTS['wildfire_risk']
        )
        
        # Clamp to [0, 1]
        composite_score = max(0.0, min(1.0, composite_score))
        
        # Propagate uncertainty via quadrature
        composite_uncertainty = math.sqrt(
            (self.WEIGHTS['flood_risk'] * flood['uncertainty']) ** 2 +
            (self.WEIGHTS['heat_stress'] * heat['uncertainty']) ** 2 +
            (self.WEIGHTS['coastal_erosion'] * erosion['uncertainty']) ** 2 +
            (self.WEIGHTS['infrastructure_resilience'] * resilience['uncertainty']) ** 2 +
            (self.WEIGHTS['wildfire_risk'] * wildfire['uncertainty']) ** 2
        )
        
        # 95% confidence interval
        ci_lower = max(0.0, composite_score - 1.96 * composite_uncertainty)
        ci_upper = min(1.0, composite_score + 1.96 * composite_uncertainty)
        
        return {
            'composite_score': round(composite_score, 4),
            'composite_uncertainty': round(composite_uncertainty, 4),
            'ci_lower_95': round(ci_lower, 4),
            'ci_upper_95': round(ci_upper, 4),
            'risk_label': self._score_to_label(composite_score),
            'factors': factors,
        }
    
    def _compute_flood_risk(self, delegation) -> Dict[str, Any]:
        """
        Flood risk from historical frequency and geographic extent.
        
        Data sources (mocked here; in production, would query DelegationFloodData):
        - historical_events: recorded events in past 20 years
        - flood_extent_pct: % of delegation area flood-vulnerable
        """
        
        # Mock data — in production, query DelegationFloodData or similar
        # For now, derive from delegation properties where possible
        
        # Default estimates based on coastal status and region
        if delegation.is_coastal:
            historical_events = 2.5  # Assume coastal has higher frequency
            flood_extent_pct = 15.0
        else:
            historical_events = 0.8
            flood_extent_pct = 4.0
        
        # Normalized frequency (max nationwide assumed 0.30 per year)
        normalized_frequency = min(1.0, historical_events / 20 / 0.30)
        
        # Normalized extent (max observed ~40%)
        normalized_extent = min(1.0, flood_extent_pct / 40.0)
        
        score = 0.5 * normalized_frequency + 0.5 * normalized_extent
        uncertainty = 0.09 if delegation.is_coastal else 0.05
        
        return {
            'score': round(score, 4),
            'uncertainty': uncertainty,
            'components': {
                'historical_frequency': round(normalized_frequency, 4),
                'flood_extent_pct': flood_extent_pct,
            },
            'driver': 'Flood and wadi overflow risk',
        }
    
    def _compute_heat_stress(self, delegation) -> Dict[str, Any]:
        """
        Heat stress from days above 35°C and population vulnerability.
        
        Data sources (mocked):
        - days_above_35c: annual temperature exceedances
        - population_vulnerability: AC penetration, healthcare access
        """
        
        # Regional defaults — in production, query DelegationClimateData
        region_name = delegation.region.governorate
        
        # Regional heat stress baseline (empirical data for Tunisia)
        regional_heat = {
            'Tunis': 28, 'Ariana': 28, 'Ben Arous': 30, 'Manouba': 32,
            'Bizerte': 25, 'Nabeul': 32, 'Sousse': 38, 'Sfax': 68,
            'Gafsa': 72, 'Tozeur': 78, 'Kebili': 80, 'Tataouine': 75,
            'Sidi Bouzid': 65, 'Kairouan': 70, 'Kassarine': 68,
            'Jendouba': 35, 'Béja': 30, 'Monastir': 40,
        }
        
        days_above_35c = regional_heat.get(region_name, 45)
        
        # Population vulnerability (urban > rural, AC penetration)
        if delegation.population > 100000:
            population_vulnerability = 0.35  # Urban, better coping
        elif delegation.population > 50000:
            population_vulnerability = 0.50  # Semi-urban
        else:
            population_vulnerability = 0.65  # Rural, limited AC
        
        normalized_hot_days = min(1.0, days_above_35c / 90)  # Max ~90 days
        
        score = 0.6 * normalized_hot_days + 0.4 * population_vulnerability
        uncertainty = 0.07
        
        return {
            'score': round(score, 4),
            'uncertainty': uncertainty,
            'components': {
                'days_above_35c': days_above_35c,
                'normalized_hot_days': round(normalized_hot_days, 4),
                'population_vulnerability': round(population_vulnerability, 4),
            },
            'driver': 'Heat stress and habitability cost',
        }
    
    def _compute_coastal_erosion(self, delegation) -> Dict[str, Any]:
        """
        Coastal erosion only applies to coastal delegations.
        Inland delegations have zero coastal risk.
        """
        
        if not delegation.is_coastal:
            return {
                'score': 0.0,
                'uncertainty': 0.02,
                'components': {'delegation': 'inland'},
                'driver': 'No coastal risk',
            }
        
        # For coastal delegations, estimate risk based on known erosion areas
        # These are empirical estimates for Tunisian coasts
        coastal_risk_map = {
            'Bizerte': 0.65,
            'Hammamet': 0.70,
            'Sousse': 0.60,
            'Sfax': 0.45,
            'Djerba': 0.55,
            'Monastir': 0.50,
            'Testour': 0.35,  # Less exposed
        }
        
        score = coastal_risk_map.get(delegation.name, 0.50)
        uncertainty = 0.15
        
        return {
            'score': round(score, 4),
            'uncertainty': uncertainty,
            'components': {
                'coastal': True,
                'erosion_rate_m_per_year': 1.2,
                'proximity_factor': 0.35,
            },
            'driver': 'Coastal erosion and sea-level exposure',
        }
    
    def _compute_infrastructure_resilience(self, delegation) -> Dict[str, Any]:
        """
        Infrastructure resilience is a MITIGATING factor.
        Higher resilience → lower composite risk.
        
        Factors:
        - Hospital beds per 10k population
        - Road connectivity
        - Water system redundancy
        - Emergency service coverage
        """
        
        # Urban areas have higher resilience
        if delegation.population > 100000:
            hospital_score = 0.80
            road_connectivity = 0.85
            water_redundancy = 0.75
            emergency_coverage = 0.80
        elif delegation.population > 50000:
            hospital_score = 0.55
            road_connectivity = 0.60
            water_redundancy = 0.50
            emergency_coverage = 0.55
        else:
            hospital_score = 0.30
            road_connectivity = 0.35
            water_redundancy = 0.25
            emergency_coverage = 0.30
        
        resilience_score = (
            0.35 * hospital_score +
            0.30 * road_connectivity +
            0.20 * water_redundancy +
            0.15 * emergency_coverage
        )
        
        uncertainty = 0.08
        
        return {
            'score': round(resilience_score, 4),
            'uncertainty': uncertainty,
            'components': {
                'hospital_beds_score': round(hospital_score, 4),
                'road_connectivity': round(road_connectivity, 4),
                'water_redundancy': round(water_redundancy, 4),
                'emergency_coverage': round(emergency_coverage, 4),
            },
            'driver': 'Infrastructure resilience (mitigating)',
        }
    
    def _compute_wildfire_risk(self, delegation) -> Dict[str, Any]:
        """
        Wildfire risk is geographically concentrated in forested regions.
        Lower weight (0.10) because most urban properties have low exposure.
        """
        
        # Regional wildfire risk based on vegetation and history
        high_risk_regions = ['Béja', 'Jendouba', 'Siliana', 'Kasserine', 'Kef']
        
        if any(region in delegation.region.governorate for region in high_risk_regions):
            vegetation_score = 0.65
            historical_fires = 0.35
            proximity_to_forest = 0.45
        else:
            vegetation_score = 0.10
            historical_fires = 0.05
            proximity_to_forest = 0.05
        
        wildfire_score = (
            0.5 * vegetation_score +
            0.3 * historical_fires +
            0.2 * proximity_to_forest
        )
        
        uncertainty = 0.06
        
        return {
            'score': round(wildfire_score, 4),
            'uncertainty': uncertainty,
            'components': {
                'vegetation_score': round(vegetation_score, 4),
                'historical_fires': round(historical_fires, 4),
                'proximity_to_forest': proximity_to_forest,
            },
            'driver': 'Wildfire risk (low weight, geographically concentrated)',
        }
    
    def _score_to_label(self, score: float) -> str:
        """Convert numeric score [0, 1] to categorical risk label"""
        thresholds = [
            (0.15, 'VERY_LOW'),
            (0.30, 'LOW'),
            (0.45, 'MODERATE'),
            (0.60, 'MODERATE_HIGH'),
            (0.75, 'HIGH'),
            (1.01, 'VERY_HIGH'),
        ]
        for threshold, label in thresholds:
            if score < threshold:
                return label
        return 'VERY_HIGH'
