"""
Hardening 3: Portfolio Covariance Model
========================================

Computes portfolio volatility and diversification metrics using covariance matrix.
Generates alerts for concentration risk, correlation risk, and diversification opportunities.
"""

import logging
from typing import Dict, List, Tuple, Optional
import numpy as np
from datetime import timedelta, datetime

from django.utils import timezone

logger = logging.getLogger(__name__)


class PortfolioCovarianceModel:
    """
    Computes portfolio risk using covariance matrix of delegation price returns.
    """

    # Shrinkage estimator (Ledoit-Wolf) for small sample sizes
    SHRINKAGE_INTENSITY = 0.5

    def __init__(self, lookback_months: int = 24):
        """
        Initialize with lookback period for computing correlations.
        Default 24 months.
        """
        self.lookback_months = lookback_months

    def compute_correlation_matrix(self, delegations: List[str]) -> Tuple[np.ndarray, bool]:
        """
        Compute correlation matrix from historical delegation price data.
        
        Returns:
            correlation_matrix: numpy array [n_delegations × n_delegations]
            is_shrinkage_applied: boolean (True if Ledoit-Wolf was needed)
        """
        try:
            from estatemind.market.core.models import DelegationMarketSnapshot, Delegation

            # Collect price time series for each delegation
            lookback_date = timezone.now() - timedelta(days=self.lookback_months * 30)

            price_series = {}
            for delegation_name in delegations:
                try:
                    delegation = Delegation.objects.get(name__iexact=delegation_name)
                except:
                    logger.warning(f'Delegation {delegation_name} not found')
                    price_series[delegation_name] = []
                    continue

                snapshots = (
                    DelegationMarketSnapshot.objects
                    .filter(
                        delegation=delegation,
                        as_of_date__gte=lookback_date,
                    )
                    .order_by('as_of_date')
                    .values_list('as_of_date', 'median_price_per_sqm')
                )

                if len(snapshots) > 0:
                    prices = [s[1] for s in snapshots if s[1] is not None]
                    # Compute monthly returns
                    if len(prices) > 1:
                        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                                  for i in range(1, len(prices))]
                        price_series[delegation_name] = returns
                    else:
                        price_series[delegation_name] = []
                else:
                    logger.warning(f'No price history for {delegation_name}')
                    price_series[delegation_name] = []

            # Align time series and compute correlation
            n = len(delegations)
            corr_matrix = np.eye(n)
            is_shrinkage = False

            # Compute pairwise correlations
            for i, del_i in enumerate(delegations):
                for j, del_j in enumerate(delegations):
                    if i < j:
                        if len(price_series[del_i]) > 1 and len(price_series[del_j]) > 1:
                            # Use common dates only
                            min_len = min(len(price_series[del_i]), len(price_series[del_j]))
                            if min_len > 1:
                                corr = np.corrcoef(
                                    price_series[del_i][-min_len:],
                                    price_series[del_j][-min_len:],
                                )[0, 1]

                                # Apply Ledoit-Wolf shrinkage if sample size small
                                if min_len < 12:
                                    is_shrinkage = True
                                    corr = self.SHRINKAGE_INTENSITY * corr + (1 - self.SHRINKAGE_INTENSITY) * 0.3
                                    # Default to 0.3 (market correlation)

                                if np.isnan(corr):
                                    corr = 0.3

                                corr_matrix[i, j] = corr
                                corr_matrix[j, i] = corr

            return corr_matrix, is_shrinkage

        except Exception as e:
            logger.error(f'Error computing correlation matrix: {e}')
            # Return identity matrix (no correlation) on error
            return np.eye(len(delegations)), False

    def get_volatilities(self, delegations: List[str]) -> Dict[str, float]:
        """Get annual price volatility for each delegation."""
        try:
            from estatemind.market.core.models import DelegationMarketSnapshot, Delegation

            lookback_date = timezone.now() - timedelta(days=self.lookback_months * 30)

            vols = {}
            for delegation_name in delegations:
                # Get delegation object
                try:
                    delegation = Delegation.objects.get(name__iexact=delegation_name)
                except:
                    vols[delegation_name] = 0.12  # Default
                    continue

                snapshots = (
                    DelegationMarketSnapshot.objects
                    .filter(
                        delegation=delegation,
                        as_of_date__gte=lookback_date,
                    )
                    .order_by('as_of_date')
                    .values_list('median_price_per_sqm')
                )

                if len(snapshots) > 1:
                    prices = [s[0] for s in snapshots if s[0] is not None]
                    if len(prices) > 1:
                        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                                  for i in range(1, len(prices))]
                        vol = np.std(returns) * np.sqrt(12)  # Annualize
                        vols[delegation_name] = vol
                    else:
                        vols[delegation_name] = 0.12
                else:
                    vols[delegation_name] = 0.12  # Default 12% annual vol

            return vols

        except Exception as e:
            logger.error(f'Error computing volatilities: {e}')
            return {d: 0.12 for d in delegations}

    def compute_portfolio_volatility(self, weights: np.ndarray, delegations: List[str]) -> float:
        """
        Compute portfolio volatility using covariance matrix.
        
        vol_p = sqrt(w^T × Σ × w)
        """
        try:
            corr_matrix, _ = self.compute_correlation_matrix(delegations)
            vols = self.get_volatilities(delegations)

            # Build covariance matrix from correlations and volatilities
            n = len(delegations)
            cov_matrix = np.zeros((n, n))

            for i in range(n):
                for j in range(n):
                    cov_matrix[i, j] = corr_matrix[i, j] * vols[delegations[i]] * vols[delegations[j]]

            # Compute portfolio variance
            weights_array = np.array(weights)
            portfolio_var = weights_array @ cov_matrix @ weights_array
            portfolio_vol = np.sqrt(portfolio_var)

            return portfolio_vol

        except Exception as e:
            logger.error(f'Error computing portfolio volatility: {e}')
            return 0.12

    def compute_diversification_ratio(self, weights: np.ndarray, delegations: List[str]) -> float:
        """
        Diversification ratio = weighted avg vol / portfolio vol
        > 1.0 means diversification benefit exists
        """
        try:
            vols = self.get_volatilities(delegations)
            weighted_avg_vol = sum(w * vols[d] for w, d in zip(weights, delegations))

            portfolio_vol = self.compute_portfolio_volatility(weights, delegations)

            if portfolio_vol > 0:
                dr = weighted_avg_vol / portfolio_vol
            else:
                dr = 1.0

            return dr

        except Exception as e:
            logger.error(f'Error computing diversification ratio: {e}')
            return 1.0

    def suggest_rebalancing(self, weights: np.ndarray, delegations: List[str],
                          target_return: Optional[float] = None,
                          target_vol_reduction: float = 0.10) -> Dict:
        """
        Suggest alternative weights that reduce volatility while maintaining return.
        
        Algorithm: minimize portfolio vol subject to:
          - expected return within 0.5% of current
          - weights sum to 1, all >= 0
        
        Simplified: find maximum diversification ratio allocation.
        """
        try:
            n = len(delegations)
            current_vol = self.compute_portfolio_volatility(weights, delegations)

            # Max diversification: weights proportional to 1/volatility
            vols = self.get_volatilities(delegations)
            inv_vols = np.array([1.0 / max(v, 0.01) for v in vols.values()])
            suggested_weights = inv_vols / inv_vols.sum()

            suggested_vol = self.compute_portfolio_volatility(suggested_weights, delegations)
            vol_reduction_pct = (current_vol - suggested_vol) / current_vol * 100

            return {
                'current_weights': dict(zip(delegations, weights)),
                'suggested_weights': dict(zip(delegations, suggested_weights)),
                'current_volatility': current_vol,
                'suggested_volatility': suggested_vol,
                'vol_reduction_pct': vol_reduction_pct,
                'rationale': (
                    f'Reweighting to max diversification allocation would reduce '
                    f'portfolio volatility from {current_vol*100:.1f}% to {suggested_vol*100:.1f}% '
                    f'({vol_reduction_pct:.1f}% reduction).'
                ),
            }

        except Exception as e:
            logger.error(f'Error suggesting rebalancing: {e}')
            return {}

    def generate_concentration_alerts(self, weights: np.ndarray, delegations: List[str]) -> List[Dict]:
        """Generate alerts for concentration risk."""
        alerts = []

        # Single delegation concentration
        for w, d in zip(weights, delegations):
            if w > 0.50:
                alerts.append({
                    'type': 'high_single_concentration',
                    'delegation': d,
                    'weight': w * 100,
                    'message': f'{d} represents {w*100:.0f}% of portfolio. '
                              f'A 10% price change would move total portfolio by {w*10:.1f}%.',
                })

        # Top 3 concentration
        top_3_weight = sum(sorted(weights, reverse=True)[:3])
        if top_3_weight > 0.70:
            alerts.append({
                'type': 'top_3_concentration',
                'weight': top_3_weight * 100,
                'message': f'Top 3 delegations represent {top_3_weight*100:.0f}% of portfolio. '
                          f'Consider adding exposure to underrepresented regions.',
            })

        return alerts

    def generate_correlation_alerts(self, delegations: List[str]) -> List[Dict]:
        """Generate alerts for high correlation (systemic risk) and data quality."""
        alerts = []

        try:
            corr_matrix, is_shrinkage = self.compute_correlation_matrix(delegations)

            # Data quality alert if shrinkage was applied
            if is_shrinkage:
                alerts.append({
                    'type': 'low_correlation_reliability',
                    'severity': 'INFO',
                    'message': (
                        'Insufficient price history for some delegations. '
                        'Ledoit-Wolf shrinkage applied. Correlation estimates are conservative.'
                    ),
                })

            # High correlation alerts
            for i in range(len(delegations)):
                for j in range(i + 1, len(delegations)):
                    if corr_matrix[i, j] > 0.70:
                        alerts.append({
                            'type': 'high_correlation',
                            'severity': 'WARN',
                            'delegation1': delegations[i],
                            'delegation2': delegations[j],
                            'correlation': corr_matrix[i, j],
                            'message': (
                                f'{delegations[i]} and {delegations[j]} have correlation {corr_matrix[i, j]:.2f}. '
                                f'They will likely move together in market downturns.'
                            ),
                        })

        except Exception as e:
            logger.warning(f'Error generating correlation alerts: {e}')

        return alerts

    def generate_diversification_suggestions(self, delegations: List[str],
                                           excluded_delegations: List[str] = None) -> List[Dict]:
        """Suggest which delegations to add for better diversification."""
        suggestions = []

        if not excluded_delegations:
            excluded_delegations = []

        try:
            from estatemind.market.core.models import DelegationMarketSnapshot

            # Get all available delegations
            all_delegations = (
                DelegationMarketSnapshot.objects
                .values_list('delegation_name', flat=True)
                .distinct()
            )
            all_delegations = list(set(all_delegations) - set(delegations) - set(excluded_delegations))

            # For each potential addition, compute correlation with current portfolio
            corr_matrix, _ = self.compute_correlation_matrix(delegations + all_delegations)

            portfolio_size = len(delegations)
            for new_del in all_delegations[:5]:  # Top 5 suggestions
                new_del_idx = delegations.__len__() + all_delegations.index(new_del)

                avg_corr_with_portfolio = np.mean([
                    corr_matrix[portfolio_size + all_delegations.index(new_del), i]
                    for i in range(portfolio_size)
                ])

                if avg_corr_with_portfolio < 0.50:
                    suggestions.append({
                        'delegation': new_del,
                        'avg_correlation': avg_corr_with_portfolio,
                        'message': (
                            f'Adding {new_del} (correlation {avg_corr_with_portfolio:.2f} with portfolio) '
                            f'would improve diversification.'
                        ),
                    })

        except Exception as e:
            logger.warning(f'Error generating diversification suggestions: {e}')

        return suggestions
