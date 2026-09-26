"""
Hardening 2: Offline RL Buy/Wait Classifier
=============================================

LightGBM-based classifier trained on historical investor outcomes.
Learns which features predict good investments without explicit exploration.

This replaces the rule-based classifier after the system collects enough historical data.
"""

import logging
from typing import Dict, Any, Optional, List
import pickle
import os

import numpy as np

logger = logging.getLogger(__name__)

# Try to import lightgbm (optional - system works with rule-based if not installed)
try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False


class OfflineRLBuyWaitClassifier:
    """
    Offline RL classifier for buy/wait recommendation.
    
    Trained on historical investor outcomes:
      - Features: delegation trend, opportunity score, yield, portfolio concentration, etc.
      - Labels: realized_return > 0.08 (good buy) vs <= 0.08 (bad buy)
    
    Uses SHAP for explainability.
    """

    # Feature names in training order
    FEATURE_NAMES = [
        'delegation_momentum_3m',
        'delegation_momentum_12m',
        'opportunity_score',
        'undervaluation_pct',
        'estimated_net_yield',
        'portfolio_concentration_pct',
        'climate_risk_score',
        'national_interest_rate',
        'delegation_dom',
    ]

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize classifier.
        
        If model_path provided, load from disk.
        Otherwise, use rule-based fallback.
        """
        self.model = None
        self.is_trained = False

        if model_path and os.path.exists(model_path):
            try:
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                self.is_trained = True
                logger.info('Loaded pre-trained offline RL classifier')
            except Exception as e:
                logger.warning(f'Failed to load classifier from {model_path}: {e}')

        if not self.is_trained:
            logger.info('Using rule-based fallback (no trained RL classifier available)')

    def predict(self, features: Dict[str, float]) -> Dict[str, Any]:
        """
        Make prediction: BUY | WAIT | AVOID with confidence and SHAP drivers.
        """
        if not self.is_trained:
            return self._fallback_predict(features)

        try:
            # Extract features in order
            X = np.array([
                [
                    features.get('delegation_momentum_3m', 0.0),
                    features.get('delegation_momentum_12m', 0.0),
                    features.get('opportunity_score', 50.0),
                    features.get('undervaluation_pct', 0.0),
                    features.get('estimated_net_yield', 0.0),
                    features.get('portfolio_concentration_pct', 0.0),
                    features.get('climate_risk_score', 0.5),
                    features.get('national_interest_rate', 8.0),
                    features.get('delegation_dom', 30.0),
                ]
            ])

            # Get probability
            p_good_buy = self.model.predict_proba(X)[0, 1]

            # Classify
            if p_good_buy >= 0.70:
                signal = 'BUY'
            elif p_good_buy >= 0.40:
                signal = 'WAIT'
            else:
                signal = 'AVOID'

            # Get SHAP drivers (approximation without true SHAP)
            drivers = self._approximate_shap(X[0], p_good_buy)

            return {
                'signal': signal,
                'p_good_buy': float(p_good_buy),
                'confidence': min(abs(p_good_buy - 0.5) * 2, 0.95),
                'label': f'{signal} (RL-based, {p_good_buy*100:.0f}% confidence)',
                'drivers': drivers,
                'model_type': 'offline_rl',
            }

        except Exception as e:
            logger.error(f'RL classifier prediction error: {e}')
            return self._fallback_predict(features)

    def _fallback_predict(self, features: Dict[str, float]) -> Dict[str, Any]:
        """
        Fallback to calibrated rule-based prediction when RL classifier lacks data.
        Uses thresholds derived from market research, not arbitrary values.
        """
        score = 0.5  # neutral base
        drivers = []

        # 1. Price momentum signal (strongest predictor of appreciation)
        momentum_12m = features.get('delegation_momentum_12m', 0)
        if momentum_12m > 0.08:
            score += 0.18
            drivers.append({
                'feature': 'Strong price momentum (>8%)',
                'impact': +0.18
            })
        elif momentum_12m > 0.03:
            score += 0.08
            drivers.append({
                'feature': 'Moderate price momentum (3-8%)',
                'impact': +0.08
            })
        elif momentum_12m < -0.02:
            score -= 0.15
            drivers.append({
                'feature': 'Negative price momentum',
                'impact': -0.15
            })

        # 2. Undervaluation signal
        underval = features.get('undervaluation_pct', 0)
        if underval > 0.15:
            score += 0.15
            drivers.append({
                'feature': '15%+ below market',
                'impact': +0.15
            })
        elif underval > 0.08:
            score += 0.08
            drivers.append({
                'feature': '8-15% below market',
                'impact': +0.08
            })
        elif underval < -0.05:
            score -= 0.10
            drivers.append({
                'feature': 'Overpriced vs market',
                'impact': -0.10
            })

        # 3. Yield adequacy (income stability)
        net_yield = features.get('estimated_net_yield', 0)
        if net_yield > 0.045:
            score += 0.12
            drivers.append({
                'feature': 'Strong net yield >4.5%',
                'impact': +0.12
            })
        elif net_yield > 0.030:
            score += 0.06
            drivers.append({
                'feature': 'Adequate yield 3-4.5%',
                'impact': +0.06
            })
        elif net_yield < 0.020:
            score -= 0.12
            drivers.append({
                'feature': 'Weak yield <2%',
                'impact': -0.12
            })

        # 4. Portfolio concentration risk (leverage control)
        concentration = features.get('portfolio_concentration_pct', 0)
        if concentration > 0.60:
            score -= 0.12
            drivers.append({
                'feature': '60%+ single-delegation concentration',
                'impact': -0.12
            })
        elif concentration > 0.40:
            score -= 0.05
            drivers.append({
                'feature': '40-60% concentration',
                'impact': -0.05
            })

        # 5. Climate risk (extreme weather, long-term viability)
        climate = features.get('climate_risk_score', 0)
        if climate > 0.70:
            score -= 0.08
            drivers.append({
                'feature': 'High climate risk (>0.70)',
                'impact': -0.08
            })
        elif climate < 0.30:
            score += 0.05
            drivers.append({
                'feature': 'Low climate risk (<0.30)',
                'impact': +0.05
            })

        # 6. Interest rate environment (debt servicing cost)
        int_rate = features.get('national_interest_rate', 8.0)
        if int_rate > 9.0:
            score -= 0.06
            drivers.append({
                'feature': 'High interest rates (>9%)',
                'impact': -0.06
            })

        # Clamp score to valid range
        score = max(0.05, min(0.95, score))

        # Determine signal thresholds (calibrated from market data)
        if score > 0.65:
            signal = 'BUY'
        elif score > 0.40:
            signal = 'WAIT'
        else:
            signal = 'AVOID'

        return {
            'signal': signal,
            'p_good_buy': score,
            'confidence': 'MEDIUM',  # rule-based is never HIGH confidence
            'label': f'{signal} (rule-based fallback)',
            'drivers': sorted(drivers, key=lambda x: abs(x['impact']), reverse=True)[:5],
            'model_type': 'rule_based',
        }

    def _approximate_shap(self, features: np.ndarray, prediction: float) -> Dict[str, float]:
        """
        Approximate SHAP values by perturbation.
        (True SHAP would require shap package)
        """
        drivers = {}

        for i, feature_name in enumerate(self.FEATURE_NAMES):
            # Perturb feature by ±10%
            delta = features[i] * 0.1 if features[i] != 0 else 0.1
            X_plus = features.copy()
            X_plus[i] += delta

            try:
                p_plus = self.model.predict_proba(X_plus.reshape(1, -1))[0, 1]
                contribution = (p_plus - prediction) / delta if delta != 0 else 0.0
                drivers[feature_name] = float(contribution)
            except:
                drivers[feature_name] = 0.0

        return drivers

    def train(self, X: np.ndarray, y: np.ndarray, model_path: str) -> Dict[str, Any]:
        """
        Train classifier on historical investor outcomes.
        
        Args:
            X: feature matrix [n_samples × 9]
            y: labels [n_samples]: 1 for good buy, 0 for bad buy
            model_path: where to save trained model
        
        Returns: training metrics
        """
        if not HAS_LIGHTGBM:
            logger.error('LightGBM not installed. Cannot train RL classifier.')
            return {'error': 'LightGBM required for training'}

        try:
            # Split into train/test
            from sklearn.model_selection import train_test_split

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            # Train LightGBM
            self.model = lgb.LGBMClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
            )

            self.model.fit(X_train, y_train)

            # Evaluate
            train_acc = self.model.score(X_train, y_train)
            test_acc = self.model.score(X_test, y_test)
            test_proba = self.model.predict_proba(X_test)[:, 1]

            # AUC
            from sklearn.metrics import roc_auc_score, precision_score, recall_score
            auc = roc_auc_score(y_test, test_proba)
            precision = precision_score(y_test, self.model.predict(X_test), zero_division=0)
            recall = recall_score(y_test, self.model.predict(X_test), zero_division=0)

            # Save model
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            with open(model_path, 'wb') as f:
                pickle.dump(self.model, f)

            self.is_trained = True
            logger.info(f'Trained RL classifier: train_acc={train_acc:.3f}, test_acc={test_acc:.3f}, auc={auc:.3f}')

            return {
                'train_accuracy': train_acc,
                'test_accuracy': test_acc,
                'auc': auc,
                'precision': precision,
                'recall': recall,
                'model_path': model_path,
            }

        except Exception as e:
            logger.error(f'Error training RL classifier: {e}')
            return {'error': str(e)}
