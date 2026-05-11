"""
Model inference chains.

Scanner chain (listing analysis):  M1 → M3 → M2 → M4 → M5
Portfolio chain (asset scoring):   M2 → M6 → M7
"""
import logging

logger = logging.getLogger(__name__)

_UNDERVAL_LABELS = {0: 'SEVERELY_UNDERVALUED', 1: 'UNDERVALUED', 2: 'FAIRLY_PRICED', 3: 'OVERPRICED'}
_GRADE_LABELS    = {0: 'D', 1: 'C', 2: 'B', 3: 'A'}


def _to_df(features: dict, feature_names: list):
    """Convert features dict to pandas DataFrame (lazy pandas import)."""
    import pandas as pd
    row = {}
    for f in feature_names:
        row[f] = features.get(f, 0.0)
    df = pd.DataFrame([row])
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    return df


def _predict(model_name: str, features: dict):
    """Predict using model (lazy registry import)."""
    from .registry import REGISTRY
    model = REGISTRY.model(model_name)
    if model is None:
        return None
    feat_names = REGISTRY.features(model_name)
    df = _to_df(features, feat_names)
    try:
        return model.predict(df)
    except Exception as e:
        logger.warning("Model %s predict failed: %s", model_name, e)
        return None


def _predict_proba(model_name: str, features: dict):
    """Predict probabilities using model (lazy registry and numpy imports)."""
    from .registry import REGISTRY
    model = REGISTRY.model(model_name)
    if model is None:
        return None
    feat_names = REGISTRY.features(model_name)
    df = _to_df(features, feat_names)
    try:
        if hasattr(model, 'predict_proba'):
            return model.predict_proba(df)
        return model.predict(df)
    except Exception as e:
        logger.warning("Model %s predict_proba failed: %s", model_name, e)
        return None


# ── Scanner chain ────────────────────────────────────────────────────────────

def score_listing(inp: dict) -> dict:
    """
    Full scanner chain: M1 → M3 → M2 → M4 → M5 (lazy imports).
    inp keys: listing_price_tnd, surface_m2, property_type, governorate,
              delegation, room_count, floor_level, days_active,
              repost_count, price_reduction_count, seller_type,
              has_parking, has_garden, has_pool, sea_view, elevator,
              photo_quality, listing_quality
    """
    import numpy as np
    from .zone_data import get_zone_stats, get_zone_forecast
    from .feature_builder import (
        build_scanner_features_m1, build_scanner_features_m2,
        build_scanner_features_m3, build_scanner_features_m4,
        build_scanner_features_m5,
    )
    from .registry import REGISTRY
    
    gov   = inp.get('governorate', 'Tunis')
    deleg = inp.get('delegation', '')
    ptype = inp.get('property_type', 'apartment')

    zone = get_zone_stats(deleg, ptype)
    fcst = get_zone_forecast(deleg, ptype)

    # ── Model 1: Undervaluation detector ────────────────────────────────────
    f1 = build_scanner_features_m1(inp, zone, fcst)
    proba_arr = _predict_proba('undervaluation_detector', f1)
    if proba_arr is not None:
        proba_arr = np.array(proba_arr).flatten()
        if len(proba_arr) >= 4:
            probas = proba_arr[:4]
        else:
            probas = np.array([0.05, 0.20, 0.60, 0.15])
        pred_class = int(np.argmax(probas))
        underval_label = _UNDERVAL_LABELS.get(pred_class, 'FAIRLY_PRICED')
        proba_undervalued = float(probas[0] + probas[1])
        underval_probas   = {
            'SEVERELY_UNDERVALUED': round(float(probas[0]), 3),
            'UNDERVALUED':          round(float(probas[1]), 3),
            'FAIRLY_PRICED':        round(float(probas[2]), 3),
            'OVERPRICED':           round(float(probas[3]), 3),
        }
    else:
        underval_label    = 'FAIRLY_PRICED'
        proba_undervalued = 0.25
        underval_probas   = {'SEVERELY_UNDERVALUED': 0.05, 'UNDERVALUED': 0.20, 'FAIRLY_PRICED': 0.60, 'OVERPRICED': 0.15}

    # ── Model 3: Buy/Wait ────────────────────────────────────────────────────
    f3 = build_scanner_features_m3(inp, zone, fcst, proba_undervalued)
    bw_proba = _predict_proba('buy_wait_classifier', f3)
    if bw_proba is not None:
        bw_arr = np.array(bw_proba).flatten()
        if len(bw_arr) >= 2:
            p_buy = float(bw_arr[-1])  # last class = BUY_NOW
        else:
            p_buy = float(bw_arr[0])
    else:
        p_buy = 0.5 + proba_undervalued * 0.3
    p_buy = float(np.clip(p_buy, 0.0, 1.0))
    buy_signal = 'BUY_NOW' if p_buy >= 0.55 else 'WAIT'

    # ── Model 2: Rental yield ────────────────────────────────────────────────
    f2 = build_scanner_features_m2(inp, zone, fcst)
    yield_pred = _predict('rental_yield', f2)
    if yield_pred is not None:
        gross_yield = float(np.clip(float(np.array(yield_pred).flatten()[0]), 1.0, 25.0))
    else:
        price  = float(inp.get('listing_price_tnd', 200000))
        ppm2   = price / max(float(inp.get('surface_m2', 100)), 1)
        gross_yield = 8.0 if ppm2 < 2000 else (6.5 if ppm2 < 3500 else 5.5)

    # ── Model 4: Opportunity score ───────────────────────────────────────────
    f4 = build_scanner_features_m4(inp, zone, fcst, proba_undervalued, gross_yield, p_buy)
    opp_pred = _predict('opportunity_score_engine', f4)
    if opp_pred is not None:
        opp_score = float(np.clip(float(np.array(opp_pred).flatten()[0]), 0.0, 100.0))
    else:
        opp_score = (proba_undervalued * 40 + p_buy * 30 + min(gross_yield * 3, 30))

    # ── Model 5: Investment grade ────────────────────────────────────────────
    f5 = build_scanner_features_m5(inp, zone, fcst, proba_undervalued, gross_yield, p_buy, opp_score)
    grade_proba = _predict_proba('investment_grade_classifier', f5)
    if grade_proba is not None:
        ga = np.array(grade_proba).flatten()
        if len(ga) >= 4:
            investment_grade = _GRADE_LABELS.get(int(np.argmax(ga[:4])), 'C')
        else:
            investment_grade = _GRADE_LABELS.get(int(np.argmax(ga)), 'C')
    else:
        if opp_score >= 75:    investment_grade = 'A'
        elif opp_score >= 55:  investment_grade = 'B'
        elif opp_score >= 35:  investment_grade = 'C'
        else:                  investment_grade = 'D'

    # ── Price estimation ─────────────────────────────────────────────────────
    price    = float(inp.get('listing_price_tnd', 200000))
    surface  = float(inp.get('surface_m2', 100))
    zone_avg = zone.get('avg_price_per_m2_tnd', 1500.0)
    fair_value = zone_avg * surface
    price_gap_pct = (price - fair_value) / max(fair_value, 1) * 100

    return {
        'undervaluation': {
            'label':              underval_label,
            'probabilities':      underval_probas,
            'proba_undervalued':  round(proba_undervalued, 3),
        },
        'buy_signal': {
            'signal':  buy_signal,
            'p_buy':   round(p_buy, 3),
        },
        'yield': {
            'gross_yield_pct': round(gross_yield, 2),
            'net_yield_pct':   round(max(0.0, gross_yield - 2.0), 2),
            'monthly_rent_est': round(price * gross_yield / 100 / 12),
        },
        'opportunity_score': round(opp_score, 1),
        'investment_grade':  investment_grade,
        'pricing': {
            'listing_price_tnd': price,
            'fair_value_est_tnd': round(fair_value),
            'price_gap_pct':     round(price_gap_pct, 1),
            'zone_avg_pm2':      round(zone_avg, 0),
            'listing_pm2':       round(price / max(surface, 1), 0),
        },
        'forecast': {
            'direction':     fcst.get('forecast_direction', 'UP'),
            'forecast_6m_pct': round(fcst.get('forecast_6m_pct', 3.5), 1),
            'forecast_12m_pct': round(fcst.get('forecast_12m_pct', 6.0), 1),
            'reliability':   round(fcst.get('forecast_reliability', 0.6), 2),
        },
        'zone': {
            'demand_intensity':    round(zone.get('demand_intensity_score', 60.0), 1),
            'supply_demand_ratio': round(zone.get('supply_demand_ratio', 1.0), 2),
            'vacancy_rate_pct':    round(zone.get('vacancy_rate_pct', 7.0), 1),
            'median_dom':          round(zone.get('median_days_on_market', 45.0), 0),
        },
        'models_used': REGISTRY.available(),
    }


# ── Portfolio chain ───────────────────────────────────────────────────────────

def score_asset(asset: dict) -> dict:
    """
    Portfolio asset scoring chain: M2 → M6 → M7 (lazy imports).
    asset keys: same as PortfolioAsset fields + holding_days, unrealized_gain_tnd, etc.
    """
    import numpy as np
    from .zone_data import get_zone_stats, get_zone_forecast
    from .feature_builder import (
        build_portfolio_features_m2,
        build_portfolio_features_m6,
        build_portfolio_features_m7,
    )
    
    gov   = asset.get('governorate', 'Tunis')
    deleg = asset.get('delegation', '')
    ptype = asset.get('property_type', 'apartment')

    zone = get_zone_stats(deleg, ptype)
    fcst = get_zone_forecast(deleg, ptype)

    # ── Model 2: Rental yield ────────────────────────────────────────────────
    f2 = build_portfolio_features_m2(asset, zone, fcst)
    yield_pred = _predict('rental_yield', f2)
    price = float(asset.get('acquisition_price_tnd', 200000))
    if yield_pred is not None:
        gross_yield = float(np.clip(float(np.array(yield_pred).flatten()[0]), 1.0, 25.0))
    else:
        rent_mo  = float(asset.get('monthly_rent_tnd', 0))
        gross_yield = (rent_mo * 12 / max(price, 1) * 100) if rent_mo > 0 else 6.0

    # ── Model 6: IRR predictor ───────────────────────────────────────────────
    f6 = build_portfolio_features_m6(asset, zone, fcst, gross_yield)
    irr_pred = _predict('irr_predictor', f6)
    if irr_pred is not None:
        irr_pct = float(np.clip(float(np.array(irr_pred).flatten()[0]), -5.0, 50.0))
    else:
        hold_years = float(asset.get('holding_days', 365)) / 365.25
        cur_val    = float(asset.get('current_value_tnd') or price)
        apprec_ann = ((cur_val / max(price, 1)) ** (1 / max(hold_years, 1)) - 1) * 100
        irr_pct    = apprec_ann + max(0.0, gross_yield - 2.0)

    # ── Model 7: Portfolio risk scorer ───────────────────────────────────────
    f7 = build_portfolio_features_m7(asset, zone, fcst, gross_yield)
    risk_pred = _predict('portfolio_risk_scorer', f7)
    if risk_pred is not None:
        risk_score = float(np.clip(float(np.array(risk_pred).flatten()[0]), 0.0, 100.0))
    else:
        risk_score = 40.0 + (1.0 - min(gross_yield / 10.0, 1.0)) * 20.0

    cur_val    = float(asset.get('current_value_tnd') or price)
    rent_mo    = float(asset.get('monthly_rent_tnd', 0))
    opex_mo    = float(asset.get('monthly_opex_tnd', 0))
    net_cf_mo  = rent_mo - opex_mo
    net_yield  = max(0.0, gross_yield - 2.0)

    risk_level = 'Low' if risk_score < 35 else ('Medium' if risk_score < 65 else 'High')

    # Investment grade based on combined signals
    composite = (max(0.0, irr_pct) * 3 + gross_yield * 5 - risk_score * 0.3 + 10)
    if composite >= 70:   grade = 'A'
    elif composite >= 50: grade = 'B'
    elif composite >= 30: grade = 'C'
    else:                 grade = 'D'

    return {
        'yield': {
            'gross_yield_pct':  round(gross_yield, 2),
            'net_yield_pct':    round(net_yield, 2),
            'monthly_rent_est': round(price * gross_yield / 100 / 12),
            'monthly_net_cf':   round(net_cf_mo),
        },
        'irr': {
            'irr_pct':        round(irr_pct, 2),
            'annualized_return': round(irr_pct, 2),
        },
        'risk': {
            'risk_score':  round(risk_score, 1),
            'risk_level':  risk_level,
        },
        'grade':              grade,
        'current_value_tnd':  round(cur_val),
        'unrealized_gain_tnd': round(cur_val - price),
        'unrealized_gain_pct': round((cur_val - price) / max(price, 1) * 100, 2),
        'forecast': {
            'forecast_6m_pct':  round(fcst.get('forecast_6m_pct', 3.5), 1),
            'forecast_12m_pct': round(fcst.get('forecast_12m_pct', 6.0), 1),
            'direction':        fcst.get('forecast_direction', 'UP'),
        },
    }


def score_portfolio(assets: list) -> dict:
    """Score all portfolio assets and compute portfolio-level metrics (lazy imports)."""
    import numpy as np
    
    if not assets:
        return {'assets': [], 'summary': {}}

    scored = []
    total_value   = 0.0
    total_cost    = 0.0
    total_gain    = 0.0
    yields        = []
    irrs          = []
    risk_scores   = []
    grades        = []

    for asset in assets:
        result = score_asset(asset)
        total_value += float(asset.get('current_value_tnd') or asset.get('acquisition_price_tnd', 0))
        total_cost  += float(asset.get('acquisition_price_tnd', 0))
        total_gain  += result['unrealized_gain_tnd']
        yields.append(result['yield']['gross_yield_pct'])
        irrs.append(result['irr']['irr_pct'])
        risk_scores.append(result['risk']['risk_score'])
        grades.append(result['grade'])
        scored.append({'asset': asset, 'score': result})

    n = len(assets)
    avg_yield    = sum(yields) / n
    avg_irr      = sum(irrs) / n
    avg_risk     = sum(risk_scores) / n
    total_return = (total_value - total_cost) / max(total_cost, 1) * 100

    grade_counts = {g: grades.count(g) for g in ['A', 'B', 'C', 'D']}

    return {
        'assets': scored,
        'summary': {
            'total_assets':        n,
            'total_value_tnd':     round(total_value),
            'total_cost_tnd':      round(total_cost),
            'total_gain_tnd':      round(total_gain),
            'total_return_pct':    round(total_return, 2),
            'avg_gross_yield_pct': round(avg_yield, 2),
            'avg_irr_pct':         round(avg_irr, 2),
            'avg_risk_score':      round(avg_risk, 1),
            'grade_distribution':  grade_counts,
        },
    }
