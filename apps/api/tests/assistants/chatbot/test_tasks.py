from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from estatemind.assistants.chatbot import tasks
from estatemind.assistants.chatbot.models import (ChatbotResponseLog, ChatbotSession, IntentAccuracyMetric,
                                                  ResponseQualityDailyReport)
from estatemind.assistants.chatbot.services import intent_data


class QualityReportTests(TestCase):
    def test_reports_yesterday_and_can_be_rerun(self):
        session = ChatbotSession.objects.create(session_id='s1')
        log = ChatbotResponseLog.objects.create(session=session, intent='market_inquiry', query='q', response='r', turn_index=0,
                                                quality_label='GOOD', overall_quality_score=0.9, is_grounded=True)
        ChatbotResponseLog.objects.filter(pk=log.pk).update(created_at=timezone.now() - timedelta(days=1))
        first = tasks.generate_quality_report()
        second = tasks.generate_quality_report()  # used to crash on the unique report_date
        self.assertEqual(first['status'], 'completed', first)
        self.assertEqual(second['status'], 'completed', second)
        self.assertEqual(ResponseQualityDailyReport.objects.count(), 1)
        self.assertEqual(ResponseQualityDailyReport.objects.get().report_date, timezone.localdate() - timedelta(days=1))


class IntentAccuracyTaskTests(TestCase):
    def test_scores_against_the_labelled_set(self):
        rows = intent_data.evaluation_set()

        class Oracle:  # right on everything except greetings
            is_loaded = True

            def classify(self, text):
                label = next(r['intent'] for r in rows if r['text'] == text)
                return {'intent': 'market_inquiry' if label == 'general_greeting' else label}

        result = tasks.evaluate_intent_accuracy(classifier=Oracle())
        greetings = sum(r['intent'] == 'general_greeting' for r in rows)
        self.assertEqual(result['status'], 'completed', result)
        self.assertAlmostEqual(result['accuracy'], (len(rows) - greetings) / len(rows))
        self.assertEqual(IntentAccuracyMetric.objects.get().test_set_size, len(rows))
