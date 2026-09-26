"""
Module 10 Requirement 2: Scenario Validity Layer

Validates simulation scenario parameters against historical feasibility ranges
and logical constraints. Prevents users from submitting nonsensical scenarios.

Two modes:
- STRICT: Reject out-of-range, require correction
- EXPLORATORY: Allow with warning, mark as speculative
"""

import logging
from typing import Dict, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationMode(Enum):
    STRICT = "strict"
    EXPLORATORY = "exploratory"


class ScenarioValidator:
    """
    Validates simulation scenario parameters against historical
    feasibility ranges and logical constraints.
    """
    
    # Historical feasibility ranges derived from Tunisian economic data
    FEASIBILITY_RANGES = {
        'interest_rate_shock_pct': {
            'min': -5.0,
            'max': 5.0,
            'historical_max_annual_change': 2.5,
            'unit': 'percentage points',
            'rationale': 'BCT has never moved rates by more than 2.5pp in a year. '
                        'Target range: [-5%, +5%] represents unprecedented but '
                        'not impossible policy action.',
        },
        'foreign_investment_multiplier': {
            'min': 0.5,
            'max': 2.5,
            'unit': 'multiplier on current level',
            'rationale': 'FDI flows historically within ±60% year-over-year. '
                        'Range allows for significant shocks while staying realistic.',
        },
        'ltv_ratio_change_pct': {
            'min': -20.0,
            'max': 20.0,
            'unit': 'percentage point change in LTV',
            'rationale': 'Regulatory LTV changes are gradual and bounded. '
                        '±20pp represents major policy shift.',
        },
        'diaspora_demand_boost_pct': {
            'min': -30.0,
            'max': 100.0,
            'unit': 'percentage change in diaspora buyer volume',
            'rationale': 'Diaspora flows respond to exchange rate and sentiment. '
                        'Historical range: ±30% (tight policy) to +100% (favorable news).',
        },
        'construction_supply_shock_pct': {
            'min': -40.0,
            'max': 40.0,
            'unit': 'percentage change in new supply',
            'rationale': 'Construction capacity constraints limit supply changes. '
                        'Beyond ±40%, assume catastrophic/unrealistic events.',
        },
        'inflation_shock_pct': {
            'min': -2.0,
            'max': 8.0,
            'unit': 'percentage points annual inflation change',
            'rationale': 'Tunisia\'s inflation historically bounded. '
                        'Range covers low and high inflation regimes.',
        },
        'simulation_months': {
            'min': 6,
            'max': 24,
            'unit': 'months',
            'rationale': 'Shorter than 6m: insufficient for policy effects. '
                        'Longer than 24m: uncertainty explodes, output uninformative.',
        },
        'n_agents': {
            'min': 50,
            'max': 2000,
            'unit': 'total agents in simulation',
            'rationale': 'Below 50: insufficient statistical power. '
                        'Above 2000: computational cost prohibitive.',
        },
        'n_runs': {
            'min': 1,
            'max': 100,
            'unit': 'ensemble runs',
            'rationale': 'Single run: deterministic. 100 runs: ~6 minutes compute.',
        }
    }
    
    # Logical consistency rules
    CONSISTENCY_RULES = [
        {
            'name': 'rate_construction_consistency',
            'description': 'High rates reduce construction (negative correlation)',
            'check': lambda s: not (
                s.get('interest_rate_shock_pct', 0) > 3.0 and
                s.get('construction_supply_shock_pct', 0) > 20.0
            ),
            'message': 'Interest rates >+3% historically reduce construction, '
                      'not increase it. This combination is internally inconsistent.',
            'severity': 'MEDIUM'
        },
        {
            'name': 'diaspora_foreign_policy_consistency',
            'description': 'Diaspora surge with restrictive foreign policy is contradictory',
            'check': lambda s: not (
                s.get('diaspora_demand_boost_pct', 0) > 50 and
                s.get('foreign_investment_multiplier', 1.0) < 0.7
            ),
            'message': 'Large diaspora surge (+50%) is inconsistent with '
                      'tightened foreign investment rules (0.7x). Both are affected '
                      'by same regulatory environment.',
            'severity': 'LOW'
        },
        {
            'name': 'inflation_rate_consistency',
            'description': 'Moderate inflation + very tight monetary policy is contradictory',
            'check': lambda s: not (
                s.get('inflation_shock_pct', 0) < -1.0 and
                s.get('interest_rate_shock_pct', 0) < -3.0
            ),
            'message': 'Deflation (-1%+) with rate cuts (>-3%) suggests policy confusion. '
                      'Usually paired: either inflation+rate_hikes or deflation+rate_cuts.',
            'severity': 'LOW'
        }
    ]
    
    def __init__(self, mode: ValidationMode = ValidationMode.STRICT):
        self.mode = mode
    
    def validate(self, scenario: Dict) -> Dict:
        """
        Validates scenario parameters.
        
        Returns:
        {
            'is_valid': bool,
            'errors': [...],              # Must be corrected (STRICT mode)
            'warnings': [...],            # Unusual but allowed
            'suggestions': {...},         # Recommended values
            'feasibility_score': 0–1,     # Overall plausibility
            'feasibility_label': str,     # PLAUSIBLE / MARGINAL / SPECULATIVE
            'can_proceed': bool,          # Can user run simulation?
            'mode': str,
        }
        """
        
        errors = []
        warnings = []
        suggestions = {}
        feasibility_scores = []
        
        # ===== Check parameter bounds =====
        for param, value in scenario.items():
            if param not in self.FEASIBILITY_RANGES:
                continue  # Ignore unknown parameters
            
            bounds = self.FEASIBILITY_RANGES[param]
            param_min = bounds['min']
            param_max = bounds['max']
            
            # Hard bounds: outside physically possible range
            if value < param_min or value > param_max:
                error_obj = {
                    'parameter': param,
                    'submitted_value': value,
                    'allowed_range': [param_min, param_max],
                    'unit': bounds.get('unit', ''),
                    'rationale': bounds.get('rationale', ''),
                    'suggested_value': max(param_min, min(param_max, value))
                }
                
                if self.mode == ValidationMode.STRICT:
                    errors.append(error_obj)
                else:
                    # EXPLORATORY mode: allow with warning
                    error_obj['severity'] = 'HIGH'
                    warnings.append(error_obj)
                
                suggestions[param] = error_obj['suggested_value']
                feasibility_scores.append(0.0)
            
            # Soft bounds: unusual but possible
            elif 'historical_max_annual_change' in bounds:
                hist_max = bounds['historical_max_annual_change']
                if abs(value) > hist_max:
                    warning_obj = {
                        'parameter': param,
                        'submitted_value': value,
                        'historical_typical_max': hist_max,
                        'message': f'Value {value} exceeds historical typical maximum '
                                  f'of ±{hist_max}. This represents a significant policy '
                                  f'shift outside modern precedent.',
                        'severity': 'MEDIUM'
                    }
                    warnings.append(warning_obj)
                    feasibility_scores.append(0.5)
                else:
                    feasibility_scores.append(1.0)
            else:
                feasibility_scores.append(1.0)
        
        # ===== Check logical consistency between parameters =====
        consistency_issues = self._check_consistency(scenario)
        warnings.extend(consistency_issues)
        
        # ===== Compute overall feasibility score =====
        if feasibility_scores:
            feasibility_score = sum(feasibility_scores) / len(feasibility_scores)
        else:
            feasibility_score = 1.0
        
        feasibility_label = (
            'PLAUSIBLE' if feasibility_score >= 0.8 else
            'MARGINAL' if feasibility_score >= 0.5 else
            'SPECULATIVE'
        )
        
        # ===== Determine if user can proceed =====
        can_proceed = True
        if self.mode == ValidationMode.STRICT and len(errors) > 0:
            can_proceed = False
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'suggestions': suggestions,
            'feasibility_score': float(feasibility_score),
            'feasibility_label': feasibility_label,
            'can_proceed': can_proceed,
            'mode': self.mode.value,
            'n_errors': len(errors),
            'n_warnings': len(warnings),
        }
    
    def _check_consistency(self, scenario: Dict) -> List[Dict]:
        """
        Checks that parameter combinations make logical sense.
        """
        
        issues = []
        
        for rule in self.CONSISTENCY_RULES:
            try:
                if not rule['check'](scenario):
                    issues.append({
                        'type': 'logical_inconsistency',
                        'rule': rule['name'],
                        'description': rule['description'],
                        'message': rule['message'],
                        'severity': rule['severity']
                    })
            except KeyError:
                # Parameters might not be in scenario, skip
                pass
        
        return issues
    
    def get_suggestion(self, scenario: Dict, param: str) -> float:
        """
        Returns suggested value for a parameter.
        
        If current value is invalid:  return clamped value
        If current value is soft-warning: return current value (but flag warning)
        If current value is valid: return current value
        """
        
        if param not in self.FEASIBILITY_RANGES:
            return scenario.get(param)
        
        value = scenario.get(param)
        if value is None:
            return None
        
        bounds = self.FEASIBILITY_RANGES[param]
        return max(bounds['min'], min(bounds['max'], value))


def validate_batch(scenarios: List[Dict], 
                    mode: ValidationMode = ValidationMode.STRICT) -> List[Dict]:
    """
    Validates multiple scenarios.
    Useful for batch scenario submission.
    """
    
    validator = ScenarioValidator(mode=mode)
    return [validator.validate(s) for s in scenarios]


def get_feasibility_ranges() -> Dict:
    """
    Returns the feasibility ranges for UI display and documentation.
    """
    
    return {
        param: {
            'min': bounds['min'],
            'max': bounds['max'],
            'unit': bounds.get('unit', ''),
            'rationale': bounds.get('rationale', ''),
        }
        for param, bounds in ScenarioValidator.FEASIBILITY_RANGES.items()
    }


def get_consistency_rules() -> List[Dict]:
    """
    Returns logical consistency rules for documentation.
    """
    
    return [
        {
            'name': rule['name'],
            'description': rule['description'],
            'message': rule['message'],
            'severity': rule['severity']
        }
        for rule in ScenarioValidator.CONSISTENCY_RULES
    ]
