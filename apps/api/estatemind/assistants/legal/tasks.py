import logging
from datetime import date

from celery import shared_task
from django.db.models import Avg, Count

logger = logging.getLogger(__name__)


@shared_task(name='legal.run_recall_validation')
def run_recall_validation(collection_name: str | None = None):
    """Retrieval recall of the active collection on data/eval_questions.json."""
    from estatemind.assistants.legal.services import chromadb_service, embedding_service
    from estatemind.assistants.legal.services.chroma_router import ChromaRouter
    from estatemind.assistants.legal.services.retrieval_quality import RetrievalQualityValidator

    collection_name = collection_name or ChromaRouter().route('all').collection
    report = RetrievalQualityValidator(chromadb_service, embedding_service).run_full_evaluation(collection_name)
    if not report['passed']:
        logger.warning('ALERT: legal retrieval recall@5 %.2f below target on %s', report['recall_at_5'],
                       collection_name)
    return report


@shared_task(name='legal.generate_quality_report')
def generate_quality_report(report_date: str | None = None):
    """Daily legal answer quality report (mirrors chatbot.generate_quality_report)."""
    from estatemind.assistants.legal.models import LegalResponseLog as Log
    from estatemind.assistants.legal.models import LegalResponseQualityDailyReport

    day = date.fromisoformat(report_date) if report_date else date.today()
    rows = Log.objects.filter(created_at__date=day)
    total = rows.count()
    if not total:
        return {'status': 'no_data', 'date': day.isoformat()}

    outcomes = dict(rows.values_list('outcome').annotate(n=Count('id')))
    answered = rows.filter(outcome__in=[Log.OUTCOME_ANSWERED, Log.OUTCOME_ANSWERED_FLAGGED])
    n_answered = answered.count()
    avgs = answered.aggregate(rel=Avg('relevance_score'), grd=Avg('groundedness_score'), ovr=Avg('overall_quality_score'))
    refusals = sum(outcomes.get(o, 0) for o in (Log.OUTCOME_NO_SOURCES, Log.OUTCOME_UNGROUNDED))
    with_feedback = rows.filter(user_feedback__isnull=False)
    fb = with_feedback.count()

    report, _ = LegalResponseQualityDailyReport.objects.update_or_create(
        report_date=day,
        defaults=dict(
            total_responses=total,
            outcome_counts=outcomes,
            answered_count=n_answered,
            refusal_rate=refusals / total,
            good_responses=answered.filter(quality_label='GOOD').count(),
            acceptable_responses=answered.filter(quality_label='ACCEPTABLE').count(),
            poor_responses=answered.filter(quality_label='POOR').count(),
            avg_relevance_score=avgs['rel'] or 0.0,
            avg_groundedness_score=avgs['grd'] or 0.0,
            avg_overall_score=avgs['ovr'] or 0.0,
            grounding_rate=(answered.filter(is_grounded=True).count() / n_answered) if n_answered else 0.0,
            total_feedback_received=fb,
            thumbs_up_count=with_feedback.filter(user_feedback='thumbs_up').count(),
            thumbs_down_count=with_feedback.filter(user_feedback='thumbs_down').count(),
            feedback_rate=fb / total,
            top_domains=dict(rows.values_list('domain').annotate(n=Count('id')).order_by('-n')[:5]),
        ),
    )
    if n_answered and report.avg_overall_score < 0.70:
        logger.warning('ALERT: legal answer quality %.2f below 0.70 on %s', report.avg_overall_score, day)
    if n_answered and report.grounding_rate < 0.80:
        logger.warning('ALERT: legal grounding rate %.1f%% below 80%% on %s', report.grounding_rate * 100, day)
    return {'status': 'completed', 'report_id': report.id, 'total_responses': total,
            'answered': n_answered, 'avg_overall_score': report.avg_overall_score,
            'grounding_rate': report.grounding_rate, 'outcomes': outcomes}


@shared_task(name='legal.retrain_reward_model')
def retrain_reward_model():
    """Monthly retrain of the legal reward model on thumbs up/down feedback."""
    from estatemind.assistants.legal.models import LegalRewardModelVersion
    from estatemind.assistants.legal.services.reward_model import LegalRewardModel

    result = LegalRewardModel().train()
    if result['status'] == 'trained':
        LegalRewardModelVersion.objects.create(
            version=result['version'], training_examples=result['training_examples'],
            thumbs_up_count=result['thumbs_up_count'], thumbs_down_count=result['thumbs_down_count'],
            cross_val_auc=result['cross_val_auc'], status='active',
        )
    else:
        logger.info('Legal reward model training %s: %s', result['status'], result.get('reason'))
    return result
