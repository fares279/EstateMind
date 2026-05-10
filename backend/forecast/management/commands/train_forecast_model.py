"""
Train a MultiOutput HistGradientBoosting price-forecast model.

Reads engineered features from:
    C:/…/Price-Trend-Forecasting/data/engineered_features.csv   (monthly delegation metrics)
    C:/…/Price-Trend-Forecasting/data/core_pricing.csv           (listing-level prices)

Exports trained model to:
    backend/forecast/artifacts/forecast_model.joblib

Run:
    python manage.py train_forecast_model
    python manage.py train_forecast_model --horizons 12 --estimators 200
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

# Data directory: two levels above the outer EstateMind directory
_DATA_DIR   = Path(__file__).resolve().parents[5] / 'Price-Trend-Forecasting' / 'data'
_ARTIFACTS  = Path(__file__).resolve().parents[2] / 'artifacts'

FEATURE_COLS = [
    'avg_price_tnd', 'log_price', 'volatility_index',
    'ma_3m', 'ma_6m', 'ma_12m',
    'std_3m', 'std_6m', 'std_12m',
    'slope_3', 'slope_6', 'slope_12', 'acceleration',
    'lag_1', 'lag_3', 'lag_6', 'lag_12',
    'month_of_year', 'month_sin', 'month_cos',
    'momentum_90d_pct', 'affordability_index',
    'market_absorption_rate', 'demand_supply_ratio',
]


def _build_targets(df: pd.DataFrame, price_col: str, horizons: int) -> pd.DataFrame:
    """Build multi-output target matrix (h=1..horizons) using forward-shift per group."""
    group_cols = [c for c in ('delegation', 'governorate', 'property_type') if c in df.columns]
    target_cols = {}
    for h in range(1, horizons + 1):
        shifted = df.groupby(group_cols)[price_col].shift(-h)
        target_cols[f'target_h{h}'] = shifted
    return pd.concat([df, pd.DataFrame(target_cols, index=df.index)], axis=1)


class Command(BaseCommand):
    help = 'Train MultiOutput HistGradientBoosting model from Price-Trend-Forecasting data.'

    def add_arguments(self, parser):
        parser.add_argument('--horizons',   type=int, default=12,  help='Number of forecast horizons')
        parser.add_argument('--estimators', type=int, default=300, help='Max iterations for HistGBT')
        parser.add_argument('--max-depth',  type=int, default=6,   help='Max tree depth')

    def handle(self, *args, **options):
        try:
            from sklearn.ensemble import HistGradientBoostingRegressor
            from sklearn.multioutput import MultiOutputRegressor
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import OrdinalEncoder
            from sklearn.compose import ColumnTransformer
            import joblib
        except ImportError as exc:
            raise CommandError(f'scikit-learn / joblib not installed: {exc}')

        horizons   = options['horizons']
        n_est      = options['estimators']
        max_depth  = options['max_depth']

        self.stdout.write(f'Loading data from {_DATA_DIR}…')

        eng_path = _DATA_DIR / 'engineered_features.csv'
        if not eng_path.exists():
            raise CommandError(f'engineered_features.csv not found at {eng_path}')

        df = pd.read_csv(eng_path, low_memory=False)
        self.stdout.write(f'  Loaded engineered_features.csv: {len(df):,} rows, {df.columns.tolist()[:8]}…')

        # Identify price column
        price_col = None
        for candidate in ('avg_price_tnd', 'price_per_m2', 'predicted_price_per_m2', 'avg_price'):
            if candidate in df.columns:
                price_col = candidate
                break
        if price_col is None:
            numeric_cols = df.select_dtypes(include='number').columns.tolist()
            price_col = numeric_cols[0] if numeric_cols else None
        if price_col is None:
            raise CommandError('Cannot identify price column in engineered_features.csv')
        self.stdout.write(f'  Using price column: {price_col}')

        # Sort chronologically
        time_col = next((c for c in ('month', 'date', 'year_month') if c in df.columns), None)
        if time_col:
            df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
            df = df.sort_values(time_col)

        # Build targets
        self.stdout.write(f'Building {horizons}-horizon targets…')
        df = _build_targets(df, price_col, horizons)
        target_cols = [f'target_h{h}' for h in range(1, horizons + 1)]

        # Identify categorical columns present in df
        cat_cols = [c for c in ('delegation', 'governorate', 'property_type', 'delegation_id') if c in df.columns]

        # Select available feature columns
        avail_feats = [c for c in FEATURE_COLS if c in df.columns]
        all_feats   = avail_feats + cat_cols
        self.stdout.write(f'  Feature columns ({len(all_feats)}): {all_feats[:6]}…')

        # Drop rows where any target is NaN (last <horizons rows per group)
        df_clean = df[all_feats + target_cols].dropna(subset=target_cols)
        self.stdout.write(f'  Training samples: {len(df_clean):,}')

        if len(df_clean) < 50:
            raise CommandError('Insufficient training data after cleaning.')

        X = df_clean[all_feats]
        Y = df_clean[target_cols].values

        # Build column transformer
        transformers = []
        if cat_cols:
            cat_present = [c for c in cat_cols if c in X.columns]
            if cat_present:
                transformers.append(('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1), cat_present))
        num_cols = [c for c in avail_feats if c in X.columns]
        if num_cols:
            from sklearn.preprocessing import StandardScaler
            transformers.append(('num', 'passthrough', num_cols))

        if transformers:
            from sklearn.compose import ColumnTransformer
            preprocessor = ColumnTransformer(transformers, remainder='drop')
        else:
            from sklearn.preprocessing import FunctionTransformer
            preprocessor = FunctionTransformer()

        base_est = HistGradientBoostingRegressor(
            max_iter=n_est,
            max_depth=max_depth,
            learning_rate=0.05,
            min_samples_leaf=20,
            random_state=42,
        )
        model = Pipeline([
            ('prep',  preprocessor),
            ('model', MultiOutputRegressor(base_est, n_jobs=-1)),
        ])

        self.stdout.write(f'Training MultiOutput HistGBT ({n_est} iter, depth {max_depth})…')
        model.fit(X, Y)

        # Quick MAPE estimate on training set (in-sample proxy)
        Y_pred = model.predict(X)
        mask   = Y != 0
        mape   = np.mean(np.abs((Y[mask] - Y_pred[mask]) / Y[mask])) * 100 if mask.any() else float('nan')
        self.stdout.write(f'  Training MAPE (in-sample): {mape:.2f}%')

        # Save
        _ARTIFACTS.mkdir(parents=True, exist_ok=True)
        out_path = _ARTIFACTS / 'forecast_model.joblib'
        joblib.dump({
            'model':        model,
            'feature_cols': all_feats,
            'target_cols':  target_cols,
            'price_col':    price_col,
            'horizons':     horizons,
            'train_mape':   mape,
        }, out_path)

        self.stdout.write(self.style.SUCCESS(
            f'Model saved to {out_path}  (in-sample MAPE {mape:.2f}%)'
        ))
