import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .services import forecast_service as fs

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_forecasts(request):
    """
    GET /api/forecast/?delegation=X&property_type=apartment   → single delegation
    GET /api/forecast/?governorate=X&property_type=apartment  → governorate avg
    GET /api/forecast/                                         → governorate list
    """
    delegation    = request.query_params.get('delegation',    '').strip()
    governorate   = request.query_params.get('governorate',   '').strip()
    property_type = request.query_params.get('property_type', 'apartment').strip()

    if delegation:
        data = fs.get_delegation_forecast(delegation, property_type)
        if data is None:
            return Response(
                {'detail': f'No forecast data for delegation: {delegation}'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(data)

    if governorate:
        data = fs.get_governorate_forecast_summary(governorate, property_type)
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
    """GET /api/forecast/national/?property_type=apartment"""
    property_type = request.query_params.get('property_type', 'apartment').strip()
    return Response(fs.get_national_summary(property_type))


@api_view(['GET'])
@permission_classes([AllowAny])
def get_forecast_delegations(request):
    """GET /api/forecast/delegations/?governorate=X"""
    governorate = request.query_params.get('governorate', '').strip()
    if not governorate:
        return Response({'detail': 'governorate param required'}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'delegations': fs.list_delegations_for_governorate(governorate)})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_market_data(request):
    """
    GET /api/forecast/market/?property_type=apartment
    Returns all delegations with current prices, 12M forecast, and trend.
    Used by the Market Dashboard tab.
    """
    property_type = request.query_params.get('property_type', 'apartment').strip()
    data = fs.get_market_data(property_type)
    if data is None:
        return Response(
            {'detail': 'No market data available. Run: python manage.py generate_forecasts'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(data)
