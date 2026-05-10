"""
EstateMind Chatbot API views.
POST /api/chatbot/message/  — send a message, get AI response
GET  /api/chatbot/session/  — get session context
"""
import json
import uuid
import logging
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .brain import process_message

logger = logging.getLogger(__name__)

SESSION_TTL = 60 * 30  # 30 minutes


def _get_session(session_id: str) -> dict:
    key = f'chat_session_{session_id}'
    return cache.get(key) or {'history': [], 'message_count': 0}


def _save_session(session_id: str, ctx: dict):
    key = f'chat_session_{session_id}'
    cache.set(key, ctx, SESSION_TTL)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def chat_message(request):
    """
    POST /api/chatbot/message/
    Body: { "message": str, "session_id": str (optional), "language": str }
    Returns: { "session_id", "message", "suggestions", "intent", "confidence" }
    """
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id') or str(uuid.uuid4())
        language = request.data.get('language', 'en')

        if not message:
            return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)

        if len(message) > 800:
            message = message[:800]

        session_ctx = _get_session(session_id)
        session_ctx['language'] = language

        # Append user message to history
        session_ctx.setdefault('history', [])
        session_ctx['history'].append({'role': 'user', 'content': message})
        if len(session_ctx['history']) > 20:
            session_ctx['history'] = session_ctx['history'][-20:]

        session_ctx['message_count'] = session_ctx.get('message_count', 0) + 1

        # Generate response
        result = process_message(message, session_ctx)

        # Append AI response to history
        session_ctx['history'].append({'role': 'assistant', 'content': result.get('message', '')})

        # Remove internal context from result before saving
        session_ctx.update(result.pop('session_context', {}))
        _save_session(session_id, session_ctx)

        return Response({
            'session_id': session_id,
            'message': result.get('message', ''),
            'suggestions': result.get('suggestions', []),
            'intent': result.get('intent', 'general'),
            'confidence': 0.92,
            'data': result.get('data'),
        }, status=status.HTTP_200_OK)

    except Exception as exc:
        logger.exception('Chat error: %s', exc)
        return Response({
            'session_id': request.data.get('session_id', str(uuid.uuid4())),
            'message': "I encountered an issue. Could you rephrase your question?",
            'suggestions': ['Apartment prices in Tunis?', 'Best investment areas?'],
            'intent': 'error',
            'confidence': 0.0,
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def chat_session(request):
    """
    GET /api/chatbot/session/?session_id=xxx
    Returns session info.
    """
    session_id = request.GET.get('session_id', '')
    if not session_id:
        return Response({'error': 'session_id required'}, status=status.HTTP_400_BAD_REQUEST)
    ctx = _get_session(session_id)
    return Response({
        'session_id': session_id,
        'message_count': ctx.get('message_count', 0),
        'history': ctx.get('history', []),
    })
