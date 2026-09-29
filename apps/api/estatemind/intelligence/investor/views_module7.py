"""
Module 7: Portfolio & Investment Intelligence API Endpoints

Endpoints:
  POST   /api/investor/scan/          - Analyze single property
  GET    /api/investor/portfolio/analysis/ - Get portfolio analysis
  POST   /api/investor/portfolio/add/ - Add asset to portfolio
  GET    /api/investor/scorers/       - List scorer versions
  POST   /api/investor/scorers/start-ab-test/
  POST   /api/investor/scorers/promote/
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from estatemind.platform.errors import error_body

INPUT_MESSAGE = 'Some of the values could not be read. Please check them and try again.'

from estatemind.intelligence.investor.models import (
    PortfolioAsset, InvestmentScore, PortfolioAnalysis, InvestorScorerVersion,
)
from estatemind.intelligence.investor.services.scoring_chain import ScannerChain, PortfolioChain
from estatemind.intelligence.investor.services.covariance_model import PortfolioCovarianceModel
from estatemind.intelligence.investor.services.scorer_registry import InvestorScorerRegistry
from estatemind.intelligence.investor.services.zone_data import get_zone_stats, get_zone_forecast
from estatemind.market.core.models import DelegationMarketSnapshot

logger = logging.getLogger(__name__)


def _latest_median_rent(delegation_name: str) -> float:
    """Median monthly rent from the latest snapshot that has one; 0 if none."""
    rent = (
        DelegationMarketSnapshot.objects
        .filter(delegation__name__iexact=delegation_name, median_rent_price__isnull=False)
        .order_by('-as_of_date')
        .values_list('median_rent_price', flat=True)
        .first()
    )
    return float(rent) if rent else 0


# ════════════════════════════════════════════════════════════════════════════════
# SCANNER ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])
def scan_property(request):
    """
    Analyze a property listing.
    
    Request:
      {
        "property": {
          "asking_price_tnd": 350000,
          "surface_m2": 120,
          "property_type": "apartment",
          "room_count": 3,
          "condition": "good",
          "age_years": 10
        },
        "market": {
          "delegation": "Ben Arous",
          "delegation_median_price_m2": 3000,
          "delegation_median_monthly_rent": 1400,
          "delegation_price_momentum_12m": 0.08,
          "delegation_dom": 30,
          "climate_risk_score": 0.45,
          "national_interest_rate": 8.0
        }
      }
    
    Returns: Complete investment analysis with grades, yields, IRRs, drivers
    """
    try:
        property_data = request.data.get('property', {})
        market_data = request.data.get('market', {})

        if not all(k in property_data for k in ['asking_price_tnd', 'surface_m2', 'property_type']):
            return Response(
                {'detail': 'Missing required property fields'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enrich market_data with zone data if delegation is provided
        delegation = market_data.get('delegation') or property_data.get('delegation', 'Tunisia')
        property_type = property_data.get('property_type', 'apartment')
        
        if delegation:
            # Missing market fields come from real data (market_inputs); what had to be
            # assumed is returned in assumed_inputs.
            from .services.market_inputs import market_inputs
            real = market_inputs(delegation, property_data.get('governorate', ''), property_type,
                                 property_data.get('surface_m2', 0))
            for key, value in real.items():
                if not market_data.get(key):
                    market_data[key] = value
            market_data['_zone_data_used'] = True
            market_data['_delegation'] = delegation

        if not all(k in market_data for k in ['delegation_median_price_m2', 'delegation_median_monthly_rent']):
            return Response(
                {'detail': 'Missing required market fields and could not load zone data'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate asking_price is within realistic bounds
        asking_price = property_data.get('asking_price_tnd', 0)
        if asking_price < 1000 or asking_price > 50_000_000:
            return Response(
                {'detail': f'Asking price must be between 1,000 and 50,000,000 TND. Got: {asking_price}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Run scanner chain
        scanner = ScannerChain()
        result = scanner.run(
            property_data=property_data,
            market_data=market_data,
            user_id=request.user.id if request.user.is_authenticated else None,
        )

        return Response(result)

    except Exception as e:
        logger.error(f'Scanner error: {e}')
        return Response(
            error_body(e, key='detail', where='investor'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ════════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_portfolio_asset(request):
    """Add property to user's portfolio."""
    try:
        data = request.data
        from datetime import date

        acq_date = date.fromisoformat(data.get('acquisition_date', str(date.today())))

        asset = PortfolioAsset.objects.create(
            user=request.user,
            property_name=data.get('property_name', 'Property'),
            property_type=data.get('property_type', 'apartment'),
            governorate=data.get('governorate'),
            delegation=data.get('delegation'),
            surface_m2=data.get('surface_m2', 0),
            room_count=data.get('room_count', 3),
            acquisition_price_tnd=data.get('acquisition_price_tnd', 0),
            acquisition_date=acq_date,
            current_value_tnd=data.get('current_value_tnd'),
            is_rented=data.get('is_rented', False),
            monthly_rent_tnd=data.get('monthly_rent_tnd', 0),
            monthly_opex_tnd=data.get('monthly_opex_tnd', 0),
        )

        return Response({
            'id': asset.pk,
            'message': 'Asset added to portfolio',
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f'Error adding asset: {e}')
        return Response(error_body(e, INPUT_MESSAGE, key='detail', where='investor'), status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def portfolio_analysis(request):
    """
    Get complete portfolio analysis for user.
    Includes yields, IRRs, risk assessment, concentration alerts, diversification suggestions.
    """
    try:
        # Fetch user's portfolio assets
        assets = PortfolioAsset.objects.filter(user=request.user)

        if not assets.exists():
            return Response({
                'detail': 'No portfolio assets',
                'portfolio': {
                    'total_assets': 0,
                },
            })

        # Build market data map
        from .services.market_inputs import market_inputs
        market_data_map = {}
        for asset in assets:
            delegation = asset.delegation
            if delegation not in market_data_map:
                # growth and its band from the price forecast (was a 0.0 placeholder,
                # so the three IRR scenarios were always identical)
                market_data_map[delegation] = market_inputs(
                    delegation, getattr(asset, 'governorate', '') or '', asset.property_type, asset.surface_m2)
                market_data_map[delegation]['delegation_median_monthly_rent'] = _latest_median_rent(delegation)

        # Run portfolio chain
        portfolio_chain = PortfolioChain()
        portfolio_data = []
        for asset in assets:
            portfolio_data.append({
                'property_name': asset.property_name,
                'property_type': asset.property_type,
                'delegation': asset.delegation,
                'surface_m2': asset.surface_m2,
                'room_count': asset.room_count,
                'acquisition_price_tnd': asset.acquisition_price_tnd,
                'current_value_tnd': asset.current_value_tnd or asset.acquisition_price_tnd,
                'is_self_managed': not asset.monthly_rent_tnd > 0,
                'monthly_rent_tnd': asset.monthly_rent_tnd,
            })

        result = portfolio_chain.run(
            portfolio_assets=portfolio_data,
            market_data_map=market_data_map,
            user_id=request.user.id,
        )

        # Add covariance-based risk analysis
        cov_model = PortfolioCovarianceModel()
        delegations = list(set(a.delegation for a in assets))

        if len(delegations) > 1:
            weights = [a.current_value_tnd or a.acquisition_price_tnd
                      for a in assets]
            total = sum(weights)
            weights = [w / total for w in weights]

            portfolio_vol = cov_model.compute_portfolio_volatility(weights, delegations)
            diversification_ratio = cov_model.compute_diversification_ratio(weights, delegations)
            concentration_alerts = cov_model.generate_concentration_alerts(weights, delegations)
            correlation_alerts = cov_model.generate_correlation_alerts(delegations)
            diversification_suggestions = cov_model.generate_diversification_suggestions(delegations)

            result['risk']['portfolio_volatility_pct'] = round(portfolio_vol * 100, 1)
            result['risk']['diversification_ratio'] = round(diversification_ratio, 2)
            result['risk']['concentration_alerts'] = concentration_alerts
            result['risk']['correlation_alerts'] = correlation_alerts
            result['risk']['diversification_suggestions'] = diversification_suggestions

        return Response(result)

    except Exception as e:
        logger.error(f'Portfolio analysis error: {e}')
        return Response(
            error_body(e, key='detail', where='investor'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ════════════════════════════════════════════════════════════════════════════════
# MODEL REGISTRY & VERSION MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
def list_scorer_versions(request):
    """List all scorer versions and their status."""
    try:
        scorer_name = request.query_params.get('scorer_name')

        if scorer_name:
            versions = InvestorScorerVersion.objects.filter(scorer_name=scorer_name)
        else:
            versions = InvestorScorerVersion.objects.all()

        result = {}
        for v in versions:
            if v.scorer_name not in result:
                result[v.scorer_name] = []

            result[v.scorer_name].append({
                'version': v.version,
                'status': v.status,
                'training_date': v.training_date.isoformat(),
                'primary_metric': {
                    'name': v.validation_metric_primary_name,
                    'value': v.validation_metric_primary,
                },
                'ab_test_active': v.ab_test_active,
                'ab_test_result': v.ab_test_result,
                'promoted_at': v.promoted_at.isoformat() if v.promoted_at else None,
            })

        return Response(result)

    except Exception as e:
        logger.error(f'Error listing scorer versions: {e}')
        return Response(
            error_body(e, key='detail', where='investor'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_ab_test(request):
    """Start A/B test for challenger scorer version."""
    try:
        scorer_name = request.data.get('scorer_name')
        version = request.data.get('version')
        traffic_pct = request.data.get('traffic_pct', 0.10)
        duration_days = request.data.get('duration_days', 14)

        challenger = InvestorScorerVersion.objects.get(
            scorer_name=scorer_name,
            version=version,
            status='challenger',
        )

        registry = InvestorScorerRegistry()
        result = registry.start_ab_test(challenger, traffic_pct, duration_days)

        return Response(result)

    except InvestorScorerVersion.DoesNotExist:
        return Response(
            {'detail': 'Challenger version not found'},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f'Error starting A/B test: {e}')
        return Response(
            error_body(e, INPUT_MESSAGE, key='detail', where='investor'),
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def promote_to_champion(request):
    """Promote challenger to champion after passing all gates."""
    try:
        scorer_name = request.data.get('scorer_name')
        version = request.data.get('version')

        challenger = InvestorScorerVersion.objects.get(
            scorer_name=scorer_name,
            version=version,
        )

        registry = InvestorScorerRegistry()
        result = registry.promote_challenger_to_champion(challenger)

        if result['success']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

    except InvestorScorerVersion.DoesNotExist:
        return Response(
            {'detail': 'Scorer version not found'},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f'Error promoting: {e}')
        return Response(
            error_body(e, INPUT_MESSAGE, key='detail', where='investor'),
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rollback_scorer(request):
    """Rollback scorer to previous version."""
    try:
        scorer_name = request.data.get('scorer_name')
        target_version = request.data.get('target_version')

        registry = InvestorScorerRegistry()
        result = registry.rollback_to_previous(scorer_name, target_version)

        if result['success']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f'Error rolling back: {e}')
        return Response(
            error_body(e, INPUT_MESSAGE, key='detail', where='investor'),
            status=status.HTTP_400_BAD_REQUEST,
        )
