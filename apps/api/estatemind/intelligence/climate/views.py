from estatemind.intelligence.climate.services.composite_scorer import ClimateCompositeScorer, NORMALS_SOURCE
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import Http404
from estatemind.platform.errors import error_body
from django.utils import timezone
from django.shortcuts import get_object_or_404
from estatemind.market.core.models import Delegation, DelegationClimateScore
from estatemind.intelligence.climate.services import KrigingClimateService

logger = logging.getLogger(__name__)


@api_view(['GET'])
def delegation_climate_detail(request, delegation_name):
    """
    GET /api/climate/delegation/<name>/
    
    Returns full composite score, all five factors, uncertainty bounds,
    freshness status, top risk drivers, and recalibration history.
    """
    try:
        delegation = get_object_or_404(
            Delegation, 
            name__iexact=delegation_name
        )
        score = get_object_or_404(
            DelegationClimateScore,
            delegation=delegation
        )
        
        return Response({
            'delegation': {
                'name': delegation.name,
                'governorate': delegation.region.governorate,
                'population': delegation.population,
                'is_coastal': delegation.is_coastal,
                'centroid': {
                    'lat': delegation.centroid_lat,
                    'lon': delegation.centroid_lon,
                }
            },
            'composite_score': score.composite_score,
            'composite_uncertainty': score.composite_uncertainty,
            'confidence_interval_95': {
                'lower': score.ci_lower_95,
                'upper': score.ci_upper_95,
            },
            'risk_label': score.risk_label,
            'freshness': score.freshness_display(),
            # weights from the scorer itself (they were hard-coded here and out of date)
            'factors': {
                name: {
                    'score': getattr(score, f'{name}_score'),
                    'uncertainty': getattr(score, f'{name}_uncertainty'),
                    'weight': weight,
                    **({'note': 'Mitigating factor (reduces risk)'} if name == 'infrastructure_resilience' else {}),
                }
                for name, weight in ClimateCompositeScorer.WEIGHTS.items()
            },
            'source': NORMALS_SOURCE,
            'computed_at': score.computed_at.isoformat(),
            'data_vintage': score.data_vintage.isoformat() if score.data_vintage else None,
            'computation_method': score.computation_method,
        })
    
    except Http404:
        raise  # unknown delegation or no score yet: 404, not 500
    except Exception as e:
        logger.error(f'Error fetching climate details for {delegation_name}: {e}')
        return Response(
            error_body(e, where='climate'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def climate_point_query(request):
    """
    GET /api/climate/point/?lat=36.8065&lon=10.1623
    
    Returns kriging-interpolated score at exact coordinates.
    Includes method label (kriging / nearest / fallback) and surface quality.
    """
    try:
        lat = float(request.query_params.get('lat'))
        lon = float(request.query_params.get('lon'))
    except (TypeError, ValueError):
        return Response(
            {'error': 'Invalid lat/lon. Expected floats.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        kriging = KrigingClimateService.get_instance()
        result = kriging.get_point_risk(lat, lon)
        
        # Add surface quality info
        result['surface_quality'] = kriging.get_surface_quality_report()
        
        return Response(result)
    
    except Exception as e:
        logger.error(f'Error querying climate at ({lat}, {lon}): {e}')
        return Response(
            error_body(e, where='climate'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def climate_heatmap(request):
    """
    GET /api/climate/heatmap/
    
    Returns GeoJSON FeatureCollection with delegation centroids or polygons
    colored by composite_score. Includes freshness badge per feature.
    """
    try:
        scores = DelegationClimateScore.objects.select_related('delegation').all()
        
        features = []
        for score in scores:
            d = score.delegation
            
            features.append({
                'type': 'Feature',
                'properties': {
                    'delegation': d.name,
                    'governorate': d.region.governorate,
                    'composite_score': score.composite_score,
                    'risk_label': score.risk_label,
                    'freshness_status': score.freshness_status(),
                    'computed_at': score.computed_at.isoformat(),
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [d.centroid_lon, d.centroid_lat]
                }
            })
        
        return Response({
            'type': 'FeatureCollection',
            'features': features,
            'count': len(features),
            'timestamp': timezone.now().isoformat(),  # was a hard-coded date
        })
    
    except Exception as e:
        logger.error(f'Error generating climate heatmap: {e}')
        return Response(
            error_body(e, where='climate'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def climate_summary(request):
    """
    GET /api/climate/summary/
    
    Returns national overview: distribution of risk labels, top 5 highest/lowest risk,
    freshness status.
    """
    try:
        scores = DelegationClimateScore.objects.select_related('delegation').all()
        
        risk_distribution = {}
        all_scores = []
        
        for score in scores:
            label = score.risk_label
            risk_distribution[label] = risk_distribution.get(label, 0) + 1
            all_scores.append((score, score.delegation.name))
        
        # Sort by composite score
        all_scores_sorted = sorted(all_scores, key=lambda x: x[0].composite_score)
        
        highest_risk = [
            {
                'delegation': s[1],
                'score': s[0].composite_score,
                'risk_label': s[0].risk_label,
            }
            for s in all_scores_sorted[-5:]
        ][::-1]  # Reverse to get highest first
        
        lowest_risk = [
            {
                'delegation': s[1],
                'score': s[0].composite_score,
                'risk_label': s[0].risk_label,
            }
            for s in all_scores_sorted[:5]
        ]
        
        # Freshness stats
        freshness_counts = {}
        for score in scores:
            status_val = score.freshness_status()
            freshness_counts[status_val] = freshness_counts.get(status_val, 0) + 1
        
        return Response({
            'summary': {
                'total_delegations': len(scores),
                'delegations_with_scores': len([s for s in scores if s.composite_score is not None]),
            },
            'risk_distribution': risk_distribution,
            'freshness': freshness_counts,
            'highest_risk': highest_risk,
            'lowest_risk': lowest_risk,
            'timestamp': timezone.now().isoformat(),  # was a hard-coded date
        })
    
    except Exception as e:
        logger.error(f'Error generating climate summary: {e}')
        return Response(
            error_body(e, where='climate'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def climate_freshness_status(request):
    """
    GET /api/climate/freshness/
    
    Returns per-delegation freshness status table for admin monitoring.
    """
    try:
        scores = DelegationClimateScore.objects.select_related('delegation').all()
        
        freshness_table = []
        for score in scores:
            freshness_table.append({
                'delegation': score.delegation.name,
                'governorate': score.delegation.region.governorate,
                'status': score.freshness_status(),
                'age_days': (timezone.now() - score.computed_at).days,
                'computed_at': score.computed_at.isoformat(),
                'score': score.composite_score,
            })
        
        # Sort by age descending (oldest first)
        freshness_table.sort(key=lambda x: x['age_days'], reverse=True)
        
        critical = [f for f in freshness_table if f['status'] == 'CRITICAL']
        stale = [f for f in freshness_table if f['status'] == 'STALE']
        warn = [f for f in freshness_table if f['status'] == 'WARN']
        fresh = [f for f in freshness_table if f['status'] == 'FRESH']
        
        return Response({
            'by_status': {
                'CRITICAL': critical,
                'STALE': stale,
                'WARN': warn,
                'FRESH': fresh,
            },
            'counts': {
                'CRITICAL': len(critical),
                'STALE': len(stale),
                'WARN': len(warn),
                'FRESH': len(fresh),
            },
            'total': len(freshness_table),
        })
    
    except Exception as e:
        logger.error(f'Error generating climate freshness status: {e}')
        return Response(
            error_body(e, where='climate'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def trigger_climate_recalibration(request):
    """
    POST /api/climate/recalibrate/
    
    Admin-only. Triggers immediate recomputation of all scores.
    Returns job ID; completion is async via Celery.
    """
    # Check admin permission (implement based on your auth model)
    if not request.user.is_staff:
        return Response(
            {'error': 'Admin access required'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from estatemind.intelligence.climate.tasks import recompute_all_climate_scores
        from django.utils import timezone
        
        # Queue the task
        task = recompute_all_climate_scores.delay()
        
        logger.info(f'Climate recalibration triggered by {request.user.username}, task_id={task.id}')
        
        # Log the recalibration event
        from estatemind.market.core.models import ClimateRecalibrationEvent
        ClimateRecalibrationEvent.objects.create(
            delegations_processed=0,
            triggered_by='api_trigger',
            status='pending',
            notes=f'API trigger by {request.user.username}, celery task_id={task.id}'
        )
        
        return Response({
            'status': 'queued',
            'task_id': task.id,
            'message': 'Climate recalibration task queued. Check task_id for progress.',
        })
    
    except Exception as e:
        logger.error(f'Error triggering climate recalibration: {e}')
        return Response(
            error_body(e, where='climate'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Import timezone for the functions
from django.utils import timezone
