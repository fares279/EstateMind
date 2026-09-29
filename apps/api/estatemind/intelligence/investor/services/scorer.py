"""
Model inference chains.

Scanner chain (listing analysis):  M1 → M3 → M2 → M4 → M5
Portfolio chain (asset scoring):   M2 → M6 → M7
"""
import logging
import numpy as np
import pandas as pd

from .market_rent import market_rent_per_m2
from .registry import REGISTRY
from .zone_data import get_zone_stats, get_zone_forecast, real_zone_stats
from .scoring_method import describe
from .feature_builder import (
    build_scanner_features_m1, build_scanner_features_m2,
    build_scanner_features_m3, build_scanner_features_m4,
    build_scanner_features_m5, build_portfolio_features_m2,
    build_portfolio_features_m6, build_portfolio_features_m7,
)

logger = logging.getLogger(__name__)

_UNDERVAL_LABELS = {0: 'SEVERELY_UNDERVALUED', 1: 'UNDERVALUED', 2: 'FAIRLY_PRICED', 3: 'OVERPRICED'}

# Share of gross rent lost to vacancy (8.3%), management (8%) and maintenance (0.5%):
# the same assumptions as the IRR calculator. Net yield used to be gross - 2 points.
OPERATING_COST_SHARE = 0.168
HOLDING_YEARS = 10
EXIT_COST_SHARE = 0.04


def net_of_costs(gross_yield_pct: float) -> float:
    return gross_yield_pct * (1 - OPERATING_COST_SHARE)


def forecast_block(fcst: dict) -> dict:
    """The forecast as shown to users: figures only when a forecast exists."""
    if not fcst.get('forecast_available'):
        return {'available': False, 'source': None, 'direction': None,
                'forecast_6m_pct': None, 'forecast_12m_pct': None, 'low_12m_pct': None, 'high_12m_pct': None}
    r = lambda v: round(v, 1) if v is not None else None  # noqa: E731
    return {'available': True, 'source': fcst.get('forecast_source'), 'direction': fcst.get('forecast_direction'),
            'forecast_6m_pct': r(fcst.get('forecast_6m_pct')), 'forecast_12m_pct': r(fcst.get('forecast_12m_pct')),
            'low_12m_pct': r(fcst.get('forecast_12m_low_pct')), 'high_12m_pct': r(fcst.get('forecast_12m_high_pct'))}


def forward_irr(value_tnd: float, annual_net_rent_tnd: float, growth_pct: float,
                years: int = HOLDING_YEARS) -> float:
    """Unlevered IRR of holding for `years` from today's value: net rent each year
    (flat), then a sale at value x (1 + growth)^years less exit costs."""
    from . import IRRCalculatorService

    flows = [-value_tnd] + [annual_net_rent_tnd] * years
    flows[-1] += value_tnd * (1 + growth_pct / 100) ** years * (1 - EXIT_COST_SHARE)
    return IRRCalculatorService._compute_irr_newton(flows) * 100
_GRADE_LABELS    = {0: 'D', 1: 'C', 2: 'B', 3: 'A'}


def _to_df(features: dict, feature_names: list) -> pd.DataFrame:
    row = {}
    for f in feature_names:
        row[f] = features.get(f, 0.0)
    df = pd.DataFrame([row])
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    return df


def _predict(model_name: str, features: dict) -> np.ndarray | None:
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


def _predict_proba(model_name: str, features: dict) -> np.ndarray | None:
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
    Full scanner chain: M1 → M3 → M2 → M4 → M5.
    inp keys: listing_price_tnd, surface_m2, property_type, governorate,
              delegation, room_count, floor_level, days_active,
              repost_count, price_reduction_count, seller_type,
              has_parking, has_garden, has_pool, sea_view, elevator,
              photo_quality, listing_quality
    """
    gov   = inp.get('governorate', 'Tunis')
    deleg = inp.get('delegation', '')
    ptype = inp.get('property_type', 'apartment')

    zone = get_zone_stats(deleg, ptype)
    fcst = get_zone_forecast(deleg, ptype)

    price    = float(inp.get('listing_price_tnd', 200000))
    surface  = float(inp.get('surface_m2', 100))
    zone_avg = zone.get('avg_price_per_m2_tnd', 1500.0)
    fair_value = zone_avg * surface
    price_gap_pct = (price - fair_value) / max(fair_value, 1) * 100

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
        # Rule-based: follow the price gap to the zone average. This used to return
        # FAIRLY_PRICED with fixed 60% 'probabilities' whatever the price.
        underval_label = ('SEVERELY_UNDERVALUED' if price_gap_pct <= -35 else
                          'UNDERVALUED' if price_gap_pct <= -15 else
                          'OVERPRICED' if price_gap_pct >= 15 else 'FAIRLY_PRICED')
        proba_undervalued = {'SEVERELY_UNDERVALUED': 0.85, 'UNDERVALUED': 0.65,
                             'FAIRLY_PRICED': 0.25, 'OVERPRICED': 0.05}[underval_label]
        underval_probas   = None  # no model, so no probabilities

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
    rent_pm2, rent_basis = market_rent_per_m2(deleg, gov, ptype)
    if yield_pred is not None:
        gross_yield = float(np.clip(float(np.array(yield_pred).flatten()[0]), 1.0, 25.0))
        yield_basis = 'model'
        monthly_rent = price * gross_yield / 100 / 12
    elif rent_pm2:
        # market rent (median of real rental listings) x surface, then yield = rent / price.
        # The rent used to be derived from the price and an assumed yield (circular).
        monthly_rent = rent_pm2 * surface
        gross_yield = monthly_rent * 12 / max(price, 1) * 100
        yield_basis = f'market_rent_{rent_basis}'
    else:
        ppm2   = price / max(surface, 1)
        gross_yield = 8.0 if ppm2 < 2000 else (6.5 if ppm2 < 3500 else 5.5)
        monthly_rent = price * gross_yield / 100 / 12
        yield_basis = 'assumed'  # no rent data for this area: a typical yield, not a measurement

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

    return {
        'undervaluation': {
            'label':              underval_label,
            'probabilities':      underval_probas,
            'method':             'model' if underval_probas is not None else 'rule_based_price_gap',
            'proba_undervalued':  round(proba_undervalued, 3),
        },
        'buy_signal': {
            'signal':  buy_signal,
            'p_buy':   round(p_buy, 3),
        },
        'yield': {
            'gross_yield_pct': round(gross_yield, 2),
            'net_yield_pct':   round(net_of_costs(gross_yield), 2),
            'monthly_rent_est': round(monthly_rent),
            'basis':           yield_basis,
            'rent_per_m2':     round(rent_pm2, 2) if rent_pm2 and yield_basis.startswith('market_rent') else None,
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
        'forecast': forecast_block(fcst),
        # measured from real listings; the zone CSV's demand, vacancy and days-on-market
        # columns hold one constant value for every delegation, so they are not shown
        'zone': real_zone_stats(deleg, ptype),
        **describe(REGISTRY.available()),
    }


# ── Portfolio chain ───────────────────────────────────────────────────────────

def score_asset(asset: dict) -> dict:
    """
    Portfolio asset scoring chain: M2 -> M6 -> M7 (rule-based when the models are absent).
    asset keys: same as PortfolioAsset fields + holding_days, unrealized_gain_tnd, etc.

    Yield: the owner's rent when given, else the market rent of real rental listings;
    without either, no yield is reported (it used to default to 6%).
    Return: forward-looking IRR over HOLDING_YEARS from today's value, for the
    forecast's central, low and high 12-month growth (it used to be the asset's past
    appreciation plus yield, and the three scenarios were not computed).
    """
    gov   = asset.get('governorate', 'Tunis')
    deleg = asset.get('delegation', '')
    ptype = asset.get('property_type', 'apartment')

    zone = get_zone_stats(deleg, ptype)
    fcst = get_zone_forecast(deleg, ptype)

    price   = float(asset.get('acquisition_price_tnd') or 0) or 1.0
    cur_val = float(asset.get('current_value_tnd') or price)
    surface = float(asset.get('surface_m2') or 0)
    rent_mo = float(asset.get('monthly_rent_tnd') or 0)
    opex_mo = float(asset.get('monthly_opex_tnd') or 0)

    # ── Model 2: Rental yield ────────────────────────────────────────────────
    f2 = build_portfolio_features_m2(asset, zone, fcst)
    yield_pred = _predict('rental_yield', f2)
    rent_basis = None
    if yield_pred is not None:
        gross_yield = float(np.clip(float(np.array(yield_pred).flatten()[0]), 1.0, 25.0))
        rent_mo_est, rent_basis = cur_val * gross_yield / 100 / 12, 'model'
    elif rent_mo > 0:
        rent_mo_est, rent_basis = rent_mo, 'your_rent'
    else:
        rent_pm2, basis = market_rent_per_m2(deleg, gov, ptype)
        rent_mo_est = rent_pm2 * surface if rent_pm2 and surface else None
        rent_basis = f'market_rent_{basis}' if rent_mo_est else None
    gross_yield = rent_mo_est * 12 / cur_val * 100 if rent_mo_est else None
    if rent_basis == 'your_rent' and opex_mo:
        net_yield = (rent_mo - opex_mo) * 12 / cur_val * 100
    else:
        net_yield = net_of_costs(gross_yield) if gross_yield is not None else None

    # ── Model 6: forward IRR, three growth scenarios ─────────────────────────
    f6 = build_portfolio_features_m6(asset, zone, fcst, gross_yield or 0.0)
    irr_pred = _predict('irr_predictor', f6)
    irr = {'irr_pct': None, 'irr_low_pct': None, 'irr_high_pct': None, 'basis': None,
           'holding_years': HOLDING_YEARS}
    if irr_pred is not None:
        irr_pct = float(np.clip(float(np.array(irr_pred).flatten()[0]), -5.0, 50.0))
        irr.update(irr_pct=round(irr_pct, 2), basis='model')
    elif net_yield is not None and fcst.get('forecast_available'):
        annual_net = cur_val * net_yield / 100
        base, low, high = (fcst['forecast_12m_pct'], fcst.get('forecast_12m_low_pct'),
                           fcst.get('forecast_12m_high_pct'))
        irr.update(
            irr_pct=round(forward_irr(cur_val, annual_net, base), 2),
            irr_low_pct=round(forward_irr(cur_val, annual_net, base if low is None else low), 2),
            irr_high_pct=round(forward_irr(cur_val, annual_net, base if high is None else high), 2),
            basis='net_yield_and_forecast',
        )
    irr['annualized_return'] = irr['irr_pct']

    # ── Model 7: Portfolio risk scorer ───────────────────────────────────────
    f7 = build_portfolio_features_m7(asset, zone, fcst, gross_yield or 0.0)
    risk_pred = _predict('portfolio_risk_scorer', f7)
    if risk_pred is not None:
        risk_score = float(np.clip(float(np.array(risk_pred).flatten()[0]), 0.0, 100.0))
    else:
        # rule: lower yield and a falling forecast mean more risk
        y = gross_yield if gross_yield is not None else 5.0
        g = fcst.get('forecast_12m_pct', 0.0) if fcst.get('forecast_available') else 0.0
        risk_score = float(np.clip(40.0 + (1.0 - min(y / 10.0, 1.0)) * 20.0 - g, 0.0, 100.0))
    risk_level = 'Low' if risk_score < 35 else ('Medium' if risk_score < 65 else 'High')

    # Investment grade based on combined signals
    composite = (max(0.0, irr['irr_pct'] or 0.0) * 3 + (gross_yield or 0.0) * 5 - risk_score * 0.3 + 10)
    grade = 'A' if composite >= 70 else 'B' if composite >= 50 else 'C' if composite >= 30 else 'D'

    r = lambda v, n=2: round(v, n) if v is not None else None  # noqa: E731
    return {
        'yield': {
            'gross_yield_pct':  r(gross_yield),
            'net_yield_pct':    r(net_yield),
            'monthly_rent_est': r(rent_mo_est, 0),
            'monthly_net_cf':   round(rent_mo - opex_mo),
            'basis':            rent_basis,
        },
        'irr': irr,
        'risk': {
            'risk_score':  round(risk_score, 1),
            'risk_level':  risk_level,
        },
        'grade':              grade,
        'current_value_tnd':  round(cur_val),
        'unrealized_gain_tnd': round(cur_val - price),
        'unrealized_gain_pct': round((cur_val - price) / max(price, 1) * 100, 2),
        'forecast': forecast_block(fcst),
    }


def score_portfolio(assets: list) -> dict:
    """Score all portfolio assets and compute portfolio-level metrics."""
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
        if result['yield']['gross_yield_pct'] is not None:
            yields.append(result['yield']['gross_yield_pct'])
        if result['irr']['irr_pct'] is not None:
            irrs.append(result['irr']['irr_pct'])
        risk_scores.append(result['risk']['risk_score'])
        grades.append(result['grade'])
        scored.append({'asset': asset, 'score': result})

    n = len(assets)
    avg_yield    = sum(yields) / len(yields) if yields else None
    avg_irr      = sum(irrs) / len(irrs) if irrs else None
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
            'avg_gross_yield_pct': round(avg_yield, 2) if avg_yield is not None else None,
            'avg_irr_pct':         round(avg_irr, 2) if avg_irr is not None else None,
            'avg_risk_score':      round(avg_risk, 1),
            'grade_distribution':  grade_counts,
        },
    }
