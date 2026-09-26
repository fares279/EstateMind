import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response

from .models import ValuationModelVersion, ValuationPredictionLog, ValuationRequest
from .serializers import ValuationInputSerializer, ValuationHistorySerializer
from .services import valuation_service
from .services.calibration_monitor import ValuationCalibrationMonitor
from .services.drift_monitor import ValuationDriftMonitor
from .services.model_registry import ValuationModelRegistry
from .services.promotion import ValuationPromotionGate

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_locations(request):
    """GET /api/valuations/locations/"""
    try:
        from estatemind.market.core.models import Region, Delegation
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
        result = valuation_service.estimate(data, image_files=image_files, user=request.user)
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
            model_name             = result.get('model_name', ''),
            model_version          = result.get('model_version', ''),
            model_artifact         = result.get('provenance', {}).get('artifact_path', ''),
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def valuation_model_registry(request):
    registry = ValuationModelRegistry()
    property_type = request.query_params.get('property_type', 'apartment')
    active_handle, active_version = registry.get_active_model(property_type, user_id=getattr(request.user, 'id', None))
    versions = [
        {
            'id': version.id,
            'model_name': version.model_name,
            'version': version.version,
            'status': version.status,
            'artifact_path': version.artifact_path,
            'training_date': version.training_date,
            'eval_rmse': version.eval_rmse,
            'eval_r2': version.eval_r2,
            'eval_mape': version.eval_mape,
            'calibration_profile': version.calibration_profile,
            'drift_profile': version.drift_profile,
        }
        for version in registry.list_versions(registry._lookup_model_name(property_type))
    ]
    return Response({
        'active': {
            'model_name': getattr(active_version, 'model_name', None),
            'version': getattr(active_version, 'version', None),
            'status': getattr(active_version, 'status', None),
            'artifact_path': getattr(active_version, 'artifact_path', None),
            'handle_path': str(active_handle.path) if active_handle else None,
        },
        'versions': versions,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def valuation_calibration_report(request):
    property_type = request.query_params.get('property_type', 'apartment')
    registry = ValuationModelRegistry()
    active_handle, active_version = registry.get_active_model(property_type, user_id=getattr(request.user, 'id', None))
    if not active_version:
        return Response({'detail': 'No registered model version found'}, status=status.HTTP_404_NOT_FOUND)
    report = ValuationCalibrationMonitor().run_calibration_check(active_version.id)
    return Response(report)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def valuation_drift_report(request):
    property_type = request.query_params.get('property_type', 'apartment')
    registry = ValuationModelRegistry()
    active_handle, active_version = registry.get_active_model(property_type, user_id=getattr(request.user, 'id', None))
    if not active_version:
        return Response({'detail': 'No registered model version found'}, status=status.HTTP_404_NOT_FOUND)
    report = ValuationDriftMonitor().run(active_version.id)
    return Response(report)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def valuation_audit_log(request):
    qs = ValuationPredictionLog.objects.filter(user=request.user).select_related('model_version').order_by('-created_at')[:50]
    return Response([
        {
            'request_id': str(log.request_id),
            'model_name': log.model_name,
            'model_version': log.model_version_label,
            'prediction_tnd': log.prediction_tnd,
            'confidence_low': log.confidence_low,
            'confidence_high': log.confidence_high,
            'confidence_level': log.confidence_level,
            'fallback_used': log.fallback_used,
            'latency_ms': log.latency_ms,
            'snapshot_date': log.snapshot_date,
            'actual_tnd': log.actual_tnd,
            'calibration_state': log.calibration_state,
            'created_at': log.created_at,
        }
        for log in qs
    ])


@api_view(['POST'])
@permission_classes([IsAdminUser])
def promote_model_version(request, version_id: int):
    registry = ValuationModelRegistry()
    try:
        version = ValuationModelVersion.objects.get(pk=version_id)
    except ValuationModelVersion.DoesNotExist:
        return Response({'detail': 'Model version not found'}, status=status.HTTP_404_NOT_FOUND)

    target = str(request.data.get('to') or 'champion').strip().lower()
    traffic_pct = int(request.data.get('traffic_pct') or request.data.get('ab_traffic_pct') or 100)

    if target == 'challenger':
        version.status = 'challenger'
        version.ab_traffic_pct = max(1, min(100, traffic_pct))
        version.promoted_by = getattr(request.user, 'email', '') or getattr(request.user, 'username', '')
        version.promoted_at = None
        version.save(update_fields=['status', 'ab_traffic_pct', 'promoted_by', 'promoted_at', 'updated_at'])
        return Response({'status': 'ok', 'version_id': version.id, 'target': target, 'traffic_pct': version.ab_traffic_pct})

    active_champion = (
        registry.list_versions(version.model_name)
        .filter(status='champion')
        .exclude(pk=version.pk)
        .first()
    )
    handle = registry._version_to_handle(version)
    model = registry._artifact_registry.maybe_load_estimator(handle)
    if model is None:
        return Response({'detail': 'Unable to load model artifact for promotion'}, status=status.HTTP_400_BAD_REQUEST)

    gate = ValuationPromotionGate()
    gate_result = gate.run(version=version, model=model, champion=active_champion)
    if not gate_result.get('promoted'):
        return Response(
            {
                'status': 'blocked',
                'reason': gate_result.get('reason', 'Promotion blocked'),
                'stability_report': gate_result.get('stability_report', {}),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    promoted = registry.promote(version.id, promoted_by=getattr(request.user, 'email', '') or getattr(request.user, 'username', ''))
    return Response(
        {
            'status': 'ok',
            'version_id': promoted.id,
            'target': 'champion',
            'traffic_pct': promoted.ab_traffic_pct,
            'stability_report': gate_result.get('stability_report', {}),
        }
    )


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
