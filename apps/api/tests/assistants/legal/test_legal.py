from unittest.mock import MagicMock, patch

from django.test import TestCase

from estatemind.assistants.legal.services.citation_builder import Citation
from estatemind.assistants.legal.services.domain_classifier import LegalDomainClassifier
from estatemind.assistants.legal.services.hallucination_detector import HallucinationDetector


class TestDomainClassifier(TestCase):
    @patch('estatemind.assistants.legal.services.domain_classifier.pipeline')
    def test_taxation_keyword_routing(self, mock_pipeline):
        mock_pipeline.return_value = MagicMock()
        classifier = LegalDomainClassifier()
        result = classifier.classify('What is the capital gains tax rate?')
        self.assertEqual(result['primary_domain'], 'taxation')
        self.assertEqual(result['method'], 'keyword')

    @patch('estatemind.assistants.legal.services.domain_classifier.pipeline')
    def test_foreign_ownership_routing(self, mock_pipeline):
        mock_pipeline.return_value = MagicMock()
        classifier = LegalDomainClassifier()
        result = classifier.classify('Can a foreign national buy property in Tunisia?')
        self.assertEqual(result['primary_domain'], 'foreign_ownership')
        self.assertEqual(result['method'], 'keyword')

    @patch('estatemind.assistants.legal.services.domain_classifier.pipeline')
    def test_inheritance_routing(self, mock_pipeline):
        mock_pipeline.return_value = MagicMock()
        classifier = LegalDomainClassifier()
        result = classifier.classify('How is property distributed among heirs?')
        self.assertEqual(result['primary_domain'], 'inheritance')
        self.assertEqual(result['method'], 'keyword')


class TestCitationBuilder(TestCase):
    def test_confidence_labels(self):
        high_citation = Citation(
            source_id='test_1',
            law_name='Test Law',
            article='Art. 1',
            passage_text='Test passage',
            similarity=0.92,
            rank=1,
        )
        self.assertEqual(high_citation.confidence_label, 'HIGH')

        low_citation = Citation(
            source_id='test_2',
            law_name='Test Law',
            article='Art. 2',
            passage_text='Test passage',
            similarity=0.55,
            rank=5,
        )
        self.assertEqual(low_citation.confidence_label, 'LOW')


class TestHallucinationDetector(TestCase):
    @patch('estatemind.assistants.legal.services.hallucination_detector.pipeline')
    def test_grounded_sentence_passes(self, mock_pipeline):
        mock_nli = MagicMock()
        mock_nli.return_value = [{'label': 'ENTAILMENT', 'score': 0.92}]
        mock_pipeline.return_value = mock_nli

        detector = HallucinationDetector()
        result = detector.check_answer(
            'Capital gains tax is 25% if held less than 2 years.',
            ['The tax rate for individuals is 25% for holdings under 2 years.'],
        )
        self.assertGreater(result['average_score'], 0.70)
        self.assertTrue(result['answer_grounded'])
        self.assertEqual(result['total_sentences'], 1)
