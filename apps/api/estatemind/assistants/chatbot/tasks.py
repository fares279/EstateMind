"""
Celery tasks for conversational AI.
Asynchronous training, quality monitoring, and accuracy evaluation.
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import date, timedelta

logger = logging.getLogger(__name__)


@shared_task(name='estatemind.assistants.chatbot.tasks.retrain_reward_model')
def retrain_reward_model():
    """
    Monthly task to retrain RLHF reward model on accumulated feedback.
    Runs on 1st of month @ 04:00 UTC (Africa/Tunis).
    
    Returns:
        dict with training status and metrics
    """
    try:
        from estatemind.assistants.chatbot.services import RLHFRewardModel
        from estatemind.assistants.chatbot.models import RewardModelVersion
        
        logger.info('Starting reward model retraining...')
        
        reward_model = RLHFRewardModel()
        result = reward_model.train()
        
        if result['status'] == 'trained':
            # Log successful training to database
            RewardModelVersion.objects.create(
                version=result['version'],
                training_examples=result['training_examples'],
                thumbs_up_count=result['thumbs_up_count'],
                thumbs_down_count=result['thumbs_down_count'],
                cross_val_auc=result['cross_val_auc'],
                status='active'
            )
            
            logger.info(f"Reward model trained: {result['version']}")
        else:
            logger.warning(f"Reward model training {result['status']}: {result.get('reason')}")
        
        return result
        
    except Exception as e:
        logger.exception(f'Reward model retraining failed: {e}')
        return {'status': 'error', 'error': str(e)}


@shared_task(name='estatemind.assistants.chatbot.tasks.generate_quality_report')
def generate_quality_report():
    """
    Daily task to compute response quality statistics and alert on degradation.
    Runs daily @ 07:00 UTC (Africa/Tunis).
    
    Returns:
        dict with report metrics
    """
    try:
        from estatemind.assistants.chatbot.models import ChatbotResponseLog, ResponseQualityDailyReport
        from django.db.models import Avg, Count, Q
        
        logger.info('Generating daily response quality report...')
        
        # Get all responses from today
        today = date.today()
        today_responses = ChatbotResponseLog.objects.filter(
            created_at__date=today
        )
        
        if not today_responses.exists():
            logger.info('No responses today, skipping quality report')
            return {'status': 'no_data'}
        
        total = today_responses.count()
        
        # Quality distribution
        good = today_responses.filter(quality_label='GOOD').count()
        acceptable = today_responses.filter(quality_label='ACCEPTABLE').count()
        poor = today_responses.filter(quality_label='POOR').count()
        
        # Average scores
        avg_relevance = today_responses.aggregate(
            Avg('relevance_score')
        )['relevance_score__avg'] or 0.0
        
        avg_groundedness = today_responses.aggregate(
            Avg('groundedness_score')
        )['groundedness_score__avg'] or 0.0
        
        avg_overall = today_responses.aggregate(
            Avg('overall_quality_score')
        )['overall_quality_score__avg'] or 0.0
        
        # Grounding rate
        fully_grounded = today_responses.filter(is_grounded=True).count()
        grounding_rate = (fully_grounded / total) if total > 0 else 0.0
        
        # Feedback statistics
        with_feedback = today_responses.filter(user_feedback__isnull=False)
        thumbs_up = with_feedback.filter(user_feedback='thumbs_up').count()
        thumbs_down = with_feedback.filter(user_feedback='thumbs_down').count()
        feedback_rate = (with_feedback.count() / total) if total > 0 else 0.0
        
        # Top intents
        intent_counts = dict(
            today_responses.values('intent').annotate(
                count=Count('id')
            ).order_by('-count').values_list('intent', 'count')[:5]
        )
        
        # Create report
        report = ResponseQualityDailyReport.objects.create(
            report_date=today,
            total_responses=total,
            good_responses=good,
            acceptable_responses=acceptable,
            poor_responses=poor,
            avg_relevance_score=avg_relevance,
            avg_groundedness_score=avg_groundedness,
            avg_overall_score=avg_overall,
            fully_grounded_count=fully_grounded,
            grounding_rate=grounding_rate,
            total_feedback_received=with_feedback.count(),
            thumbs_up_count=thumbs_up,
            thumbs_down_count=thumbs_down,
            feedback_rate=feedback_rate,
            top_intents=intent_counts
        )
        
        logger.info(
            f'Quality report generated: {total} responses, '
            f'{avg_overall:.2%} overall, {grounding_rate:.1%} grounded'
        )
        
        # Check for degradation
        if avg_overall < 0.70:
            logger.warning(f'ALERT: Quality degradation detected. '
                          f'Overall score {avg_overall:.2f} below threshold')
        
        if grounding_rate < 0.80:
            logger.warning(f'ALERT: Grounding rate {grounding_rate:.1%} '
                          f'below target 80%')
        
        return {
            'status': 'completed',
            'report_id': report.id,
            'total_responses': total,
            'avg_overall_score': avg_overall,
            'grounding_rate': grounding_rate
        }
        
    except Exception as e:
        logger.exception(f'Quality report generation failed: {e}')
        return {'status': 'error', 'error': str(e)}


@shared_task(name='estatemind.assistants.chatbot.tasks.evaluate_intent_accuracy')
def evaluate_intent_accuracy():
    """
    Weekly task to evaluate intent classifier accuracy on recent queries.
    Runs Monday @ 03:00 UTC (Africa/Tunis).
    
    Returns:
        dict with accuracy metrics
    """
    try:
        from estatemind.assistants.chatbot.models import ChatbotResponseLog, IntentAccuracyMetric
        from estatemind.assistants.chatbot.services import IntentClassifier
        from django.db.models import Count
        
        logger.info('Evaluating intent classifier accuracy...')
        
        # Get all responses from past 7 days
        week_ago = timezone.now() - timedelta(days=7)
        test_responses = ChatbotResponseLog.objects.filter(
            created_at__gte=week_ago
        ).select_related('session')
        
        if test_responses.count() < 20:
            logger.info('Insufficient test data (need 20+), skipping')
            return {'status': 'insufficient_data', 'count': test_responses.count()}
        
        # Initialize classifier
        classifier = IntentClassifier()
        
        if not classifier.is_loaded:
            logger.warning('Intent classifier not loaded, cannot evaluate')
            return {'status': 'classifier_unavailable'}
        
        correct = 0
        accuracy_by_intent = {}
        confusion = {}
        
        for response in test_responses:
            # Re-classify the query
            result = classifier.classify(
                response.query,
                session_context=response.session.memory_snapshot
            )
            predicted_intent = result['intent']
            actual_intent = response.intent
            
            # Track accuracy
            if predicted_intent == actual_intent:
                correct += 1
            
            # Per-intent breakdown
            if actual_intent not in accuracy_by_intent:
                accuracy_by_intent[actual_intent] = {'correct': 0, 'total': 0}
            
            accuracy_by_intent[actual_intent]['total'] += 1
            if predicted_intent == actual_intent:
                accuracy_by_intent[actual_intent]['correct'] += 1
            
            # Confusion matrix
            confusion_key = f'{actual_intent}->{predicted_intent}'
            confusion[confusion_key] = confusion.get(confusion_key, 0) + 1
        
        total = test_responses.count()
        overall_accuracy = correct / total if total > 0 else 0.0
        
        # Convert per-intent breakdown to percentages
        accuracy_percentages = {
            intent: (data['correct'] / data['total'])
            for intent, data in accuracy_by_intent.items()
        }
        
        # Create metric record
        metric = IntentAccuracyMetric.objects.create(
            total_queries_tested=total,
            correct_predictions=correct,
            accuracy=overall_accuracy,
            accuracy_by_intent=accuracy_percentages,
            confusion_matrix=confusion,
            test_set_size=total
        )
        
        logger.info(
            f'Intent accuracy evaluated: {overall_accuracy:.1%} '
            f'({correct}/{total})'
        )
        
        # Check if meets target
        if overall_accuracy < 0.92:
            logger.warning(f'ALERT: Intent accuracy {overall_accuracy:.1%} '
                          f'below target 92%')
        
        return {
            'status': 'completed',
            'total_queries': total,
            'accuracy': overall_accuracy,
            'accuracy_by_intent': accuracy_percentages,
            'metric_id': metric.id
        }
        
    except Exception as e:
        logger.exception(f'Intent accuracy evaluation failed: {e}')
        return {'status': 'error', 'error': str(e)}
