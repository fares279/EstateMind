"""Legal assistant pipeline.

Same shape as the chatbot's chat_message pipeline:
  1. load session + rolling memory
  2. classify: legal or not, and which domain
  3. retrieve legal passages; stop if none is relevant enough
  4. generate an answer from the passages (with recent conversation)
  5. check grounding sentence by sentence; regenerate once, then refuse
  6. score quality, predict reward
  7. log the turn (quality, sources, outcome) and update memory
"""
import logging
import re
import time
import uuid

from django.core.cache import cache

from estatemind.assistants.chatbot.services.conversation_memory import ConversationMemory
from estatemind.assistants.conversation_facts import (
    extract_user_name, is_name_question, name_acknowledgement, name_response,
)
from estatemind.assistants.legal.models import LegalResponseLog, LegalSession

from . import llm_service, prompts
from .citation_builder import Citation
from .hallucination_detector import FAIL, FLAG

logger = logging.getLogger(__name__)

SESSION_TTL = 60 * 30
_FOLLOW_UP = ('it', 'this', 'that', 'they', 'them', 'those', 'ce', 'cela', 'ça', 'cette', 'ces', 'il', 'elle')

O = LegalResponseLog
FOLLOW_UP_MIN_CONFIDENCE = 0.5


def _memory_key(session_id: str) -> str:
    return f'legal_memory_{session_id}'


def _load_session(session_id: str | None, user=None):
    session_id = session_id or str(uuid.uuid4())
    session, _ = LegalSession.objects.get_or_create(session_id=session_id)
    if user is not None and getattr(user, 'is_authenticated', False) and session.user_id is None:
        session.user = user
        session.save(update_fields=['user'])
    data = cache.get(_memory_key(session_id)) or session.memory_snapshot
    memory = ConversationMemory.deserialize(session_id, data) if data else ConversationMemory(session_id)
    return session, memory


def _save_session(session: LegalSession, memory: ConversationMemory, domain: str):
    data = memory.serialize()
    cache.set(_memory_key(session.session_id), data, SESSION_TTL)
    session.memory_snapshot = data
    session.turn_count = memory.turn_count
    session.last_domain = domain or session.last_domain
    session.save(update_fields=['memory_snapshot', 'turn_count', 'last_domain', 'last_active_at'])


def _retrieval_query(question: str, memory: ConversationMemory) -> str:
    """Short follow-ups ("and for foreigners?") are searched together with the previous question."""
    words = question.lower().split()
    if memory.recent_turns and (len(words) <= 6 or any(w.strip('?,.') in _FOLLOW_UP for w in words[:3])):
        return f"{memory.recent_turns[-1]['user']} {question}"
    return question


def _citations(passages) -> list[dict]:
    return [
        Citation(source_id=p.source_id, law_name=p.metadata.get('law_name', ''),
                 article=p.metadata.get('article_ref', ''), passage_text=p.text,
                 similarity=p.similarity, rank=i).to_dict()
        for i, p in enumerate(passages, start=1)
    ]


_GREETING = re.compile(
    r"^\W*(hello|hi|hey|good (morning|afternoon|evening)|bonjour|bonsoir|salut|salam|marhaba|"
    r"مرحبا|السلام عليكم|أهلا)\b[\W]*$", re.IGNORECASE)
_THANKS = re.compile(r"^\W*(thanks?( you)?|merci( beaucoup)?|شكرا)\b[\W]*$", re.IGNORECASE)
_CAPABILITIES = re.compile(
    r"^\W*(who are you|what (can|do) you (do|know)|help|aide|que (sais|peux)-tu faire|qui es-tu)\W*$",
    re.IGNORECASE)


def _small_talk(question: str) -> str | None:
    """'greeting' for a greeting or 'what can you do', 'thanks' for thanks, else None.
    Whole messages only: 'hello, what are the registration fees?' is a real question."""
    text = question.strip()
    if _THANKS.match(text):
        return 'thanks'
    if _GREETING.match(text) or _CAPABILITIES.match(text):
        return 'greeting'
    return None


class LegalAssistant:
    def __init__(self, classifier, retriever, detector, quality_monitor, reward_model):
        self.classifier = classifier
        self.retriever = retriever
        self.detector = detector
        self.quality = quality_monitor
        self.reward = reward_model

    def answer(self, question: str, session_id: str | None = None, user=None) -> dict:
        started = time.monotonic()
        question = question.strip()[:2000]
        session, memory = _load_session(session_id, user)
        language = prompts.detect_language(question)
        log = {'language': language, 'generation_attempts': 0, 'llm_model': ''}
        answer_text, citations, grounding, quality = '', [], {}, {}

        # 1b. personal facts, as in the market chatbot ("my name is Bob" / "what is my name?")
        stated_name = extract_user_name(question)
        if stated_name:
            memory.extracted_facts['user_name'] = stated_name
        if stated_name or is_name_question(question):
            reply = (name_acknowledgement(stated_name, language) if stated_name
                     else name_response(memory.extracted_facts.get('user_name'), language))
            memory.add_turn(user_message=question, assistant_response=reply, intent='conversation', entities={})
            _save_session(session, memory, session.last_domain)
            return {'session_id': session.session_id, 'turn_index': memory.turn_count - 1, 'response_log_id': None,
                    'outcome': O.OUTCOME_CONVERSATION, 'answer': reply, 'language': language,
                    'domain': 'conversation', 'in_scope': True, 'citations': [], 'sentences': [],
                    'grounding_score': None, 'grounding_label': None, 'quality_label': None,
                    'overall_quality': None, 'reward_score': None, 'feedback_requested': False}

        # 1c. greetings, thanks, 'what can you do': a short introduction with example
        # questions (a greeting used to get "This is not a legal question")
        small_talk = _small_talk(question)
        if small_talk:
            reply = prompts.message(small_talk, language)
            if small_talk == 'greeting':
                from estatemind.assistants.legal.views import SAMPLE_QUESTIONS
                reply += '\n' + '\n'.join(f'- {q}' for q in SAMPLE_QUESTIONS[:3])
            memory.add_turn(user_message=question, assistant_response=reply, intent='conversation', entities={})
            _save_session(session, memory, session.last_domain)
            return {'session_id': session.session_id, 'turn_index': memory.turn_count - 1, 'response_log_id': None,
                    'outcome': O.OUTCOME_CONVERSATION, 'answer': reply, 'language': language,
                    'domain': 'conversation', 'in_scope': True, 'citations': [], 'sentences': [],
                    'grounding_score': None, 'grounding_label': None, 'quality_label': None,
                    'overall_quality': None, 'reward_score': None, 'feedback_requested': False}

        # 2. classify the question itself; if it is a follow-up the classifier is unsure
        # about ("et pour un terrain ?": zoning at 0.37), judge it with the previous
        # question instead (transactions at 0.79). Always using the context misrouted
        # clear follow-ups ("et si l'acheteur est étranger ?": foreign ownership -> leasing).
        query = _retrieval_query(question, memory)
        cls = self.classifier.classify(question)
        if query != question and (not cls['in_scope'] or cls['confidence'] < FOLLOW_UP_MIN_CONFIDENCE):
            cls = self.classifier.classify(query)
        domain = cls['primary_domain']
        log.update(domain=domain, domain_confidence=cls['confidence'], in_scope=cls['in_scope'])

        if not cls['in_scope']:
            outcome, answer_text = O.OUTCOME_OUT_OF_SCOPE, prompts.message('out_of_scope', language)
        else:
            # 3. retrieve
            retrieval = self.retriever.retrieve(query, domain)
            citations = _citations(retrieval.context_passages if retrieval.sufficient else [])
            log.update(
                collection_used=retrieval.collection, embedding_model=retrieval.embedding_model,
                retrieval_top_similarity=retrieval.top_similarity,
                retrieval_sources=[{'source_id': p.source_id, 'label': p.label, 'similarity': p.similarity}
                                   for p in retrieval.passages],
            )
            if not retrieval.sufficient:
                outcome, answer_text = O.OUTCOME_NO_SOURCES, prompts.message('no_sources', language)
            else:
                outcome, answer_text, grounding = self._generate_grounded(
                    question, retrieval.context_passages, language, memory, log)
                if outcome in (O.OUTCOME_ANSWERED, O.OUTCOME_ANSWERED_FLAGGED, O.OUTCOME_ANSWERED_EXTRACTIVE):
                    quality = self.quality.evaluate(question, answer_text, grounding,
                                                    len(retrieval.context_passages))

        reward = self.reward.predict_quality(question, answer_text) if quality else None
        memory.add_turn(user_message=question, assistant_response=answer_text, intent=domain, entities={})
        _save_session(session, memory, domain)

        entry = LegalResponseLog.objects.create(
            session=session, turn_index=memory.turn_count - 1, question=question, answer=answer_text,
            outcome=outcome,
            relevance_score=quality.get('relevance'), groundedness_score=quality.get('groundedness'),
            citation_score=quality.get('citation_score'), length_appropriate=quality.get('length_appropriate'),
            overall_quality_score=quality.get('overall'), quality_label=quality.get('quality_label'),
            is_grounded=(grounding.get('decision') not in (FAIL, FLAG)) if grounding else None,
            ungrounded_sentences=grounding.get('ungrounded_sentences', []),
            reward_score=reward, latency_ms=int((time.monotonic() - started) * 1000),
            **log,
        )
        return {
            'session_id': session.session_id,
            'turn_index': entry.turn_index,
            'response_log_id': entry.id,
            'outcome': outcome,
            'answer': answer_text,
            'language': language,
            'domain': domain,
            'in_scope': cls['in_scope'],
            'citations': citations,
            'sentences': grounding.get('sentences', []),
            'grounding_score': grounding.get('grounded_ratio'),
            'grounding_label': self._grounding_label(grounding),
            'quality_label': quality.get('quality_label'),
            'overall_quality': quality.get('overall'),
            'reward_score': reward,
            'feedback_requested': True,
        }

    def _generate_grounded(self, question, passages, language, memory, log):
        """Generate, check, regenerate once if unsupported, else refuse."""
        texts = [p.text for p in passages]
        grounding = {}
        for strict in (False, True):
            log['generation_attempts'] += 1
            messages = prompts.build_messages(question, passages, language, memory.recent_turns, strict=strict)
            try:
                answer = llm_service.chat(messages)
                log['llm_model'] = llm_service.model_name()
            except llm_service.LLMUnavailable as exc:
                logger.warning('Legal LLM unavailable, quoting the sources instead: %s', exc)
                return self._extractive(question, passages, language, log)
            grounding = self.detector.check_answer(answer, texts)
            if not answer.strip():  # declined / empty output: nothing to show
                grounding = {**grounding, 'decision': FAIL, 'grounded_ratio': 0.0}
            if grounding['decision'] != FAIL:
                if grounding['decision'] == FLAG:
                    shown = {r['sentence']: r['display_text'] for r in grounding['sentences']}
                    answer = ' '.join(shown.get(s, s) for s in self.detector._split_sentences(answer))
                    return O.OUTCOME_ANSWERED_FLAGGED, answer, grounding
                return O.OUTCOME_ANSWERED, answer, grounding
            logger.info('Legal answer failed grounding (ratio %.2f), attempt %d',
                        grounding['grounded_ratio'], log['generation_attempts'])
        return O.OUTCOME_UNGROUNDED, prompts.message('ungrounded', language), grounding

    def _extractive(self, question, passages, language, log):
        """Quote the most relevant sentences of the retrieved texts (no LLM needed)."""
        from . import embedding_service, extractive

        selected = extractive.select(question, passages, embedding_service.embed_texts)
        if not selected:
            return O.OUTCOME_NO_SOURCES, prompts.message('no_sources', language), {}
        answer = extractive.compose(selected, language)
        log['llm_model'] = 'extractive'
        grounding = self.detector.check_answer(' '.join(s for _, s, _ in selected), [p.text for p in passages])
        return O.OUTCOME_ANSWERED_EXTRACTIVE, answer, grounding

    @staticmethod
    def _grounding_label(grounding: dict) -> str | None:
        if not grounding:
            return None
        ratio = grounding.get('grounded_ratio', 0.0)
        return 'HIGH' if ratio >= 0.85 else 'MEDIUM' if ratio >= 0.65 else 'LOW'


def get_assistant() -> LegalAssistant:
    from estatemind.assistants.legal import apps
    return LegalAssistant(apps.get_domain_classifier(), apps.get_retriever(), apps.get_hallucination_detector(),
                          apps.get_quality_monitor(), apps.get_reward_model())


def get_status() -> dict:
    from django.conf import settings

    from . import chromadb_service
    from .chroma_router import ChromaRouter

    route = ChromaRouter().route('transactions')
    docs = chromadb_service.get_document_count(route.collection)
    llm_endpoints = llm_service.endpoint_status()
    llm_ok = any(e['available'] for e in llm_endpoints)
    return {
        'llm_endpoints': llm_endpoints,
        'documents_indexed': docs,
        'collection': route.collection,
        'collection_source': route.source,
        'embedding_model': route.embedding_model,
        'llm_available': llm_ok,
        'model': llm_service.model_name(),
        'retrieval_ready': docs > 0,
        # without an LLM the assistant still answers, by quoting the sources
        'ready': docs > 0,
        'answer_mode': 'written' if llm_ok else 'quoted',
        'llm_endpoint': getattr(settings, 'LEGAL_RAG', {}).get('LLM_API_URL', ''),
    }
