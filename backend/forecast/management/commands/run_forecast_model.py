"""
Run the trained forecast model and populate DelegationForecast + DelegationPriceData.

Loads the pre-trained model artifact, runs inference on the latest engineered
features, and writes results to the database.  Falls back to the pre-computed
forecast_table_h12.csv when the model cannot run inference (e.g., feature
columns changed).

Run:
    python manage.py run_forecast_model
    python manage.py run_forecast_model --model-path artifacts/my_model.joblib
    python manage.py run_forecast_model --use-csv   # force CSV fallback
"""
import csv
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

_APP_DIR     = Path(__file__).resolve().parents[2]   # forecast/
_ARTIFACTS   = _APP_DIR / 'artifacts'
_OUTER       = Path(__file__).resolve().parents[5]   # outer EstateMind/

_MODEL_PATH  = _ARTIFACTS / 'forecast_model.joblib'
_TABLE_CSV   = _OUTER / 'Price-Trend-Forecasting' / 'forecast_only_artifacts_h12' / 'forecast_table_h12.csv'
_ENG_FEAT    = _OUTER / 'Price-Trend-Forecasting' / 'data' / 'engineered_features.csv'
_DELEG_CSV   = _OUTER / 'delegations' / 'delegations.csv'

FORECAST_ORIGIN = date(2026, 1, 1)


def _add_months(d, n):
    total = d.month - 1 + n
    return date(d.year + total // 12, total % 12 + 1, 1)


def _parse_trend(raw):
    s = str(raw).strip().rstrip('%').replace('+', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


class Command(BaseCommand):
    help = 'Run forecast model → populate DelegationForecast + DelegationPriceData.'

    def add_arguments(self, parser):
        parser.add_argument('--model-path', type=str, default='', help='Path to model joblib (overrides default)')
        parser.add_argument('--use-csv',    action='store_true',   help='Skip model; use pre-computed forecast_table_h12.csv')
        parser.add_argument('--property-type', type=str, default='apartment', help='Property type for ML inference (apartment|house|commercial|land)')

    def handle(self, *args, **options):
        from forecast.models import DelegationForecast, DelegationPriceData

        use_csv    = options['use_csv']
        model_path = Path(options['model_path']) if options['model_path'] else _MODEL_PATH
        prop_type  = options['property_type']

        # ── 1. Load/build governorate lookup from delegations.csv ─────────────
        gov_map = {}   # delegation_name → governorate
        price_map = {} # delegation_name → {property_type: {min, avg, max, trend, notes}}
        if _DELEG_CSV.exists():
            PROP_COLS = {
                'apartment':  ('Apartment_Avg_TND','Apartment_Min_TND','Apartment_Max_TND','Apartment_Trend_Percent','Apartment_Notes'),
                'house':      ('House_Avg_TND','House_Min_TND','House_Max_TND','House_Trend_Percent','House_Notes'),
                'commercial': ('Commercial_Avg_TND','Commercial_Min_TND','Commercial_Max_TND','Commercial_Trend_Percent','Commercial_Notes'),
                'land':       ('Land_Avg_TND','Land_Min_TND','Land_Max_TND','Land_Trend_Percent','Land_Notes'),
            }
            with open(_DELEG_CSV, newline='', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    d = row.get('Delegation', '').strip()
                    g = row.get('Governorate', '').strip()
                    if not d or not g:
                        continue
                    gov_map[d] = g
                    price_map.setdefault(d, {})
                    for pt, (avg_col, min_col, max_col, tr_col, nt_col) in PROP_COLS.items():
                        try:
                            price_map[d][pt] = {
                                'avg':   float(row[avg_col]),
                                'min':   float(row[min_col]),
                                'max':   float(row[max_col]),
                                'trend': _parse_trend(row.get(tr_col, 0)),
                                'notes': row.get(nt_col, ''),
                            }
                        except (ValueError, KeyError):
                            pass
            self.stdout.write(f'Loaded {len(gov_map)} delegations from delegations.csv')

        # ── 2. Build DelegationPriceData rows from CSV ────────────────────────
        self.stdout.write('Rebuilding DelegationPriceData from delegations.csv…')
        DelegationPriceData.objects.all().delete()
        pd_rows = []
        for deleg, props in price_map.items():
            gov = gov_map.get(deleg, '')
            for pt, vals in props.items():
                pd_rows.append(DelegationPriceData(
                    delegation_name=deleg,
                    governorate=gov,
                    property_type=pt,
                    price_min=vals['min'],
                    price_avg=vals['avg'],
                    price_max=vals['max'],
                    annual_trend_pct=vals['trend'],
                    notes=vals['notes'],
                ))
        DelegationPriceData.objects.bulk_create(pd_rows, batch_size=500)
        self.stdout.write(f'  Inserted {len(pd_rows)} DelegationPriceData rows.')

        # ── 3. Generate DelegationForecast rows ───────────────────────────────
        forecast_rows = []
        model_version = 'csv_v2'

        if not use_csv and model_path.exists():
            # Try ML model inference
            forecast_rows, model_version = self._run_ml(
                model_path, gov_map, price_map, prop_type
            )

        if not forecast_rows:
            # Fallback: pre-computed forecast_table_h12.csv (apartment only)
            self.stdout.write('Using pre-computed forecast_table_h12.csv…')
            forecast_rows, model_version = self._load_csv_table(gov_map)

        if not forecast_rows:
            # Final fallback: compound-growth from delegations.csv for all 4 types
            self.stdout.write('Falling back to compound-growth generation from delegations.csv…')
            forecast_rows, model_version = self._compound_growth(price_map, gov_map)

        self.stdout.write(f'Clearing old DelegationForecast rows…')
        DelegationForecast.objects.all().delete()
        DelegationForecast.objects.bulk_create(forecast_rows, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f'Done — {len(pd_rows)} price rows + {len(forecast_rows)} forecast rows '
            f'(model_version={model_version}).'
        ))

    # ── ML inference path ─────────────────────────────────────────────────────
    def _run_ml(self, model_path, gov_map, price_map, prop_type):
        try:
            import joblib
        except ImportError:
            self.stderr.write('joblib not installed; skipping ML path.')
            return [], 'csv_v2'

        from forecast.models import DelegationForecast

        self.stdout.write(f'Loading model from {model_path}…')
        artifact = joblib.load(model_path)
        model        = artifact['model']
        feature_cols = artifact['feature_cols']
        target_cols  = artifact['target_cols']
        horizons     = artifact.get('horizons', 12)

        if not _ENG_FEAT.exists():
            self.stderr.write(f'engineered_features.csv not found at {_ENG_FEAT}')
            return [], 'csv_v2'

        eng = pd.read_csv(_ENG_FEAT, low_memory=False)

        # Filter to latest available month per delegation/property_type
        time_col = next((c for c in ('month', 'date', 'year_month') if c in eng.columns), None)
        if time_col:
            eng[time_col] = pd.to_datetime(eng[time_col], errors='coerce')
            eng = eng.sort_values(time_col)
            latest = eng.groupby([c for c in ('delegation', 'governorate', 'property_type') if c in eng.columns]).tail(1)
        else:
            latest = eng

        # Filter for requested property type if column exists
        if 'property_type' in latest.columns and prop_type:
            sub = latest[latest['property_type'] == prop_type]
            if sub.empty:
                sub = latest
        else:
            sub = latest

        avail_feats = [c for c in feature_cols if c in sub.columns]
        if not avail_feats:
            self.stderr.write('No feature columns found in engineered_features.csv')
            return [], 'csv_v2'

        missing = [c for c in feature_cols if c not in sub.columns]
        if missing:
            self.stdout.write(f'  Missing features (will be filled with 0): {missing[:5]}')
        X = sub.reindex(columns=feature_cols, fill_value=0)
        X = X.fillna(0)

        preds = model.predict(X)   # shape (n_delegations, horizons)
        self.stdout.write(f'  Inference complete: {preds.shape}')

        rows = []
        for i, (_, row_data) in enumerate(sub.iterrows()):
            del_name = (str(row_data.get('delegation') or row_data.get('delegation_id') or '')).strip()
            if not del_name:
                continue
            gov = gov_map.get(del_name, str(row_data.get('governorate', '')))
            for h in range(1, horizons + 1):
                pred_val = float(preds[i, h - 1]) if h <= preds.shape[1] else 0
                # Values from model are in same units as training price_col (assumed millimes)
                rows.append(DelegationForecast(
                    delegation_name=del_name,
                    governorate=gov,
                    property_type=prop_type,
                    forecast_origin=FORECAST_ORIGIN,
                    forecast_month=_add_months(FORECAST_ORIGIN, h - 1),
                    horizon_idx=h,
                    predicted_price_per_m2=abs(pred_val),
                    model_mape_pct=artifact.get('train_mape', 2.50),
                    model_version='ml_histgbt_v1',
                ))

        self.stdout.write(f'  Built {len(rows)} ML forecast rows for property_type={prop_type}.')
        return rows, 'ml_histgbt_v1'

    # ── Pre-computed CSV table path ───────────────────────────────────────────
    def _load_csv_table(self, gov_map):
        from forecast.models import DelegationForecast

        if not _TABLE_CSV.exists():
            self.stderr.write(f'forecast_table_h12.csv not found at {_TABLE_CSV}')
            return [], 'csv_v2'

        rows = []
        with open(_TABLE_CSV, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                del_name = (row.get('delegation_id') or row.get('delegation') or '').strip()
                if not del_name:
                    continue
                try:
                    horizon_idx = int(row.get('horizon_idx') or row.get('horizon') or 0)
                    pred_val    = float(row.get('predicted_price_per_m2') or 0)
                    forecast_m  = row.get('forecast_month') or row.get('forecast_date') or ''
                except (ValueError, TypeError):
                    continue

                origin_str = row.get('forecast_origin_month') or str(FORECAST_ORIGIN)
                try:
                    origin = date.fromisoformat(origin_str[:10])
                except ValueError:
                    origin = FORECAST_ORIGIN
                try:
                    fm = date.fromisoformat(forecast_m[:10])
                except ValueError:
                    fm = _add_months(FORECAST_ORIGIN, horizon_idx - 1)

                gov = gov_map.get(del_name, '')
                rows.append(DelegationForecast(
                    delegation_name=del_name,
                    governorate=gov,
                    property_type='apartment',  # CSV table is apartment-only
                    forecast_origin=origin,
                    forecast_month=fm,
                    horizon_idx=horizon_idx,
                    predicted_price_per_m2=abs(pred_val),
                    model_mape_pct=2.92,
                    model_version='ml_histgbt_h12',
                ))

        self.stdout.write(f'  Loaded {len(rows)} rows from forecast_table_h12.csv.')
        return rows, 'ml_histgbt_h12'

    # ── Compound-growth fallback ───────────────────────────────────────────────
    def _compound_growth(self, price_map, gov_map):
        from forecast.models import DelegationForecast

        rows = []
        for deleg, props in price_map.items():
            gov = gov_map.get(deleg, '')
            for pt, vals in props.items():
                mf = (1 + vals['trend'] / 100) ** (1 / 12)
                for h in range(1, 13):
                    price_tnd = vals['avg'] * (mf ** (h - 1))
                    rows.append(DelegationForecast(
                        delegation_name=deleg,
                        governorate=gov,
                        property_type=pt,
                        forecast_origin=FORECAST_ORIGIN,
                        forecast_month=_add_months(FORECAST_ORIGIN, h - 1),
                        horizon_idx=h,
                        predicted_price_per_m2=price_tnd * 1000,
                        model_mape_pct=2.50,
                        model_version='csv_v2',
                    ))
        self.stdout.write(f'  Built {len(rows)} compound-growth rows.')
        return rows, 'csv_v2'
