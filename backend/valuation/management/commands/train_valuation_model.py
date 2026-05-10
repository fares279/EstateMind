"""
Train a gradient-boosting model for property valuation.

Uses listings.csv (10,056 rows) from backend/valuation/data/ and the
delegation-level price data from delegations.csv as additional context.

Exports trained model to:
    backend/valuation/artifacts/valuation_model.joblib

Run:
    python manage.py train_valuation_model
    python manage.py train_valuation_model --estimators 500 --max-depth 8
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

_APP_DIR    = Path(__file__).resolve().parents[2]         # valuation/
_DATA_DIR   = _APP_DIR / 'data'
_ARTIFACTS  = _APP_DIR / 'artifacts'
_OUTER      = Path(__file__).resolve().parents[5]         # outer EstateMind/
_DELEG_CSV  = _OUTER / 'delegations' / 'delegations.csv'

LISTINGS_CSV = _DATA_DIR / 'listings.csv'

# Canonical model feature columns
FEATURE_COLS = [
    'property_type', 'transaction_type', 'governorate', 'city',
    'surface_m2', 'bedrooms', 'bathrooms',
]
CAT_COLS = ['property_type', 'transaction_type', 'governorate', 'city']
NUM_COLS = ['surface_m2', 'bedrooms', 'bathrooms']
TARGET   = 'price_per_m2'

PPM2_MIN = 100
PPM2_MAX = 25_000


class Command(BaseCommand):
    help = 'Train HistGradientBoosting valuation model from listings.csv.'

    def add_arguments(self, parser):
        parser.add_argument('--estimators', type=int, default=400, help='Max gradient boosting iterations')
        parser.add_argument('--max-depth',  type=int, default=6,   help='Max tree depth')
        parser.add_argument('--l2-reg',     type=float, default=1.0, help='L2 regularisation')
        parser.add_argument('--test-split', type=float, default=0.15, help='Holdout fraction for eval')

    def handle(self, *args, **options):
        try:
            from sklearn.ensemble import HistGradientBoostingRegressor
            from sklearn.preprocessing import OrdinalEncoder
            from sklearn.compose import ColumnTransformer
            from sklearn.pipeline import Pipeline
            from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
            import joblib
        except ImportError as exc:
            raise CommandError(f'scikit-learn / joblib not installed: {exc}')

        n_est     = options['estimators']
        max_depth = options['max_depth']
        l2_reg    = options['l2_reg']
        test_frac = options['test_split']

        # ── 1. Load listings ──────────────────────────────────────────────────
        if not LISTINGS_CSV.exists():
            raise CommandError(f'Listings CSV not found: {LISTINGS_CSV}')

        self.stdout.write(f'Loading {LISTINGS_CSV}…')
        df = pd.read_csv(LISTINGS_CSV, low_memory=False)
        self.stdout.write(f'  Raw rows: {len(df):,}  columns: {df.columns.tolist()[:8]}')

        # Coerce numerics
        for col in ('price_tnd', 'surface_m2', 'price_per_m2', 'bedrooms', 'bathrooms'):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Compute price_per_m2 when missing
        if TARGET not in df.columns:
            if {'price_tnd', 'surface_m2'}.issubset(df.columns):
                df[TARGET] = df['price_tnd'] / df['surface_m2'].replace({0: np.nan})
            else:
                raise CommandError(f'Cannot derive {TARGET} from available columns.')

        # Remove outliers and nulls
        df = df[df[TARGET].between(PPM2_MIN, PPM2_MAX)].dropna(subset=[TARGET])
        df['surface_m2'] = df['surface_m2'].clip(lower=10, upper=20_000)
        df['bedrooms']   = df['bedrooms'].fillna(0).clip(lower=0, upper=20)
        df['bathrooms']  = df['bathrooms'].fillna(0).clip(lower=0, upper=10)

        # Normalise text columns
        for col in CAT_COLS:
            if col in df.columns:
                df[col] = df[col].fillna('unknown').astype(str).str.lower().str.strip()

        # Normalise property_type to canonical 4-type system
        _alias = {'villa': 'house', 'office': 'commercial', 'farm': 'commercial',
                  'appartement': 'apartment', 'maison': 'house', 'terrain': 'land'}
        if 'property_type' in df.columns:
            df['property_type'] = df['property_type'].map(lambda x: _alias.get(x, x))

        self.stdout.write(f'  Clean rows: {len(df):,}')

        # ── 2. Optionally enrich with delegation-level avg prices ─────────────
        if _DELEG_CSV.exists():
            try:
                deleg_df = pd.read_csv(_DELEG_CSV, encoding='utf-8-sig')
                for col in ('Delegation', 'Governorate'):
                    deleg_df[col] = deleg_df[col].str.strip().str.lower()
                avg_map = dict(zip(
                    deleg_df['Delegation'],
                    deleg_df.get('Apartment_Avg_TND', deleg_df.iloc[:, 2])
                ))
                df['city_avg_price'] = df['city'].str.lower().map(avg_map)
                if 'city_avg_price' not in FEATURE_COLS:
                    FEATURE_COLS.append('city_avg_price')
                    NUM_COLS.append('city_avg_price')
                self.stdout.write(f'  Enriched with delegation averages ({len(avg_map)} entries).')
            except Exception as exc:
                self.stdout.write(f'  Delegation enrichment skipped: {exc}')

        avail_feats = [c for c in FEATURE_COLS if c in df.columns]
        avail_cat   = [c for c in CAT_COLS if c in avail_feats]
        avail_num   = [c for c in NUM_COLS  if c in avail_feats]

        X = df[avail_feats].copy()
        y = df[TARGET].values

        # ── 3. Chronological / index split ───────────────────────────────────
        split_idx = int(len(X) * (1 - test_frac))
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y[:split_idx],      y[split_idx:]
        self.stdout.write(f'  Train: {len(X_train):,}  Test: {len(X_test):,}')

        # ── 4. Build pipeline ─────────────────────────────────────────────────
        transformers = []
        if avail_cat:
            transformers.append((
                'cat',
                OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1),
                avail_cat,
            ))
        if avail_num:
            transformers.append(('num', 'passthrough', avail_num))

        from sklearn.compose import ColumnTransformer
        preprocessor = ColumnTransformer(transformers, remainder='drop')

        model = Pipeline([
            ('prep',  preprocessor),
            ('model', HistGradientBoostingRegressor(
                max_iter=n_est,
                max_depth=max_depth,
                l2_regularization=l2_reg,
                learning_rate=0.05,
                min_samples_leaf=20,
                random_state=42,
            )),
        ])

        # ── 5. Train ──────────────────────────────────────────────────────────
        self.stdout.write(f'Training HistGBT (max_iter={n_est}, depth={max_depth})…')
        model.fit(X_train, y_train)

        # ── 6. Evaluate ───────────────────────────────────────────────────────
        y_pred_train = model.predict(X_train)
        y_pred_test  = model.predict(X_test)

        train_mae  = mean_absolute_error(y_train, y_pred_train)
        test_mae   = mean_absolute_error(y_test,  y_pred_test)
        train_mape = mean_absolute_percentage_error(y_train, y_pred_train) * 100
        test_mape  = mean_absolute_percentage_error(y_test,  y_pred_test)  * 100

        self.stdout.write(
            f'  Train MAE={train_mae:.0f} TND/m²  MAPE={train_mape:.2f}%\n'
            f'  Test  MAE={test_mae:.0f} TND/m²  MAPE={test_mape:.2f}%'
        )

        # ── 7. Save ───────────────────────────────────────────────────────────
        _ARTIFACTS.mkdir(parents=True, exist_ok=True)
        out_path = _ARTIFACTS / 'valuation_model.joblib'
        joblib.dump({
            'model':        model,
            'feature_cols': avail_feats,
            'cat_cols':     avail_cat,
            'num_cols':     avail_num,
            'version':      'histgbt_v1',
            'train_mae':    train_mae,
            'test_mae':     test_mae,
            'train_mape':   train_mape,
            'test_mape':    test_mape,
            'n_train':      len(X_train),
            'n_test':       len(X_test),
        }, out_path)

        self.stdout.write(self.style.SUCCESS(
            f'Saved to {out_path}  '
            f'(test MAE {test_mae:.0f} TND/m², MAPE {test_mape:.2f}%)'
        ))
