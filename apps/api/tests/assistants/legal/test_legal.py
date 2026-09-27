from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIClient

from estatemind.assistants.legal.models import LegalResponseLog, LegalSession
from estatemind.assistants.legal.services import llm_service
from estatemind.assistants.legal.services.citation_builder import Citation
from estatemind.assistants.legal.services.dataset_service import repair_mojibake
from estatemind.assistants.legal.services.hallucination_detector import FAIL, FLAG, PASS, HallucinationDetector
from estatemind.assistants.legal.services.quality_monitor import LegalResponseQualityMonitor
from estatemind.assistants.legal.services.rag_engine import LegalAssistant
from estatemind.assistants.legal.services.retrieval_quality import load_eval_questions
from estatemind.assistants.legal.services.retriever import Passage, RetrievalResult

PASSAGE_58 = ("Art. 58.- Sont enregistrés au droit fixe les contrats relatifs à l'acquisition auprès des "
              "promoteurs immobiliers de bâtiments ou terrains aménagés pour l'exercice d'activités économiques "
              "ou de terrains destinés à la construction d'immeubles à usage d'habitation.")


class TestMojibakeRepair(TestCase):
    def test_corrupted_words_are_repaired(self):
        cases = {'dèlai': 'délai', 'mobiliçres': 'mobilières', 'àŠtre': 'être', 'clàīture': 'clôture',
                 'enregistrès': 'enregistrés', "l'àtat": "l'État", 'prèsent': 'présent'}
        for bad, good in cases.items():
            self.assertEqual(repair_mojibake(bad), good, bad)

    def test_genuine_accents_are_kept(self):
        for word in ('hypothèque', 'règles', 'règlement', 'première', 'après', 'façon', 'déjà'):
            self.assertEqual(repair_mojibake(word), word)


class TestDomainClassifier(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from estatemind.assistants.legal.services.domain_classifier import LegalDomainClassifier
        cls.classifier = LegalDomainClassifier()

    def test_keyword_domains(self):
        self.assertEqual(self.classifier.classify('What is the capital gains tax rate?')['primary_domain'],
                         'taxation')
        self.assertEqual(self.classifier.classify('Can a foreign national buy property in Tunisia?')
                         ['primary_domain'], 'foreign_ownership')
        self.assertEqual(self.classifier.classify('How is property distributed among heirs?')['primary_domain'],
                         'inheritance')

    def test_scope_on_eval_set(self):
        wrong = []
        for q in load_eval_questions():
            expected = q['category'] != 'out_of_scope'
            if self.classifier.classify(q['question'])['in_scope'] != expected:
                wrong.append(q['id'])
        self.assertEqual(wrong, [])


class TestHallucinationDetector(TestCase):
    def test_reads_lowercase_nli_labels(self):
        # The real NLI models emit lowercase labels; the old detector compared
        # against 'ENTAILMENT' and scored every sentence 0.0.
        det = HallucinationDetector.__new__(HallucinationDetector)
        det._nli_available = True
        with patch.object(HallucinationDetector, '_pipe', MagicMock(return_value=[[
            {'label': 'entailment', 'score': 0.91}, {'label': 'neutral', 'score': 0.06},
            {'label': 'contradiction', 'score': 0.03},
        ]])):
            self.assertEqual(det._entailment_scores([('premise', 'hypothesis')]), [0.91])

    def test_configured_model_labels_include_entailment(self):
        det = HallucinationDetector()
        if det._nli_available:
            labels = {v.lower() for v in HallucinationDetector._pipe.model.config.id2label.values()}
            self.assertIn('entailment', labels)

    def test_supported_and_unsupported_sentences(self):
        det = HallucinationDetector()
        if not det._nli_available:
            self.skipTest('NLI model not available')
        good = det.check_answer("Les contrats d'acquisition de terrains destinés à la construction de logements "
                                "auprès des promoteurs immobiliers sont enregistrés au droit fixe [1].", [PASSAGE_58])
        bad = det.check_answer('Registration duty on property purchases is 5% of the purchase price [1].',
                               [PASSAGE_58])
        self.assertEqual(good['decision'], PASS)
        self.assertEqual(bad['decision'], FAIL)

    def test_disclaimers_are_not_checked(self):
        det = HallucinationDetector.__new__(HallucinationDetector)
        det._nli_available = False
        result = det.check_answer('Please consult a notary for your specific case.', ['anything'])
        self.assertEqual(result['total_sentences'], 0)
        self.assertEqual(result['decision'], PASS)

    def test_decide_thresholds(self):
        det = HallucinationDetector.__new__(HallucinationDetector)
        self.assertEqual(det.decide(1.0, 3), PASS)
        self.assertEqual(det.decide(0.6, 5), FLAG)
        self.assertEqual(det.decide(0.2, 5), FAIL)


class TestCitationBuilder(TestCase):
    def test_confidence_labels(self):
        high = Citation(source_id='t1', law_name='Law', article='Art. 1', passage_text='x', similarity=0.92, rank=1)
        low = Citation(source_id='t2', law_name='Law', article='Art. 2', passage_text='x', similarity=0.55, rank=5)
        self.assertEqual(high.confidence_label, 'HIGH')
        self.assertEqual(low.confidence_label, 'LOW')


class TestQualityMonitor(TestCase):
    def test_citation_score_counts_valid_references(self):
        grounding = {'sentences': [{'sentence': 'A [1].'}, {'sentence': 'B [7].'}, {'sentence': 'C.'},
                                   {'sentence': 'D [1, 2].'}]}
        self.assertEqual(LegalResponseQualityMonitor.citation_score(grounding, n_passages=2), 0.5)


# ── Pipeline, with fake retrieval and LLM ────────────────────────────────────

def _passage(sim=0.8):
    return Passage(rank=1, text=PASSAGE_58, similarity=sim,
                   metadata={'chunk_id': 'c1', 'law_name': "Code d'Incitation aux Investissements",
                             'article_ref': 'Art. 58', 'article_index': 13})


class _FakeClassifier:
    def __init__(self, in_scope=True):
        self.in_scope = in_scope

    def classify(self, q):
        return {'primary_domain': 'transactions', 'confidence': 0.8, 'in_scope': self.in_scope}


class _FakeRetriever:
    def __init__(self, sufficient=True):
        self.sufficient = sufficient
        self.queries = []

    def retrieve(self, query, domain):
        self.queries.append(query)
        p = _passage(0.8 if self.sufficient else 0.3)
        return RetrievalResult(passages=[p], collection='legal_test', embedding_model='test-model',
                               top_similarity=p.similarity, sufficient=self.sufficient,
                               context_passages=[p] if self.sufficient else [])


class _FakeDetector:
    def __init__(self, decisions):
        self.decisions = list(decisions)

    def check_answer(self, answer, passages):
        d = self.decisions.pop(0)
        s = {'sentence': answer, 'entailment_score': 0.9 if d == PASS else 0.1, 'grounded': d == PASS,
             'display_text': answer if d == PASS else f'[Unverified against retrieved sources: {answer}]'}
        return {'sentences': [s], 'exempt_sentences': [], 'grounded_ratio': 1.0 if d == PASS else 0.0,
                'ungrounded_sentences': [] if d == PASS else [answer], 'decision': d}

    @staticmethod
    def _split_sentences(text):
        return [text]


class _FakeQuality:
    def evaluate(self, question, answer, grounding, n):
        return {'relevance': 0.8, 'groundedness': grounding['grounded_ratio'], 'citation_score': 1.0,
                'length_appropriate': True, 'overall': 0.9, 'quality_label': 'GOOD'}


_REWARD = SimpleNamespace(predict_quality=lambda q, a: 0.5)
ANSWER = 'Acquisitions from property developers of land for housing are registered at the fixed duty [1].'


def _assistant(in_scope=True, sufficient=True, decisions=(PASS,)):
    return LegalAssistant(_FakeClassifier(in_scope), _FakeRetriever(sufficient), _FakeDetector(decisions),
                          _FakeQuality(), _REWARD)


class TestLegalAssistantPipeline(TestCase):
    def test_answered_and_logged(self):
        with patch.object(llm_service, 'chat', return_value=ANSWER) as chat:
            result = _assistant().answer('Which acquisitions pay the fixed registration duty?')
        self.assertEqual(result['outcome'], LegalResponseLog.OUTCOME_ANSWERED)
        self.assertEqual(chat.call_count, 1)
        self.assertEqual(result['citations'][0]['article'], 'Art. 58')
        log = LegalResponseLog.objects.get(id=result['response_log_id'])
        self.assertEqual(log.quality_label, 'GOOD')
        self.assertEqual(log.collection_used, 'legal_test')
        self.assertTrue(log.is_grounded)

    def test_out_of_scope_skips_retrieval_and_llm(self):
        assistant = _assistant(in_scope=False)
        with patch.object(llm_service, 'chat') as chat:
            result = assistant.answer('What is the price per m2 in La Marsa?')
        self.assertEqual(result['outcome'], LegalResponseLog.OUTCOME_OUT_OF_SCOPE)
        self.assertEqual(assistant.retriever.queries, [])
        chat.assert_not_called()

    def test_no_relevant_source_refuses_without_llm(self):
        with patch.object(llm_service, 'chat') as chat:
            result = _assistant(sufficient=False).answer('Can a foreigner buy an apartment?')
        self.assertEqual(result['outcome'], LegalResponseLog.OUTCOME_NO_SOURCES)
        self.assertEqual(result['citations'], [])
        chat.assert_not_called()

    def test_ungrounded_answer_is_regenerated_then_refused(self):
        with patch.object(llm_service, 'chat', return_value='Registration duty is 5% [1].') as chat:
            result = _assistant(decisions=(FAIL, FAIL)).answer('What is the registration duty?')
        self.assertEqual(chat.call_count, 2)
        strict_system = chat.call_args_list[1].args[0][0]['content']
        self.assertIn('previous answer contained statements', strict_system)
        self.assertEqual(result['outcome'], LegalResponseLog.OUTCOME_UNGROUNDED)
        self.assertNotIn('5%', result['answer'])

    def test_regenerated_answer_that_passes_is_returned(self):
        with patch.object(llm_service, 'chat', side_effect=['Duty is 5% [1].', ANSWER]):
            result = _assistant(decisions=(FAIL, PASS)).answer('What is the registration duty?')
        self.assertEqual(result['outcome'], LegalResponseLog.OUTCOME_ANSWERED)
        self.assertEqual(result['answer'], ANSWER)

    def test_flagged_answer_marks_unverified_sentences(self):
        with patch.object(llm_service, 'chat', return_value=ANSWER):
            result = _assistant(decisions=(FLAG,)).answer('Which contracts pay the fixed duty?')
        self.assertEqual(result['outcome'], LegalResponseLog.OUTCOME_ANSWERED_FLAGGED)
        self.assertIn('Unverified', result['answer'])

    def test_llm_unavailable_still_returns_sources(self):
        with patch.object(llm_service, 'chat', side_effect=llm_service.LLMUnavailable('down')):
            result = _assistant().answer('Which contracts pay the fixed duty?')
        self.assertEqual(result['outcome'], LegalResponseLog.OUTCOME_LLM_UNAVAILABLE)
        self.assertEqual(len(result['citations']), 1)

    def test_session_memory_and_follow_up_retrieval(self):
        assistant = _assistant(decisions=(PASS, PASS))
        with patch.object(llm_service, 'chat', return_value=ANSWER) as chat:
            first = assistant.answer('Which property acquisition contracts pay the fixed duty?')
            second = assistant.answer('And for commercial buildings?', session_id=first['session_id'])
        self.assertEqual(second['turn_index'], 1)
        self.assertIn('fixed duty', assistant.retriever.queries[1])
        history_roles = [m['role'] for m in chat.call_args_list[1].args[0]]
        self.assertEqual(history_roles, ['system', 'user', 'assistant', 'user'])
        self.assertEqual(LegalSession.objects.get(session_id=first['session_id']).turn_count, 2)


class TestLegalViews(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_ask_feedback_and_session(self):
        with patch('estatemind.assistants.legal.services.rag_engine.get_assistant', return_value=_assistant()), \
                patch.object(llm_service, 'chat', return_value=ANSWER):
            r = self.client.post('/api/legal/ask/', {'question': 'Which contracts pay the fixed duty?'},
                                 format='json')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        for key in ('answer', 'sources', 'citations', 'session_id', 'outcome', 'response_log_id', 'quality_label'):
            self.assertIn(key, body)

        fb = self.client.post('/api/legal/feedback/', {'response_log_id': body['response_log_id'],
                                                       'feedback': 'thumbs_up'}, format='json')
        self.assertEqual(fb.status_code, 200)
        self.assertEqual(LegalResponseLog.objects.get(id=body['response_log_id']).user_feedback, 'thumbs_up')

        s = self.client.get('/api/legal/session/', {'session_id': body['session_id']})
        self.assertEqual(s.json()['turn_count'], 1)

    def test_ask_returns_503_when_llm_unreachable(self):
        with patch('estatemind.assistants.legal.services.rag_engine.get_assistant', return_value=_assistant()), \
                patch.object(llm_service, 'chat', side_effect=llm_service.LLMUnavailable('down')):
            r = self.client.post('/api/legal/ask/', {'question': 'Which contracts pay the fixed duty?'},
                                 format='json')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(len(r.json()['sources']), 1)

    def test_feedback_rejects_bad_payloads(self):
        self.assertEqual(self.client.post('/api/legal/feedback/', {'feedback': 'meh'}, format='json').status_code,
                         400)
        self.assertEqual(self.client.post('/api/legal/feedback/', {'feedback': 'thumbs_up'}, format='json')
                         .status_code, 400)

    def test_status_reports_unreachable_llm(self):
        import requests
        llm_service._availability_cache.clear()
        with patch.object(llm_service.requests, 'get', side_effect=requests.exceptions.ConnectionError('dns')):
            self.assertFalse(llm_service.check_availability(force=True))
        llm_service._availability_cache.clear()


class TestLegalRewardModel(TestCase):
    def test_uses_legal_feedback_rows(self):
        from estatemind.assistants.legal.services.reward_model import LegalRewardModel
        session = LegalSession.objects.create(session_id='s1')
        LegalResponseLog.objects.create(session=session, turn_index=0, question='q', answer='a', outcome='answered',
                                        user_feedback='thumbs_up')
        LegalResponseLog.objects.create(session=session, turn_index=1, question='q2', answer='', outcome='out_of_scope',
                                        user_feedback='thumbs_down')
        rows = LegalRewardModel()._labeled_examples()
        self.assertEqual(rows, [{'query': 'q', 'response': 'a', 'user_feedback': 'thumbs_up'}])
        self.assertEqual(LegalRewardModel().train()['reason'], 'insufficient_data')
