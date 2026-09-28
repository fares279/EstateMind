"""
Legal AI assistant endpoints.
POST /api/legal/ask/       — ask a question (grounded answer + sources + quality)
POST /api/legal/feedback/  — thumbs up/down on an answer (reward model training data)
GET  /api/legal/session/   — session context
GET  /api/legal/status/    — index, model and LLM availability
GET  /api/legal/questions/ — sample questions
"""
import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from estatemind.platform.throttling import FeedbackThrottle, LegalAskThrottle, with_defaults
from estatemind.platform.errors import error_body

from .models import LegalResponseLog, LegalSession

logger = logging.getLogger(__name__)

# Questions the current corpus can answer (see data/eval_questions.json).
SAMPLE_QUESTIONS = [
    "Which property acquisition contracts are registered at the fixed registration duty?",
    "Must an assignment of a mortgage-backed debt be recorded in the land register?",
    "When does an assignment of receivables take effect against the debtor?",
    "How long does the tax administration have to approve a VAT refund request?",
    "Quel est le délai de convocation de l'assemblée générale constitutive ?",
    "How is the net asset value of a collective investment scheme calculated?",
]


class LegalAskView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = with_defaults(LegalAskThrottle)

    def post(self, request):
        question = (request.data.get('question') or '').strip()
        if not question:
            return Response({'error': 'The "question" field is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from .services.rag_engine import get_assistant
            result = get_assistant().answer(question, session_id=request.data.get('session_id'), user=request.user)
        except Exception:
            logger.exception('Legal ask failed')
            return Response({'error': 'An internal error occurred in the legal service.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        http_status = (status.HTTP_503_SERVICE_UNAVAILABLE
                       if result['outcome'] == LegalResponseLog.OUTCOME_LLM_UNAVAILABLE else status.HTTP_200_OK)
        return Response({
            'question': question,
            'status': 'success' if http_status == status.HTTP_200_OK else 'llm_unavailable',
            'sources': result['citations'],
            'domain_detected': result['domain'],
            **result,
        }, status=http_status)


class LegalFeedbackView(APIView):
    """{ "response_log_id": int, "feedback": "thumbs_up"|"thumbs_down", "feedback_text": str? }
    or { "session_id": str, "turn_index": int, ... } — same contract as /api/chatbot/feedback/."""
    permission_classes = [AllowAny]
    throttle_classes = with_defaults(FeedbackThrottle)

    def post(self, request):
        feedback = request.data.get('feedback')
        if feedback not in ('thumbs_up', 'thumbs_down'):
            return Response({'error': 'Invalid feedback. Must be "thumbs_up" or "thumbs_down"'},
                            status=status.HTTP_400_BAD_REQUEST)

        log = None
        log_id = request.data.get('response_log_id')
        session_id = request.data.get('session_id')
        if log_id:
            # The session id (a random UUID only that conversation's client holds)
            # must match, or anyone could rate any answer and skew reward training.
            if not session_id:
                return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            log = LegalResponseLog.objects.filter(id=log_id, session__session_id=session_id).first()
        elif session_id and request.data.get('turn_index') is not None:
            log = LegalResponseLog.objects.filter(
                session__session_id=request.data['session_id'], turn_index=request.data['turn_index']).first()
        else:
            return Response({'error': 'Must provide either response_log_id or (session_id + turn_index)'},
                            status=status.HTTP_400_BAD_REQUEST)
        if log is None:
            return Response({'error': 'Response not found'}, status=status.HTTP_404_NOT_FOUND)

        text = request.data.get('feedback_text') or None
        log.add_feedback(feedback, text)
        return Response({
            'status': 'recorded',
            'response_log_id': log.id,
            'feedback': feedback,
            'recorded_at': log.feedback_at.isoformat(),
            'context': {'session_id': log.session.session_id, 'turn_index': log.turn_index,
                        'outcome': log.outcome, 'quality': log.quality_label},
        })


class LegalSessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response({'error': 'session_id required'}, status=status.HTTP_400_BAD_REQUEST)
        session = LegalSession.objects.filter(session_id=session_id).first()
        if session is None:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'session_id': session.session_id,
            'turn_count': session.turn_count,
            'started_at': session.started_at.isoformat(),
            'last_active_at': session.last_active_at.isoformat(),
            'last_domain': session.last_domain,
            'turns': list(session.responses.order_by('turn_index').values(
                'turn_index', 'question', 'answer', 'outcome', 'quality_label', 'user_feedback')),
        })


class LegalStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            from .services.rag_engine import get_status
            return Response(get_status())
        except Exception as exc:  # noqa: BLE001
            logger.exception('Legal status failed')
            return Response({'documents_indexed': 0, 'llm_available': False, 'ready': False,
                             'error': 'The legal assistant status is unavailable right now.',
                             'reference': error_body(exc, where='legal_status')['reference']})


class LegalSampleQuestionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'questions': SAMPLE_QUESTIONS})
