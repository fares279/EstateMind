from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import PortfolioAsset, ScanResult
from .services.scorer import score_listing, score_asset, score_portfolio
from .services.zone_data import get_zone_stats, get_zone_forecast
from .services.registry import REGISTRY


# ── Portfolio CRUD ────────────────────────────────────────────────────────────

def _asset_to_dict(asset: PortfolioAsset) -> dict:
    return {
        'id':                    asset.pk,
        'property_name':         asset.property_name,
        'property_type':         asset.property_type,
        'governorate':           asset.governorate,
        'delegation':            asset.delegation,
        'surface_m2':            asset.surface_m2,
        'room_count':            asset.room_count,
        'floor_level':           asset.floor_level,
        'amenity_score':         asset.amenity_score,
        'acquisition_price_tnd': asset.acquisition_price_tnd,
        'acquisition_date':      str(asset.acquisition_date),
        'current_value_tnd':     asset.current_value_tnd,
        'is_rented':             asset.is_rented,
        'monthly_rent_tnd':      asset.monthly_rent_tnd,
        'monthly_opex_tnd':      asset.monthly_opex_tnd,
        'notes':                 asset.notes,
        'holding_days':          asset.holding_days,
        'unrealized_gain_tnd':   asset.unrealized_gain_tnd,
        'unrealized_gain_pct':   round(asset.unrealized_gain_pct, 2),
        'created_at':            asset.created_at.isoformat(),
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def portfolio_list(request):
    if request.method == 'GET':
        assets = PortfolioAsset.objects.filter(user=request.user)
        return Response([_asset_to_dict(a) for a in assets])

    data = request.data
    try:
        from datetime import date
        acq_date = date.fromisoformat(data.get('acquisition_date', str(date.today())))
        asset = PortfolioAsset.objects.create(
            user                  = request.user,
            property_name         = data.get('property_name', 'My Property'),
            property_type         = data.get('property_type', 'apartment'),
            governorate           = data.get('governorate', ''),
            delegation            = data.get('delegation', ''),
            surface_m2            = float(data.get('surface_m2', 100)),
            room_count            = int(data.get('room_count', 3)),
            floor_level           = int(data.get('floor_level', 0)),
            amenity_score         = float(data.get('amenity_score', 1.0)),
            acquisition_price_tnd = float(data.get('acquisition_price_tnd', 0)),
            acquisition_date      = acq_date,
            current_value_tnd     = float(data['current_value_tnd']) if data.get('current_value_tnd') else None,
            is_rented             = bool(data.get('is_rented', False)),
            monthly_rent_tnd      = float(data.get('monthly_rent_tnd', 0)),
            monthly_opex_tnd      = float(data.get('monthly_opex_tnd', 0)),
            notes                 = data.get('notes', ''),
        )
        return Response(_asset_to_dict(asset), status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def portfolio_detail(request, pk):
    try:
        asset = PortfolioAsset.objects.get(pk=pk, user=request.user)
    except PortfolioAsset.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(_asset_to_dict(asset))

    if request.method == 'DELETE':
        asset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    data = request.data
    for field in ['property_name', 'property_type', 'governorate', 'delegation',
                  'surface_m2', 'room_count', 'floor_level', 'amenity_score',
                  'acquisition_price_tnd', 'current_value_tnd', 'is_rented',
                  'monthly_rent_tnd', 'monthly_opex_tnd', 'notes']:
        if field in data:
            setattr(asset, field, data[field])
    if 'acquisition_date' in data:
        from datetime import date
        asset.acquisition_date = date.fromisoformat(data['acquisition_date'])
    asset.save()
    return Response(_asset_to_dict(asset))


# ── Portfolio scoring ─────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def portfolio_score(request):
    """Score all assets in the portfolio using Models 2→6→7."""
    assets = PortfolioAsset.objects.filter(user=request.user)
    if not assets:
        return Response({'assets': [], 'summary': {}})

    asset_dicts = [_asset_to_dict(a) for a in assets]
    result = score_portfolio(asset_dicts)
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def portfolio_score_asset(request, pk):
    """Score a single portfolio asset."""
    try:
        asset = PortfolioAsset.objects.get(pk=pk, user=request.user)
    except PortfolioAsset.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    result = score_asset(_asset_to_dict(asset))
    return Response({**_asset_to_dict(asset), 'score': result})


# ── Scanner ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scanner_score(request):
    """
    Score a listing: chains Models 1→3→2→4→5.
    Required: listing_price_tnd, surface_m2, property_type, governorate, delegation
    """
    inp = request.data
    if not inp.get('listing_price_tnd') or not inp.get('surface_m2'):
        return Response({'error': 'listing_price_tnd and surface_m2 are required'},
                        status=status.HTTP_400_BAD_REQUEST)

    result = score_listing(inp)

    # Persist to scan history
    try:
        sr = ScanResult.objects.create(
            user                 = request.user,
            listing_price_tnd    = float(inp.get('listing_price_tnd', 0)),
            surface_m2           = float(inp.get('surface_m2', 0)),
            property_type        = inp.get('property_type', ''),
            governorate          = inp.get('governorate', ''),
            delegation           = inp.get('delegation', ''),
            room_count           = int(inp.get('room_count', 3)),
            undervaluation_label = result['undervaluation']['label'],
            undervaluation_proba = result['undervaluation']['proba_undervalued'],
            buy_signal           = result['buy_signal']['signal'],
            p_buy                = result['buy_signal']['p_buy'],
            gross_yield_pct      = result['yield']['gross_yield_pct'],
            opportunity_score    = result['opportunity_score'],
            investment_grade     = result['investment_grade'],
            full_result          = result,
        )
        result['scan_id'] = sr.pk
    except Exception:
        pass

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scanner_history(request):
    scans = ScanResult.objects.filter(user=request.user)[:20]
    return Response([
        {
            'id':                   s.pk,
            'listing_price_tnd':    s.listing_price_tnd,
            'surface_m2':           s.surface_m2,
            'property_type':        s.property_type,
            'governorate':          s.governorate,
            'delegation':           s.delegation,
            'undervaluation_label': s.undervaluation_label,
            'buy_signal':           s.buy_signal,
            'gross_yield_pct':      s.gross_yield_pct,
            'opportunity_score':    s.opportunity_score,
            'investment_grade':     s.investment_grade,
            'created_at':           s.created_at.isoformat(),
        }
        for s in scans
    ])


# ── Opportunities ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def opportunities(request):
    """
    Returns best investment opportunities across delegations.
    Uses forecast + zone data to rank delegations by opportunity score.
    """
    from core.models import Delegation
    from forecast.models import DelegationPriceData

    ptype_raw = (request.GET.get('property_type') or 'apartment').strip().lower()
    ptype_map = {
        'apartment': 'apartment',
        'apartments': 'apartment',
        'house': 'house',
        'houses': 'house',
        'commercial': 'commercial',
        'land': 'land',
    }
    ptype = ptype_map.get(ptype_raw, 'apartment')

    try:
        limit = max(1, min(int(request.GET.get('limit', 20)), 100))
    except (TypeError, ValueError):
        limit = 20

    # Primary source: forecast snapshot table by property type.
    rows = list(
        DelegationPriceData.objects
        .filter(property_type=ptype)
        .exclude(price_avg__isnull=True)
        .order_by('-annual_trend_pct')[:200]
    )

    # Fallback source: core delegation benchmark fields.
    if not rows:
        field_map = {
            'apartment': ('apt_avg_tnd', 'apt_trend_pct'),
            'house': ('house_avg_tnd', 'house_trend_pct'),
            'commercial': ('comm_avg_tnd', 'comm_trend_pct'),
            'land': ('land_avg_tnd', 'land_trend_pct'),
        }
        avg_field, trend_field = field_map.get(ptype, field_map['apartment'])
        core_rows = (
            Delegation.objects
            .exclude(**{f'{avg_field}__isnull': True})
            .values('name', 'region__governorate', avg_field, trend_field)
        )
        rows = [
            {
                'delegation_name': row['name'],
                'governorate': row['region__governorate'] or '',
                'price_avg': row.get(avg_field) or 0,
                'annual_trend_pct': row.get(trend_field) or 0,
            }
            for row in core_rows
            if (row.get(avg_field) or 0) > 0
        ]

    results = []
    for row in rows:
        if hasattr(row, 'delegation_name'):
            delegation_name = row.delegation_name
            governorate = row.governorate
            price_avg = row.price_avg
            annual_trend_pct = row.annual_trend_pct
        else:
            delegation_name = row.get('delegation_name', '')
            governorate = row.get('governorate', '')
            price_avg = row.get('price_avg')
            annual_trend_pct = row.get('annual_trend_pct')

        price = float(price_avg or 0)
        if price <= 0:
            continue

        _ = get_zone_stats(delegation_name, ptype)
        _ = get_zone_forecast(delegation_name, ptype)

        inp = {
            'listing_price_tnd': price * 100.0,
            'surface_m2': 100.0,
            'property_type': ptype,
            'governorate': governorate,
            'delegation': delegation_name,
            'room_count': 3,
        }

        try:
            scored = score_listing(inp)
        except Exception:
            continue

        results.append({
            'delegation': delegation_name,
            'governorate': governorate,
            'avg_price_pm2': price,
            'annual_trend_pct': float(annual_trend_pct or 0),
            'opportunity_score': scored['opportunity_score'],
            'investment_grade': scored['investment_grade'],
            'gross_yield_pct': scored['yield']['gross_yield_pct'],
            'buy_signal': scored['buy_signal']['signal'],
            'forecast_6m_pct': scored['forecast']['forecast_6m_pct'],
            'forecast_12m_pct': scored['forecast']['forecast_12m_pct'],
            'undervaluation': scored['undervaluation']['label'],
        })

    results.sort(key=lambda x: x['opportunity_score'], reverse=True)
    return Response(results[:limit])


# ── Dashboard ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def investor_dashboard(request):
    """Aggregated dashboard: portfolio summary + top opportunities + market signals."""
    assets = PortfolioAsset.objects.filter(user=request.user)
    asset_dicts = [_asset_to_dict(a) for a in assets]

    portfolio_result = score_portfolio(asset_dicts) if asset_dicts else {
        'assets': [], 'summary': {
            'total_assets': 0, 'total_value_tnd': 0, 'total_cost_tnd': 0,
            'total_gain_tnd': 0, 'total_return_pct': 0, 'avg_gross_yield_pct': 0,
            'avg_irr_pct': 0, 'avg_risk_score': 50, 'grade_distribution': {},
        },
    }

    # Market signals: top 5 opportunity delegations
    from forecast.models import DelegationPriceData
    top_delegations = list(
        DelegationPriceData.objects.filter(property_type='apartment')
        .order_by('-annual_trend_pct')[:5]
        .values('delegation_name', 'governorate', 'price_avg', 'annual_trend_pct')
    )

    models_status = {name: REGISTRY.is_available(name) for name in [
        'undervaluation_detector', 'rental_yield', 'buy_wait_classifier',
        'opportunity_score_engine', 'investment_grade_classifier',
        'irr_predictor', 'portfolio_risk_scorer',
    ]}

    return Response({
        'portfolio':         portfolio_result['summary'],
        'assets':            portfolio_result['assets'],
        'market_signals':    top_delegations,
        'models_status':     models_status,
        'scan_count':        ScanResult.objects.filter(user=request.user).count(),
    })


# ── Risk analysis ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def risk_analysis(request):
    """Detailed risk breakdown for the whole portfolio."""
    assets = PortfolioAsset.objects.filter(user=request.user)
    if not assets:
        return Response({'risk_score': 0, 'breakdown': [], 'concentration': {}})

    gov_concentration   = {}
    ptype_concentration = {}
    scored_assets = []

    for a in assets:
        result = score_asset(_asset_to_dict(a))
        gov_concentration[a.governorate]    = gov_concentration.get(a.governorate, 0) + float(a.current_value_tnd or a.acquisition_price_tnd)
        ptype_concentration[a.property_type] = ptype_concentration.get(a.property_type, 0) + float(a.current_value_tnd or a.acquisition_price_tnd)
        scored_assets.append({
            'id':           a.pk,
            'name':         a.property_name,
            'risk_score':   result['risk']['risk_score'],
            'risk_level':   result['risk']['risk_level'],
            'grade':        result['grade'],
            'irr_pct':      result['irr']['irr_pct'],
            'yield_pct':    result['yield']['gross_yield_pct'],
        })

    total_val = sum(gov_concentration.values()) or 1
    gov_pct   = {g: round(v / total_val * 100, 1) for g, v in gov_concentration.items()}
    ptype_pct = {p: round(v / total_val * 100, 1) for p, v in ptype_concentration.items()}

    avg_risk = sum(a['risk_score'] for a in scored_assets) / len(scored_assets)

    # Concentration risk: HHI
    hhi = sum((p / 100) ** 2 for p in gov_pct.values()) * 100
    concentration_risk = 'High' if hhi > 60 else ('Medium' if hhi > 30 else 'Low')

    return Response({
        'portfolio_risk_score':   round(avg_risk, 1),
        'concentration_risk':     concentration_risk,
        'hhi_index':              round(hhi, 1),
        'assets':                 scored_assets,
        'governorate_exposure':   gov_pct,
        'property_type_exposure': ptype_pct,
    })
