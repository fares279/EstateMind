from django.test import SimpleTestCase

from estatemind.assistants.legal.services.domain_classifier import routing_cross_validation


class _Stub:
    """scope_scores from a table: (legal, non_legal) per question."""

    def __init__(self, scores):
        self.scores = scores

    def classify(self, question):
        legal, non_legal = self.scores[question]
        return {'scope_scores': {'legal': legal, 'non_legal': non_legal}}


class RoutingCrossValidationTests(SimpleTestCase):
    def test_separable_questions_score_perfectly(self):
        scores = {f'legal {i}': (0.7, 0.3) for i in range(5)} | {f'price {i}': (0.3, 0.7) for i in range(5)}
        questions = [{'question': q, 'category': 'out_of_scope' if q.startswith('price') else 'answerable'}
                     for q in scores]
        report = routing_cross_validation(questions, classifier=_Stub(scores))
        self.assertEqual((report['in_sample_correct'], report['leave_one_out_correct']), (10, 10))

    def test_a_question_only_its_own_threshold_fits_is_missed_when_held_out(self):
        # one non-legal question sits where only a very low threshold catches it; held out,
        # the others pick thresholds that miss it
        scores = {f'legal {i}': (0.60, 0.50) for i in range(6)} | {'odd price': (0.30, 0.36)} | \
                 {f'price {i}': (0.30, 0.70) for i in range(4)}
        questions = [{'question': q, 'category': 'out_of_scope' if 'price' in q else 'answerable'} for q in scores]
        report = routing_cross_validation(questions, classifier=_Stub(scores))
        self.assertLess(report['leave_one_out_correct'], len(questions))
