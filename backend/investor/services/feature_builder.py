"""
Builds feature vectors for each of the 7 investor models
from simplified user input + zone data + macro defaults.
"""
import math
from .zone_data import get_zone_stats, get_zone_forecast, MACRO

_PTYPE_CODE = {'apartment': 0, 'house': 1, 'villa': 1, 'commercial': 2, 'office': 2, 'land': 3}

_GOV_LIST = [
    'ariana', 'béja', 'beja', 'ben arous', 'bizerte', 'gabès', 'gabes',
    'gafsa', 'jendouba', 'kairouan', 'kasserine', 'kébili', 'kebili',
    'la manouba', 'manouba', 'le kef', 'kef', 'mahdia', 'médenine', 'medenine',
    'monastir', 'nabeul', 'sfax', 'sidi bouzid', 'siliana', 'sousse',
    'tataouine', 'tozeur', 'tunis', 'zaghouan',
]

_DELEG_LIST = None  # lazy loaded


def _gov_code(gov: str) -> float:
    key = gov.lower().strip()
    try:
        return float(_GOV_LIST.index(key))
    except ValueError:
        return 14.0  # median fallback


def _deleg_code(deleg: str) -> float:
    global _DELEG_LIST
    if _DELEG_LIST is None:
        try:
            from pathlib import Path
            import csv
            csv_path = Path(__file__).resolve().parents[4] / 'delegations' / 'delegations.csv'
            with open(csv_path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                _DELEG_LIST = sorted(set(row.get('delegation', '').lower().strip() for row in reader))
        except Exception:
            _DELEG_LIST = []
    key = deleg.lower().strip()
    try:
        return float(_DELEG_LIST.index(key))
    except ValueError:
        return float(len(_DELEG_LIST) // 2)


def _surface_category(m2: float) -> float:
    if m2 < 50:   return 0.0
    if m2 < 80:   return 1.0
    if m2 < 120:  return 2.0
    if m2 < 200:  return 3.0
    return 4.0


def _amenity_score(inp: dict) -> float:
    score = 0.0
    if inp.get('has_parking'):  score += 0.5
    if inp.get('has_garden'):   score += 0.5
    if inp.get('has_pool'):     score += 1.0
    if inp.get('sea_view'):     score += 1.0
    if inp.get('elevator'):     score += 0.5
    return max(1.0, score)


def _floor_premium(floor: int) -> float:
    if floor <= 0: return 0.0
    if floor == 1: return 0.02
    if floor == 2: return 0.04
    return min(floor * 0.015, 0.10)


def build_scanner_features_m1(inp: dict, zone: dict, fcst: dict) -> dict:
    """Features for Model 1: undervaluation_detector (30 features)."""
    price      = float(inp.get('listing_price_tnd', 200000))
    surface    = float(inp.get('surface_m2', 100))
    ptype      = inp.get('property_type', 'apartment').lower()
    gov        = inp.get('governorate', 'Tunis')
    deleg      = inp.get('delegation', '')
    rooms      = float(inp.get('room_count', 3))
    floor      = int(inp.get('floor_level', 0))
    days       = float(inp.get('days_active', 15))
    repost     = float(inp.get('repost_count', 0))
    reductions = float(inp.get('price_reduction_count', 0))
    agency     = 1.0 if str(inp.get('seller_type', 'agency')).lower() == 'agency' else 0.0

    zone_avg_pm2 = zone.get('avg_price_per_m2_tnd', 1500.0)
    price_pm2    = price / max(surface, 1)
    price_gap    = (price_pm2 - zone_avg_pm2) / max(zone_avg_pm2, 1)
    pm2_dev      = price_gap
    percentile   = min(max(50.0 + price_gap * 50, 5.0), 95.0)
    within_ci    = 1.0 if abs(price_gap) < 0.15 else 0.0
    dom_ratio    = days / max(zone.get('median_days_on_market', 45), 1)
    freshness    = max(0.0, 1.0 - days / 90.0)
    room_density = rooms / max(surface, 1)
    amenity      = _amenity_score(inp)
    ptype_code   = float(_PTYPE_CODE.get(ptype, 0))
    surf_cat     = _surface_category(surface)
    gov_code     = _gov_code(gov)

    demand = zone.get('demand_intensity_score', 60.0)
    zone_trend = zone.get('price_change_yoy_pct', 6.0) / 100.0
    supply_demand = zone.get('supply_demand_ratio', 1.0)
    fcst_dir   = fcst.get('forecast_direction_code', 1.0)
    fcst_6m    = fcst.get('forecast_6m_pct', 3.5) / 100.0

    return {
        'f01_price_gap_ratio':   price_gap,
        'f02_pm2_zone_deviation':pm2_dev,
        'f03_price_percentile':  percentile,
        'f04_within_ci':         within_ci,
        'f05_dom_ratio':         dom_ratio,
        'f06_repost_count':      repost,
        'f07_reduction_count':   reductions,
        'f08_reduction_mag':     reductions * 0.03,
        'f09_listing_freshness': freshness,
        'f10_photo_quality':     float(inp.get('photo_quality', 5.0)),
        'f11_desc_sentiment':    0.5,
        'f12_promo_bias':        0.0,
        'f13_agency':            agency,
        'f14_demand_score':      demand,
        'f15_zone_demand_trend': zone_trend,
        'f16_supply_demand':     supply_demand,
        'f17_surface_cat':       surf_cat,
        'f18_ptype_enc':         ptype_code,
        'f19_room_density':      room_density,
        'f20_amenity_score':     amenity,
        'f21_proximity':         zone.get('avg_proximity_transport_km', 1.0),
        'f22_forecast_dir':      fcst_dir,
        'f23_forecast_6m':       fcst_6m,
        'f24_bct_rate':          MACRO['bct_benchmark_rate_pct'],
        'fx_climate_risk':       50.0,
        'fx_inflation':          MACRO['inflation_rate_cpi_pct'],
        'fx_mortgage_rate':      MACRO['avg_mortgage_rate_pct'],
        'fx_listing_quality':    float(inp.get('listing_quality', 5.0)),
        'fx_floor_premium':      _floor_premium(floor),
        'fx_gov_enc':            gov_code,
    }


def build_scanner_features_m3(inp: dict, zone: dict, fcst: dict, m1_proba_undervalued: float) -> dict:
    """Features for Model 3: buy_wait_classifier (17 features)."""
    price    = float(inp.get('listing_price_tnd', 200000))
    surface  = float(inp.get('surface_m2', 100))
    days     = float(inp.get('days_active', 15))
    repost   = float(inp.get('repost_count', 0))

    zone_avg_pm2 = zone.get('avg_price_per_m2_tnd', 1500.0)
    price_pm2    = price / max(surface, 1)
    price_gap    = (price_pm2 - zone_avg_pm2) / max(zone_avg_pm2, 1)
    percentile   = min(max(50.0 + price_gap * 50, 5.0), 95.0)
    dom_ratio    = days / max(zone.get('median_days_on_market', 45), 1)

    return {
        'f09_forecast_confidence':        fcst.get('forecast_confidence_code', 1.0),
        'f17_forecast_direction_encoded': fcst.get('forecast_direction_code', 1.0),
        'f01_price_gap_ratio':            price_gap,
        'f02_price_percentile_in_zone':   percentile,
        'f03_days_on_market_ratio':       dom_ratio,
        'f04_repost_count':               repost,
        'f05_zone_demand_trend':          zone.get('price_change_yoy_pct', 6.0) / 100.0,
        'f06_supply_demand_ratio':        zone.get('supply_demand_ratio', 1.0),
        'f07_demand_intensity_score':     zone.get('demand_intensity_score', 60.0),
        'f08_forecast_6m':                fcst.get('forecast_6m_pct', 3.5),
        'f10_trend_volatility_score':     fcst.get('trend_volatility_score', 25.0),
        'f11_macro_affordability_index':  1.0 - MACRO['avg_mortgage_rate_pct'] / 20.0,
        'f12_climate_risk_composite':     50.0,
        'f13_bct_rate_current':           MACRO['bct_benchmark_rate_pct'],
        'f14_inflation_rate_current':     MACRO['inflation_rate_cpi_pct'],
        'f15_mortgage_rate_avg_current':  MACRO['avg_mortgage_rate_pct'],
        'f16_undervaluation_proba':       m1_proba_undervalued,
    }


def build_scanner_features_m2(inp: dict, zone: dict, fcst: dict) -> dict:
    """Features for Model 2: rental_yield (25 features)."""
    surface  = float(inp.get('surface_m2', 100))
    rooms    = float(inp.get('room_count', 3))
    floor    = float(inp.get('floor_level', 0))
    ptype    = inp.get('property_type', 'apartment').lower()
    gov      = inp.get('governorate', 'Tunis')
    price    = float(inp.get('listing_price_tnd', 200000))

    return {
        'f01_surface_area':             surface,
        'f02_room_count':               rooms,
        'f03_room_density':             rooms / max(surface, 1),
        'f04_floor_level':              floor,
        'f05_amenity_score':            _amenity_score(inp),
        'f06_demand_intensity':         zone.get('demand_intensity_score', 60.0),
        'f07_supply_demand_ratio':      zone.get('supply_demand_ratio', 1.0),
        'f08_zone_demand_trend':        zone.get('price_change_yoy_pct', 6.0) / 100.0,
        'f09_proximity_school':         zone.get('avg_proximity_school_km', 1.5),
        'f10_proximity_hospital':       zone.get('avg_proximity_hospital_km', 3.0),
        'f11_proximity_transport':      zone.get('avg_proximity_transport_km', 1.0),
        'f12_composite_proximity':      (zone.get('avg_proximity_school_km', 1.5) +
                                         zone.get('avg_proximity_hospital_km', 3.0) +
                                         zone.get('avg_proximity_transport_km', 1.0)) / 3.0,
        'f13_ptype_encoded':            float(_PTYPE_CODE.get(ptype, 0)),
        'f14_surface_category':         _surface_category(surface),
        'f15_forecast_6m':              fcst.get('forecast_6m_pct', 3.5),
        'f16_forecast_reliability':     fcst.get('forecast_reliability', 0.6),
        'f17_climate_risk_composite':   50.0,
        'f18_climate_value_drag':       0.0,
        'f19_bct_rate':                 MACRO['bct_benchmark_rate_pct'],
        'f20_inflation_rate':           MACRO['inflation_rate_cpi_pct'],
        'f21_unemployment_regional':    MACRO['unemployment_rate_national_pct'],
        'f22_mortgage_rate':            MACRO['avg_mortgage_rate_pct'],
        'f23_gov_encoded':              _gov_code(gov),
        'f24_vacancy_rate':             zone.get('vacancy_rate_pct', 7.0),
        'f25_market_value_estimate':    price,
    }


def build_scanner_features_m4(inp: dict, zone: dict, fcst: dict,
                               m1_proba: float, m2_yield: float,
                               m3_p_buy: float) -> dict:
    """Features for Model 4: opportunity_score_engine (80 features — filled with zone/macro)."""
    price    = float(inp.get('listing_price_tnd', 200000))
    surface  = float(inp.get('surface_m2', 100))
    ptype    = inp.get('property_type', 'apartment').lower()
    gov      = inp.get('governorate', 'Tunis')
    deleg    = inp.get('delegation', '')
    rooms    = float(inp.get('room_count', 3))
    floor    = int(inp.get('floor_level', 0))
    days     = float(inp.get('days_active', 15))
    repost   = float(inp.get('repost_count', 0))
    reductions = float(inp.get('price_reduction_count', 0))

    zone_avg_pm2 = zone.get('avg_price_per_m2_tnd', 1500.0)
    price_pm2    = price / max(surface, 1)
    price_gap_abs = price_pm2 - zone_avg_pm2
    price_gap_ratio = price_gap_abs / max(zone_avg_pm2, 1)
    percentile   = min(max(50.0 + price_gap_ratio * 50, 5.0), 95.0)
    within_ci    = 1.0 if abs(price_gap_ratio) < 0.15 else 0.0

    opex_estimate = price * 0.005  # ~0.5% of price annually
    net_yield     = max(0.0, m2_yield - 2.0)  # net yield after costs

    return {
        'current_estimated_value_tnd':   price,
        'acquisition_price_tnd':         price,
        'total_cost_basis_tnd':          price * 1.07,
        'acquisition_transaction_cost_tnd': price * 0.07,
        'unrealized_gain_loss_tnd':      0.0,
        'unrealized_gain_loss_pct':      0.0,
        'holding_period_days':           0.0,
        'holding_period_years':          0.0,
        'surface_m2':                    surface,
        'room_count':                    rooms,
        'bedrooms':                      max(1.0, rooms - 1),
        'bathrooms':                     max(1.0, math.ceil(rooms / 3)),
        'floor_level':                   float(floor),
        'amenity_score':                 _amenity_score(inp),
        'surface_category':              _surface_category(surface),
        'room_density':                  rooms / max(surface, 1),
        'floor_premium':                 _floor_premium(floor),
        'property_type_code':            float(_PTYPE_CODE.get(ptype, 0)),
        'governorate_code':              _gov_code(gov),
        'delegation_code':               _deleg_code(deleg),
        'listing_price_tnd':             price,
        'estimated_fair_value_tnd':      price_pm2 / max(1 + price_gap_ratio, 0.5) * surface,
        'price_gap_absolute_tnd':        price_gap_abs * surface,
        'price_gap_ratio':               price_gap_ratio,
        'within_confidence_interval':    within_ci,
        'photo_quality_score':           float(inp.get('photo_quality', 5.0)),
        'description_sentiment_score':   0.5,
        'promotional_bias_flag':         0.0,
        'listing_quality_score':         float(inp.get('listing_quality', 5.0)),
        'avg_price_per_m2_tnd':          zone_avg_pm2,
        'median_price_per_m2_tnd':       zone.get('median_price_per_m2_tnd', zone_avg_pm2 * 0.95),
        'demand_intensity_score':        zone.get('demand_intensity_score', 60.0),
        'supply_demand_ratio':           zone.get('supply_demand_ratio', 1.0),
        'median_days_on_market':         zone.get('median_days_on_market', 45.0),
        'vacancy_rate_pct':              zone.get('vacancy_rate_pct', 7.0),
        'avg_proximity_school_km':       zone.get('avg_proximity_school_km', 1.5),
        'avg_proximity_hospital_km':     zone.get('avg_proximity_hospital_km', 3.0),
        'avg_proximity_transport_km':    zone.get('avg_proximity_transport_km', 1.0),
        'price_change_mom_pct':          zone.get('price_change_mom_pct', 0.5),
        'price_change_yoy_pct':          zone.get('price_change_yoy_pct', 6.0),
        'zone_population':               zone.get('zone_population', 80000.0),
        'transaction_velocity_score':    zone.get('transaction_velocity_score', 50.0),
        'forecast_3m_pct':               fcst.get('forecast_3m_pct', 2.0),
        'forecast_6m_pct':               fcst.get('forecast_6m_pct', 3.5),
        'forecast_12m_pct':              fcst.get('forecast_12m_pct', 6.0),
        'forecast_direction_code':       fcst.get('forecast_direction_code', 1.0),
        'forecast_confidence_code':      fcst.get('forecast_confidence_code', 1.0),
        'forecast_reliability':          fcst.get('forecast_reliability', 0.6),
        'trend_volatility_score':        fcst.get('trend_volatility_score', 25.0),
        'flood_risk_score':              20.0,
        'heat_stress_score':             40.0,
        'drought_risk_score':            35.0,
        'infrastructure_risk_score':     30.0,
        'sustainability_score':          60.0,
        'climate_risk_composite':        50.0,
        'climate_value_adjustment_10y_pct': 0.0,
        'coastal_proximity_km':          50.0,
        'elevation_m':                   50.0,
        **MACRO,
        'macro_pressure_score':          50.0,
        'currency_pressure_score':       40.0,
        'undervaluation_proxy_score':    m1_proba * 100,
        'yield_attractiveness_score':    min(m2_yield * 10, 100.0),
        'demand_heat_score':             zone.get('demand_intensity_score', 60.0),
        'risk_penalty_score':            50.0,
        'value_momentum_score':          max(0.0, -price_gap_ratio * 50 + 50),
        'forecast_momentum_score':       min(fcst.get('forecast_6m_pct', 3.5) * 10, 100.0),
        'liquidity_score':               zone.get('transaction_velocity_score', 50.0),
        'buy_now_proxy_score':           m3_p_buy * 100,
    }


def build_scanner_features_m5(inp: dict, zone: dict, fcst: dict,
                               m1_proba: float, m2_yield: float,
                               m3_p_buy: float, m4_score: float,
                               asset: dict | None = None) -> dict:
    """Features for Model 5: investment_grade_classifier."""
    price    = float(inp.get('listing_price_tnd', 200000))
    surface  = float(inp.get('surface_m2', 100))
    ptype    = inp.get('property_type', 'apartment').lower()
    gov      = inp.get('governorate', 'Tunis')
    deleg    = inp.get('delegation', '')
    rooms    = float(inp.get('room_count', 3))
    floor    = int(inp.get('floor_level', 0))

    net_yield = max(0.0, m2_yield - 2.0)
    cost_basis = price * 1.07
    acq_cost   = price * 0.07

    a = asset or {}

    return {
        'opportunity_score_signal':          m4_score,
        'p_buy':                             m3_p_buy,
        'gross_yield_predicted':             m2_yield,
        'net_yield_computed':                net_yield,
        'climate_risk_signal':               50.0,
        'climate_value_adjustment_signal':   0.0,
        'feature_profitability_score':       (m4_score / 100) * 50 + net_yield * 2,
        'feature_risk_score':                50.0,
        'current_estimated_value_tnd':       float(a.get('current_value_tnd', price)),
        'acquisition_price_tnd':             float(a.get('acquisition_price_tnd', price)),
        'total_cost_basis_tnd':              cost_basis,
        'acquisition_transaction_cost_tnd':  acq_cost,
        'unrealized_gain_loss_tnd':          float(a.get('unrealized_gain_tnd', 0)),
        'unrealized_gain_loss_pct':          float(a.get('unrealized_gain_pct', 0)),
        'monthly_rent_income_tnd':           float(a.get('monthly_rent_tnd', price * m2_yield / 100 / 12)),
        'monthly_operating_cost_tnd':        float(a.get('monthly_opex_tnd', price * 0.005 / 12)),
        'hold_to_date_irr_pct':              float(a.get('hold_irr', net_yield)),
        'forecast_6m_pct':                   fcst.get('forecast_6m_pct', 3.5),
        'forecast_direction_code':           fcst.get('forecast_direction_code', 1.0),
        'forecast_confidence_code':          fcst.get('forecast_confidence_code', 1.0),
        'forecast_reliability':              fcst.get('forecast_reliability', 0.6),
        'trend_volatility_score':            fcst.get('trend_volatility_score', 25.0),
        'demand_intensity_score':            zone.get('demand_intensity_score', 60.0),
        'supply_demand_ratio':               zone.get('supply_demand_ratio', 1.0),
        'median_days_on_market':             zone.get('median_days_on_market', 45.0),
        'vacancy_rate_pct':                  zone.get('vacancy_rate_pct', 7.0),
        'avg_proximity_school_km':           zone.get('avg_proximity_school_km', 1.5),
        'avg_proximity_hospital_km':         zone.get('avg_proximity_hospital_km', 3.0),
        'avg_proximity_transport_km':        zone.get('avg_proximity_transport_km', 1.0),
        'price_change_mom_pct':              zone.get('price_change_mom_pct', 0.5),
        'price_change_yoy_pct':              zone.get('price_change_yoy_pct', 6.0),
        'transaction_velocity_score':        zone.get('transaction_velocity_score', 50.0),
        'flood_risk_score':                  20.0,
        'heat_stress_score':                 40.0,
        'drought_risk_score':                35.0,
        'infrastructure_risk_score':         30.0,
        'sustainability_score':              60.0,
        'coastal_proximity_km':              50.0,
        'elevation_m':                       50.0,
        **MACRO,
        'property_type_code':                float(_PTYPE_CODE.get(ptype, 0)),
        'governorate_code':                  _gov_code(gov),
        'delegation_code':                   _deleg_code(deleg),
        'is_rented':                         1.0 if a.get('is_rented') else 0.0,
        'portfolio_yield_spread':            net_yield - 4.0,
        'target_irr_pct':                    12.0,
    }


def build_portfolio_features_m2(asset: dict, zone: dict, fcst: dict) -> dict:
    """Adapt PortfolioAsset dict to rental_yield features."""
    return build_scanner_features_m2(
        {
            'listing_price_tnd': asset.get('current_value_tnd') or asset.get('acquisition_price_tnd', 200000),
            'surface_m2':        asset.get('surface_m2', 100),
            'room_count':        asset.get('room_count', 3),
            'floor_level':       asset.get('floor_level', 0),
            'property_type':     asset.get('property_type', 'apartment'),
            'governorate':       asset.get('governorate', 'Tunis'),
        },
        zone, fcst,
    )


def build_portfolio_features_m6(asset: dict, zone: dict, fcst: dict, m2_yield: float) -> dict:
    """Features for Model 6: irr_predictor."""
    price        = float(asset.get('acquisition_price_tnd', 200000))
    cur_val      = float(asset.get('current_value_tnd') or price)
    surface      = float(asset.get('surface_m2', 100))
    rooms        = float(asset.get('room_count', 3))
    ptype        = asset.get('property_type', 'apartment').lower()
    gov          = asset.get('governorate', 'Tunis')
    deleg        = asset.get('delegation', '')
    rent_mo      = float(asset.get('monthly_rent_tnd', 0))
    opex_mo      = float(asset.get('monthly_opex_tnd', 0))
    hold_days    = float(asset.get('holding_days', 0))
    hold_years   = hold_days / 365.25

    cost_basis   = price * 1.07
    sale_cost    = cur_val * 0.03
    annual_rent  = rent_mo * 12
    annual_opex  = opex_mo * 12
    net_cf       = annual_rent - annual_opex
    appreciation = cur_val - price
    gross_return = appreciation + annual_rent * max(hold_years, 1)
    gross_yield  = annual_rent / max(price, 1) * 100
    net_yield    = max(0.0, gross_yield - 2.0)
    ltv          = 0.6  # assumed 60% LTV
    ppm2         = price / max(surface, 1)
    return_pm2   = gross_return / max(surface, 1)
    ann_apprec   = appreciation / max(hold_years, 1) / max(price, 1) * 100
    ann_cf_ret   = net_cf / max(price, 1) * 100

    return {
        'purchase_price':           price,
        'purchase_transaction_cost':price * 0.07,
        'total_cost_basis':         cost_basis,
        'sale_price':               cur_val,
        'sale_transaction_cost':    sale_cost,
        'holding_years':            hold_years,
        'annual_rent':              annual_rent,
        'annual_opex':              annual_opex,
        'annual_net_cashflow':      net_cf,
        'gross_return_total':       gross_return,
        'appreciation':             appreciation,
        'gross_yield_at_purchase':  gross_yield,
        'net_yield_at_purchase':    net_yield,
        'bct_rate_at_purchase':     MACRO['bct_benchmark_rate_pct'],
        'mortgage_rate_at_purchase':MACRO['avg_mortgage_rate_pct'],
        'avg_inflation_holding':    MACRO['inflation_rate_cpi_pct'],
        'climate_risk_at_purchase': 50.0,
        'climate_value_adjustment': 0.0,
        'ltv_ratio':                ltv,
        'price_per_m2':             ppm2,
        'room_density':             rooms / max(surface, 1),
        'return_per_m2':            return_pm2,
        'annual_appreciation':      ann_apprec,
        'annual_cashflow_return':   ann_cf_ret,
        'purchase_cost_ratio':      0.07,
        'sale_cost_ratio':          0.03,
        'surface_m2':               surface,
        'room_count':               rooms,
        'property_type_code':       float(_PTYPE_CODE.get(ptype, 0)),
        'governorate_code':         _gov_code(gov),
        'delegation_code':          _deleg_code(deleg),
    }


def build_portfolio_features_m7(asset: dict, zone: dict, fcst: dict,
                                 m2_yield: float) -> dict:
    """Features for Model 7: portfolio_risk_scorer."""
    price    = float(asset.get('acquisition_price_tnd', 200000))
    cur_val  = float(asset.get('current_value_tnd') or price)
    surface  = float(asset.get('surface_m2', 100))
    rooms    = float(asset.get('room_count', 3))
    ptype    = asset.get('property_type', 'apartment').lower()
    gov      = asset.get('governorate', 'Tunis')
    deleg    = asset.get('delegation', '')
    floor    = float(asset.get('floor_level', 0))
    amenity  = float(asset.get('amenity_score', 1.0))

    zone_avg_pm2 = zone.get('avg_price_per_m2_tnd', 1500.0)
    price_pm2    = cur_val / max(surface, 1)
    price_gap_abs  = price_pm2 - zone_avg_pm2
    price_gap_ratio = price_gap_abs / max(zone_avg_pm2, 1)
    percentile     = min(max(50.0 + price_gap_ratio * 50, 5.0), 95.0)

    return {
        'listing_price_tnd':          cur_val,
        'surface_m2':                 surface,
        'room_count':                 rooms,
        'price_percentile_in_zone':   percentile,
        'price_per_m2_listing':       price_pm2,
        'zone_price_gap_absolute_tnd':price_gap_abs,
        'price_gap_ratio':            price_gap_ratio,
        'price_per_m2_zone_deviation':price_gap_ratio,
        'within_zone_band':           1.0 if abs(price_gap_ratio) < 0.15 else 0.0,
        'price_reduction_count':      0.0,
        'cumulative_price_reduction_pct': 0.0,
        'repost_count':               0.0,
        'price_hardness_score':       0.8,
        'listing_freshness_score':    1.0,
        'seller_type_agency':         1.0,
        'listing_quality_score':      5.0,
        'photo_quality_score':        5.0,
        'amenity_score':              amenity,
        'composite_proximity_score':  (zone.get('avg_proximity_school_km', 1.5) +
                                       zone.get('avg_proximity_hospital_km', 3.0) +
                                       zone.get('avg_proximity_transport_km', 1.0)) / 3.0,
        'demand_intensity_score':     zone.get('demand_intensity_score', 60.0),
        'supply_demand_ratio':        zone.get('supply_demand_ratio', 1.0),
        'transaction_velocity_score': zone.get('transaction_velocity_score', 50.0),
        'forecast_3m_pct':            fcst.get('forecast_3m_pct', 2.0),
        'forecast_6m_pct':            fcst.get('forecast_6m_pct', 3.5),
        'forecast_12m_pct':           fcst.get('forecast_12m_pct', 6.0),
        'forecast_direction_code':    fcst.get('forecast_direction_code', 1.0),
        'forecast_confidence_code':   fcst.get('forecast_confidence_code', 1.0),
        'forecast_reliability_score': fcst.get('forecast_reliability_score', 60.0),
        'trend_volatility_score':     fcst.get('trend_volatility_score', 25.0),
        'forecast_momentum':          fcst.get('forecast_momentum', 1.0),
        'flood_risk_score':           20.0,
        'heat_stress_score':          40.0,
        'drought_risk_score':         35.0,
        'infrastructure_risk_score':  30.0,
        'sustainability_score':       60.0,
        'climate_risk_score':         50.0,
        'climate_value_drag':         0.0,
        **MACRO,
        'macro_affordability_index':  1.0 - MACRO['avg_mortgage_rate_pct'] / 20.0,
        'macro_pressure_score':       50.0,
        'property_type_code':         float(_PTYPE_CODE.get(ptype, 0)),
        'governorate_code':           _gov_code(gov),
        'delegation_code':            _deleg_code(deleg),
    }
