import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)

SAMPLE_QUESTIONS = [
    "What registration duties apply to real estate transactions in Tunisia?",
    "What investment incentives are available for real estate projects in Tunisia?",
    "How is income from real estate taxed under Tunisian law?",
    "What are the legal steps to create a real estate company in Tunisia?",
    "How are mortgage debts and property liens enforced in Tunisia?",
    "What are the rules for collective real estate investment funds in Tunisia?",
    "What savings and investment instruments are regulated under Tunisian law?",
    "What are the registration fee rates for property purchase contracts?",
]


class LegalAskView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        question = (request.data.get('question') or '').strip()
        if not question:
            return Response(
                {'error': 'The "question" field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from .services.rag_service import answer_question
            answer, sources = answer_question(question)
            return Response({'question': question, 'answer': answer, 'sources': sources})

        except RuntimeError as exc:
            msg = str(exc)
            if any(k in msg.lower() for k in ('too long', 'reach', 'http error', 'timeout', 'inaccessible')):
                return Response({'error': msg}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            logger.exception("RAG runtime error")
            return Response({'error': msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ImportError as exc:
            logger.error("Missing dependency: %s", exc)
            return Response(
                {'error': (
                    f"Missing dependency: {exc}. "
                    "Install required packages: "
                    "`pip install sentence-transformers chromadb`."
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except Exception:
            logger.exception("Unexpected legal ask error")
            return Response(
                {'error': 'An internal error occurred in the legal service.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LegalStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            from .services.rag_service import get_status
            return Response(get_status())
        except ImportError as exc:
            return Response({
                'documents_indexed': 0,
                'llm_available': False,
                'model': 'Llama 3.1 70B',
                'ready': False,
                'error': f'Missing dependency: {exc}',
            })
        except Exception as exc:
            return Response({
                'documents_indexed': 0,
                'llm_available': False,
                'model': 'Llama 3.1 70B',
                'ready': False,
                'error': str(exc),
            })


class LegalSampleQuestionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'questions': SAMPLE_QUESTIONS})
