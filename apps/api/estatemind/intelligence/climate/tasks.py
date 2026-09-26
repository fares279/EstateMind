import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from estatemind.market.core.models import Delegation, DelegationClimateScore, ClimateRecalibrationEvent
from estatemind.intelligence.climate.services import ClimateCompositeScorer, KrigingClimateService

logger = logging.getLogger(__name__)


@shared_task(name='estatemind.intelligence.climate.tasks.recompute_all_climate_scores')
def recompute_all_climate_scores():
    """
    Runs every 6 months (1st of Jan and Jul at 02:00).
    Recomputes composite climate scores for all delegations.
    Logs significant changes (delta > 0.05) for audit.
    Triggers kriging surface rebuild after completion.
    """
    import time
    start_time = time.time()
    
    scorer = ClimateCompositeScorer()
    results = {
        'processed': 0,
        'significant_changes': [],
        'errors': []
    }
    
    try:
        for delegation in Delegation.objects.all():
            try:
                # Get previous score for change detection
                try:
                    previous = DelegationClimateScore.objects.get(
                        delegation=delegation
                    )
                    previous_score = previous.composite_score
                except DelegationClimateScore.DoesNotExist:
                    previous_score = None
                
                # Compute new score
                new_score = scorer.compute(delegation)
                
                # Detect significant changes
                if previous_score is not None:
                    delta = abs(new_score['composite_score'] - previous_score)
                    if delta > 0.05:
                        results['significant_changes'].append({
                            'delegation': delegation.name,
                            'previous_score': round(previous_score, 4),
                            'new_score': new_score['composite_score'],
                            'delta': round(delta, 4),
                            'direction': 'worsened' if new_score['composite_score'] > previous_score else 'improved'
                        })
                
                # Save to database (update or create)
                DelegationClimateScore.objects.update_or_create(
                    delegation=delegation,
                    defaults={
                        'composite_score': new_score['composite_score'],
                        'composite_uncertainty': new_score['composite_uncertainty'],
                        'ci_lower_95': new_score['ci_lower_95'],
                        'ci_upper_95': new_score['ci_upper_95'],
                        'risk_label': new_score['risk_label'],
                        'flood_risk_score': new_score['factors']['flood_risk']['score'],
                        'flood_risk_uncertainty': new_score['factors']['flood_risk']['uncertainty'],
                        'heat_stress_score': new_score['factors']['heat_stress']['score'],
                        'heat_stress_uncertainty': new_score['factors']['heat_stress']['uncertainty'],
                        'coastal_erosion_score': new_score['factors']['coastal_erosion']['score'],
                        'coastal_erosion_uncertainty': new_score['factors']['coastal_erosion']['uncertainty'],
                        'infrastructure_resilience_score': new_score['factors']['infrastructure_resilience']['score'],
                        'infrastructure_resilience_uncertainty': new_score['factors']['infrastructure_resilience']['uncertainty'],
                        'wildfire_risk_score': new_score['factors']['wildfire_risk']['score'],
                        'wildfire_risk_uncertainty': new_score['factors']['wildfire_risk']['uncertainty'],
                        'computed_at': timezone.now(),
                        'data_vintage': timezone.now().date(),
                        'computation_method': 'composite_weighted',
                    }
                )
                
                results['processed'] += 1
                
            except Exception as e:
                results['errors'].append({
                    'delegation': delegation.name,
                    'error': str(e)
                })
                logger.error(f'Climate score recomputation failed for {delegation.name}: {e}')
        
        # Log significant changes to alert team
        if results['significant_changes']:
            logger.warning(
                f"Climate recalibration detected {len(results['significant_changes'])} "
                f"significant score changes: {results['significant_changes']}"
            )
        
        # Rebuild kriging surface after all scores updated
        kriging = KrigingClimateService.get_instance()
        kriging.invalidate()
        surface_built = kriging.build_surface()
        if not surface_built:
            logger.warning('Kriging surface rebuild failed during recalibration')
        
        # Record event in audit log
        duration_seconds = time.time() - start_time
        status = 'success' if not results['errors'] else 'partial'
        
        ClimateRecalibrationEvent.objects.create(
            delegations_processed=results['processed'],
            delegations_changed_significantly=len(results['significant_changes']),
            significant_changes=results['significant_changes'],
            errors=results['errors'],
            triggered_by='celery_beat',
            duration_seconds=duration_seconds,
            status=status,
            notes=f"Processed {results['processed']} delegations, "
                  f"{len(results['significant_changes'])} significant changes, "
                  f"{len(results['errors'])} errors"
        )
        
        logger.info(
            f'Climate recalibration complete: '
            f'{results["processed"]} processed, '
            f'{len(results["significant_changes"])} changed, '
            f'{len(results["errors"])} errors, '
            f'{duration_seconds:.1f}s'
        )
        
        return results
    
    except Exception as e:
        logger.error(f'Climate recalibration task failed: {e}', exc_info=True)
        ClimateRecalibrationEvent.objects.create(
            delegations_processed=results['processed'],
            delegations_changed_significantly=len(results['significant_changes']),
            significant_changes=results['significant_changes'],
            errors=results['errors'] + [{'error': str(e)}],
            triggered_by='celery_beat',
            duration_seconds=time.time() - start_time,
            status='failure',
            notes=f'Task failed: {str(e)}'
        )
        raise


@shared_task(name='estatemind.intelligence.climate.tasks.check_freshness_and_alert')
def check_freshness_and_alert():
    """
    Runs daily at 06:00.
    Checks if any delegations have STALE or CRITICAL freshness status.
    Logs warning if found.
    """
    stale_scores = DelegationClimateScore.objects.filter()
    
    critical_count = 0
    stale_count = 0
    
    for score in stale_scores:
        status = score.freshness_status()
        if status == 'CRITICAL':
            critical_count += 1
        elif status == 'STALE':
            stale_count += 1
    
    if critical_count > 0 or stale_count > 0:
        logger.warning(
            f'Climate score freshness alert: '
            f'{critical_count} CRITICAL, '
            f'{stale_count} STALE'
        )
    
    logger.info(
        f'Climate freshness check complete: '
        f'{critical_count} critical, {stale_count} stale scores'
    )
    
    return {
        'critical': critical_count,
        'stale': stale_count,
    }
