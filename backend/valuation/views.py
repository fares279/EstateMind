import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import ValuationRequest
from .serializers import ValuationInputSerializer, ValuationHistorySerializer

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_locations(request):
    """GET /api/valuations/locations/"""
    try:
        from core.models import Region, Delegation
        regions = list(
            Region.objects.all().order_by('governorate')
            .values('id', 'governorate', 'avg_price_per_sqm', 'latitude', 'longitude')
        )
        delegations = list(
            Delegation.objects.select_related('region')
            .all().order_by('region__governorate', 'name')
            .values('id', 'name', 'region__id', 'region__governorate',
                    'centroid_lat', 'centroid_lon')
        )
        return Response({'regions': regions, 'delegations': delegations})
    except Exception as exc:
        logger.exception("get_locations error: %s", exc)
        return Response({'regions': [], 'delegations': []})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def predict_valuation(request):
    """POST /api/valuations/predict/"""
    serializer = ValuationInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = dict(serializer.validated_data)
    image_files = request.FILES.getlist('images') or []
    data['image_count'] = len(image_files)

    try:
        # Import lazily to avoid loading heavy ML dependencies during global URL resolution.
        from .services import valuation_service
        result = valuation_service.estimate(data, image_files=image_files)
    except Exception as exc:
        logger.exception("Valuation pipeline error: %s", exc)
        return Response(
            {'detail': 'Valuation service error. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    try:
        ValuationRequest.objects.create(
            user             = request.user,
            property_type    = data.get('property_type', ''),
            transaction_type = data.get('transaction_type', 'sale'),
            governorate      = data.get('governorate', ''),
            city             = data.get('city', '') or data.get('delegation', ''),
            neighborhood     = data.get('neighborhood', ''),
            size_m2          = data.get('size_m2'),
            bedrooms         = data.get('bedrooms'),
            bathrooms        = data.get('bathrooms'),
            condition        = data.get('condition', ''),
            has_pool         = data.get('has_pool', False),
            has_garden       = data.get('has_garden', False),
            has_parking      = data.get('has_parking', False),
            sea_view         = data.get('sea_view', False),
            elevator         = data.get('elevator', False),
            description      = data.get('description', ''),
            image_count      = len(image_files),
            estimated_price  = result['estimated_price'],
            lower_bound      = result['lower_bound'],
            upper_bound      = result['upper_bound'],
            price_per_m2     = result.get('price_per_m2'),
            confidence       = result['confidence'],
            confidence_level = result['confidence_level'],
            prediction_mode  = result['prediction_mode'],
            response_data    = result,
            climate_risk_category  = result.get('climate_risk_category', ''),
            climate_adjustment_pct = result.get('climate_adjustment_pct'),
            climate_adjusted_price = result.get('climate_adjusted_price'),
            climate_label          = result.get('climate_label', ''),
        )
    except Exception as exc:
        logger.warning("Failed to save valuation history: %s", exc)

    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def valuation_history(request):
    """GET /api/valuations/history/"""
    qs = ValuationRequest.objects.filter(user=request.user).order_by('-created_at')[:20]
    return Response(ValuationHistorySerializer(qs, many=True).data)


# ── Forecast endpoints ────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def get_forecasts(request):
    """
    GET /api/valuations/forecasts/?delegation=X    -> single delegation 12-month
    GET /api/valuations/forecasts/?governorate=X   -> governorate aggregate
    GET /api/valuations/forecasts/                 -> available governorate list
    """
    from .services import forecast_service as fs

    delegation  = request.query_params.get('delegation', '').strip()
    governorate = request.query_params.get('governorate', '').strip()

    if delegation:
        data = fs.get_delegation_forecast(delegation)
        if data is None:
            return Response(
                {'detail': f'No forecast data for delegation: {delegation}'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(data)

    if governorate:
        data = fs.get_governorate_forecast_summary(governorate)
        if data is None:
            return Response(
                {'detail': f'No forecast data for governorate: {governorate}'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(data)

    return Response({'governorates': fs.list_governorates_with_forecasts()})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_national_forecast(request):
    """GET /api/valuations/forecasts/national/ — top movers across Tunisia"""
    from .services import forecast_service as fs
    return Response(fs.get_national_summary())


@api_view(['GET'])
@permission_classes([AllowAny])
def get_forecast_delegations(request):
    """GET /api/valuations/forecasts/delegations/?governorate=X"""
    from .services import forecast_service as fs
    governorate = request.query_params.get('governorate', '').strip()
    if not governorate:
        return Response(
            {'detail': 'governorate param required'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response({'delegations': fs.list_delegations_for_governorate(governorate)})
