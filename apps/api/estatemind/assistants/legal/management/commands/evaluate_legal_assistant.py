"""Run data/eval_questions.json through the legal assistant and report quality.

Every question goes through the full pipeline (classification, retrieval,
generation, grounding gate, quality scoring) and is logged in
LegalResponseLog like a user question, under one evaluation session. The
report covers routing (did each kind of question get the right outcome), the
sources returned, and the quality/groundedness scores of generated answers,
next to the chatbot's scores for comparison.

    python manage.py evaluate_legal_assistant [--json report.json]
"""
import json
import statistics
import time
import uuid
from collections import Counter

from django.core.management.base import BaseCommand

from estatemind.assistants.legal.services.retrieval_quality import gold_match
from django.db.models import Avg

from estatemind.assistants.legal.models import LegalResponseLog as Log
from estatemind.assistants.legal.services import chromadb_service
from estatemind.assistants.legal.services.rag_engine import get_assistant
from estatemind.assistants.legal.services.retrieval_quality import load_eval_questions

EXPECTED = {
    'answerable': {Log.OUTCOME_ANSWERED, Log.OUTCOME_ANSWERED_FLAGGED, Log.OUTCOME_LLM_UNAVAILABLE},
    'unanswerable': {Log.OUTCOME_NO_SOURCES, Log.OUTCOME_UNGROUNDED},
    'out_of_scope': {Log.OUTCOME_OUT_OF_SCOPE, Log.OUTCOME_NO_SOURCES},
}


def _mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 3) if values else None


class Command(BaseCommand):
    help = 'Evaluate the legal assistant end to end on data/eval_questions.json.'

    def add_arguments(self, parser):
        parser.add_argument('--json', help='Also write the full report to this file.')
        parser.add_argument('--routing-cv', action='store_true',
                            help='Only report the leave-one-out estimate of the scope decision (no LLM needed).')

    def handle(self, *args, **options):
        if options.get('routing_cv'):
            from estatemind.assistants.legal.services.domain_classifier import routing_cross_validation
            report = routing_cross_validation(load_eval_questions())
            self.stdout.write(json.dumps(report, indent=1))
            return
        assistant = get_assistant()
        rows = []
        for q in load_eval_questions():
            # one session per question: follow-up handling must not mix questions
            session_id = f'eval-{uuid.uuid4().hex[:12]}'
            started = time.monotonic()
            result = assistant.answer(q['question'], session_id=session_id)
            elapsed = time.monotonic() - started
            log = Log.objects.get(id=result['response_log_id'])
            gold_hit = None
            if q['category'] == 'answerable' and result['citations']:
                col = chromadb_service._get_collection_by_name(log.collection_used)
                metas = col.get(ids=[c['source_id'] for c in result['citations']], include=['metadatas'])['metadatas']
                gold_hit = any(gold_match(m, q['gold']) for m in metas)
            rows.append({
                'id': q['id'], 'category': q['category'], 'lang': q['lang'], 'outcome': log.outcome,
                'routed_ok': log.outcome in EXPECTED[q['category']], 'gold_in_sources': gold_hit,
                'top_similarity': log.retrieval_top_similarity, 'quality_label': log.quality_label,
                'overall': log.overall_quality_score, 'groundedness': log.groundedness_score,
                'relevance': log.relevance_score, 'citation_score': log.citation_score,
                'attempts': log.generation_attempts, 'seconds': round(elapsed, 2),
                'answer': log.answer,
            })

        generated = [r for r in rows if r['outcome'] in (Log.OUTCOME_ANSWERED, Log.OUTCOME_ANSWERED_FLAGGED)]
        from estatemind.assistants.chatbot.models import ChatbotResponseLog
        chatbot = ChatbotResponseLog.objects.aggregate(
            overall=Avg('overall_quality_score'), groundedness=Avg('groundedness_score'),
            relevance=Avg('relevance_score'))
        report = {
            'questions': len(rows),
            'outcomes': dict(Counter(r['outcome'] for r in rows)),
            'routing_accuracy': {
                cat: f"{sum(r['routed_ok'] for r in rows if r['category'] == cat)}/"
                     f"{sum(1 for r in rows if r['category'] == cat)}" for cat in EXPECTED},
            'answerable_gold_in_sources': f"{sum(1 for r in rows if r['gold_in_sources'])}/"
                                          f"{sum(1 for r in rows if r['gold_in_sources'] is not None)}",
            'generated_answers': len(generated),
            'legal_quality': {
                'overall': _mean(r['overall'] for r in generated),
                'groundedness': _mean(r['groundedness'] for r in generated),
                'relevance': _mean(r['relevance'] for r in generated),
                'citation_score': _mean(r['citation_score'] for r in generated),
                'labels': dict(Counter(r['quality_label'] for r in generated)),
                'regenerated': sum(1 for r in rows if r['attempts'] > 1),
            },
            'chatbot_quality_all_time': {k: round(v, 3) if v is not None else None for k, v in chatbot.items()},
            'median_seconds': statistics.median(r['seconds'] for r in rows),
        }
        self.stdout.write(json.dumps(report, indent=1, ensure_ascii=False))
        if not generated:
            self.stdout.write(self.style.WARNING(
                'No answers were generated (LLM unreachable?) — quality scores need a reachable LLM.'))
        if options.get('json'):
            with open(options['json'], 'w', encoding='utf-8') as fh:
                json.dump({'summary': report, 'rows': rows}, fh, indent=1, ensure_ascii=False)
