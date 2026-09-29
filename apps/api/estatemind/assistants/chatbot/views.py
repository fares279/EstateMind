"""
EstateMind Chatbot API views — AI Advisor endpoints.
POST /api/chatbot/message/  — send a message, get AI response with grounding + quality monitoring
GET  /api/chatbot/session/  — get session context
POST /api/chatbot/feedback/ — record user feedback for RLHF training
"""

import json
import uuid
import logging
import re
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from estatemind.assistants.chatbot.services.conversation_memory import ConversationMemory
from estatemind.assistants.chatbot.models import ChatbotSession, ChatbotResponseLog
from estatemind.platform.throttling import ChatThrottle, FeedbackThrottle, with_defaults
from estatemind.platform.errors import error_body
from estatemind.assistants.conversation_facts import extract_user_name, is_name_question, name_response
from estatemind.assistants.chatbot.apps import (
    get_intent_classifier,
    get_market_retriever,
    get_hallucination_guard,
    get_quality_monitor,
    get_reward_model,
)

logger = logging.getLogger(__name__)

SESSION_TTL = 60 * 30  # 30 minutes


def _extract_user_name(message: str) -> str | None:
    return extract_user_name(message)


def _is_name_question(message: str) -> bool:
    return is_name_question(message)


def _detect_ranking_query(message: str) -> bool:
    """Detect ranking queries like 'top 5', 'best', 'highest', etc."""
    lower = message.lower().strip()
    ranking_keywords = [
        'top ', 'best ', 'highest', 'lowest', 'most ', 'least ', 
        'rank', 'ranking', 'compare', 'which is better',
        'top delegations', 'top properties', 'leading', 'worst'
    ]
    return any(keyword in lower for keyword in ranking_keywords)


def _data_basis_note(market: dict) -> str:
    """Say when a market figure rests on EstateMind's price benchmarks (synthetic
    sample listings) rather than real listings."""
    basis = market.get('data_basis')
    if basis == 'benchmarks':
        return "No real listings are on record there, so this figure comes from EstateMind's price benchmarks. "
    if basis == 'mixed':
        return "Part of this figure comes from EstateMind's price benchmarks where real listings are missing. "
    return ''


def _format_source_tag(source_tag: str) -> str:
    """Convert verbose source tag to concise label for display."""
    if not source_tag:
        return "EstateMind"
    
    # Map common source tags to concise labels
    tag_lower = source_tag.lower()
    
    if 'market_snapshot' in tag_lower:
        return "Market Data"
    elif 'forecast' in tag_lower:
        return "Price Forecast"
    elif 'climate' in tag_lower:
        return "Climate Analysis"
    elif 'investment' in tag_lower:
        return "Investment Grade"
    elif 'ranking' in tag_lower:
        return "Market Rankings"
    else:
        # Generic fallback: extract first part before underscore or date
        parts = source_tag.split('_')
        return parts[0].replace('-', ' ').title() if parts else "EstateMind"




def _name_response(memory: ConversationMemory) -> str:
    return name_response(memory.extracted_facts.get('user_name'))

def _get_or_create_session(session_id: str = None):
    """
    Gets or creates a ChatbotSession and loads memory from Redis.
    """
    if not session_id:
        session_id = str(uuid.uuid4())
    
    session_obj, created = ChatbotSession.objects.get_or_create(
        session_id=session_id
    )
    
    # Load memory from cache or create new
    memory_key = f'chat_memory_{session_id}'
    memory_data = cache.get(memory_key)
    
    if memory_data:
        memory = ConversationMemory.deserialize(session_id, memory_data)
    else:
        memory = ConversationMemory(session_id)
    
    return session_obj, memory


def _save_memory(session_id: str, memory: ConversationMemory):
    """
    Saves conversation memory to Redis and updates session snapshot.
    """
    memory_key = f'chat_memory_{session_id}'
    serialized = memory.serialize()
    cache.set(memory_key, serialized, SESSION_TTL)
    
    # Also update session snapshot for backup
    try:
        session = ChatbotSession.objects.get(session_id=session_id)
        session.memory_snapshot = serialized
        session.turn_count = memory.turn_count
        session.primary_location_interest = (
            memory.extracted_facts.get('primary_location_interest')
        )
        session.preferred_property_type = (
            memory.extracted_facts.get('preferred_property_type')
        )
        session.save()
    except ChatbotSession.DoesNotExist:
        pass


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes(with_defaults(ChatThrottle))
@csrf_exempt
def chat_message(request):
    """
    POST /api/chatbot/message/
    Hardened pipeline:
    1. Load or create session with rolling memory
    2. Resolve ambiguous references
    3. Classify intent with ML model
    4. Retrieve grounded market context
    5. Generate grounded response
    6. Validate groundedness (hallucination guard)
    7. Score response quality
    8. Optionally rerank with reward model
    9. Log for monitoring and RLHF training
    10. Record user feedback widget
    
    Body: { "message": str, "session_id": str (optional) }
    Returns: { "session_id", "message", "intent", "confidence", "sources", 
               "quality_label", "grounded", "turn_index" }
    """
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        mode = request.data.get('mode', 'general')  # 'general' or 'legal'
        
        if not message:
            return Response(
                {'error': 'Message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(message) > 1000:
            message = message[:1000]
        
        # Inject legal system context if mode is 'legal'
        if mode == 'legal':
            legal_context = (
                "[LEGAL MODE] You are a Tunisian real estate law specialist. "
                "Answer questions about Tunisian property law, registration procedures, taxes, and legal processes. "
                "Cite relevant Tunisian law articles when applicable. "
                "Always recommend consulting a notary for official transactions. "
                "Respond in the same language as the question (Arabic, French, or English). "
                "Current question: "
            )
            message = legal_context + message
        
        # Step 1: Load or create session
        session_obj, memory = _get_or_create_session(session_id)
        session_id = session_obj.session_id
        
        # Step 2: Resolve ambiguous references
        ambiguous_result = memory.resolve_ambiguous_reference(message)
        enriched_message = ambiguous_result.get('enriched_query', message)

        detected_name = _extract_user_name(message)
        if detected_name:
            memory.extracted_facts['user_name'] = detected_name

        if _is_name_question(message):
            response_text = _name_response(memory)
            intent = 'general_greeting'
            confidence = 1.0
            entities = {}
            retrieval_data = {}
            sources_used = []
            intent_result = {'secondary_intent': None}
        elif detected_name:
            response_text = f"Nice to meet you, {detected_name}. I'll remember that."
            intent = 'general_greeting'
            confidence = 1.0
            entities = {}
            retrieval_data = {}
            sources_used = []
            intent_result = {'secondary_intent': None}
        else:
            # Step 3: Classify intent
            intent_classifier = get_intent_classifier()
            intent_result = intent_classifier.classify(
                enriched_message,
                session_context=memory.get_context_for_response()
            )
            intent = intent_result['intent']
            confidence = intent_result['confidence']
            entities = intent_result['entities']

            logger.info(f'Intent: {intent} ({confidence:.2f}) for session {session_id}')

            # Step 4: Retrieve grounded context
            location = entities.get('location') or memory.extracted_facts.get('primary_location_interest')
            is_ranking_query = _detect_ranking_query(enriched_message)
            retriever = get_market_retriever()

            retrieval_data = {}
            sources_used = []
            # Allow retrieval for: location-specific queries OR ranking queries without location
            # climate_question was missing here, so climate answers never had data
            should_retrieve = location and intent in ['market_inquiry', 'investment_advice', 'forecast_inquiry',
                                                      'climate_question']
            should_retrieve = should_retrieve or (is_ranking_query and intent in ['market_inquiry', 'investment_advice'])
            
            if should_retrieve:
                if location:
                    # Location-specific retrieval
                    retrieval_data = retriever.get_market_context(
                        location=location,
                        location_type=entities.get('location_type', 'delegation'),
                        data_types=['market_snapshot', 'forecast', 'climate_risk', 'investment_grade'],
                        property_type=entities.get('property_type', 'apartment')
                    )
                else:
                    # Nationwide ranking retrieval (no location needed)
                    retrieval_data = retriever.get_national_rankings(
                        data_types=['market_snapshot', 'forecast', 'investment_grade'],
                        property_type=entities.get('property_type', 'apartment')
                    )
                sources_used = [
                    d.get('source_tag')
                    for d in retrieval_data.get('context', {}).values()
                    if isinstance(d, dict) and d.get('available')
                ]

            # Step 5: Generate response (using existing brain or template)
            # For now, use simplified grounded response
            response_text = _generate_grounded_response(
                intent=intent,
                entities=entities,
                retrieval_data=retrieval_data,
                memory=memory
            )
        
        # Step 6: Validate groundedness
        guard = get_hallucination_guard()
        grounding_result = guard.validate_response(
            response_text,
            retrieval_data.get('context', {})
        )
        
        if not grounding_result['is_grounded']:
            # Add disclaimer if ungrounded claims detected
            response_text += (
                f"\n\n[Note: This response contains estimated information. "
                f"Please verify with official sources for {', '.join(grounding_result['ungrounded_claims'])}]"
            )
        
        # Step 7: Score response quality
        quality_monitor = get_quality_monitor()
        quality_scores = quality_monitor.evaluate(
            query=enriched_message,
            response=response_text,
            retrieved_context=retrieval_data.get('context', {}),
            intent=intent,
            grounding_result=grounding_result
        )
        
        # Step 8: Optionally rerank with reward model
        reward_model = get_reward_model()
        reward_score = reward_model.predict_quality(enriched_message, response_text)
        
        # Step 9: Log response for monitoring and RLHF
        response_log = ChatbotResponseLog.objects.create(
            session=session_obj,
            turn_index=memory.turn_count,
            intent=intent,
            intent_confidence=confidence,
            secondary_intent=intent_result.get('secondary_intent'),
            extraction_metadata=entities,
            query=enriched_message,
            response=response_text,
            relevance_score=quality_scores['relevance'],
            groundedness_score=quality_scores['groundedness'],
            length_appropriate=quality_scores['length_appropriate'],
            has_source_attribution=quality_scores['has_source_attribution'],
            overall_quality_score=quality_scores['overall'],
            quality_label=quality_scores['quality_label'],
            ungrounded_claims=grounding_result.get('ungrounded_claims', []),
            retrieval_sources_used=sources_used,
            is_grounded=grounding_result['is_grounded']
        )
        
        # Step 10: Update memory with new turn
        memory.add_turn(
            user_message=message,
            assistant_response=response_text,
            intent=intent,
            entities=entities
        )
        _save_memory(session_id, memory)
        
        return Response({
            'session_id': session_id,
            'message': response_text,
            'intent': intent,
            'confidence': confidence,
            'entities': entities,
            'quality_label': quality_scores['quality_label'],
            'overall_quality': round(quality_scores['overall'], 2),
            'grounded': grounding_result['is_grounded'],
            'grounding_score': round(grounding_result['grounding_score'], 2),
            'sources': sources_used,
            # the index the log is stored under, so session+turn feedback finds this
            # answer (it used to be one ahead: the count after add_turn)
            'turn_index': response_log.turn_index,
            'reward_score': round(reward_score, 2),
            'response_log_id': response_log.id,
            'feedback_requested': True,  # Show feedback widget
        }, status=status.HTTP_200_OK)
        
    except Exception as exc:
        logger.exception(f'Chat error: {exc}')
        return Response({
            'error': 'Internal error processing request',
            'message': "I encountered an issue. Could you rephrase your question?",
            'session_id': request.data.get('session_id', str(uuid.uuid4())),
        }, status=status.HTTP_200_OK)


def _generate_grounded_response(intent: str, entities: dict,
                                retrieval_data: dict,
                                memory) -> str:
    """
    Generates a response grounded in retrieved data.
    Never invents statistics — all claims must be in retrieval_data.
    """
    
    context = retrieval_data.get('context', {})
    location = entities.get('location')

    if intent == 'general_greeting':
        return (
            "Hello! I'm EstateMind AI, your personal real estate advisor for Tunisia. "
            "You can ask me about prices, forecasts, investment opportunities, mortgages, or climate risk. "
            "What would you like to explore?"
        )
    
    if not location:
        return (
            "I can help with Tunisia's real estate market, but I need a location to ground the answer. "
            "Please mention a governorate or delegation such as Tunis, Sousse, Sfax, or Nabeul."
        )
    
    # Extract grounded data
    market = context.get('market', {})
    forecast = context.get('forecast', {})
    climate = context.get('climate', {})
    investment = context.get('investment', {})
    
    parts = []
    
    # Build response based on intent and available data
    if intent == 'market_inquiry':
        if market.get('available'):
            freshness = market.get('freshness_prefix', '')
            source_label = _format_source_tag(market.get('source_tag', ''))
            parts.append(
                f"{freshness}The market in {location} shows a median price of "
                f"{market['median_price_per_sqm']:.0f} TND/m² with a {market['trend_direction']} "
                f"12-month outlook ({market.get('trend_pct', 0):.1f}%). "
                f"There are {market['listing_count']} real listings on record. "
                f"{_data_basis_note(market)}"
                f"[Source: {source_label}]"
            )
        else:
            parts.append(f"I don't have current market data for {location}. {market.get('reason', '')}")
    
    elif intent == 'investment_advice':
        parts_list = []
        
        if market.get('available'):
            parts_list.append(
                f"The market in {location} is currently at "
                f"{market['median_price_per_sqm']:.0f} TND/m² with a {market['trend_direction']} trend"
            )
        
        if forecast.get('available'):
            parts_list.append(
                f"12-month forecast projects {forecast['price_change_12m_pct']:.1f}% change"
            )
        
        if investment.get('available'):
            parts_list.append(
                f"rule-based investment grade: {investment['grade']} "
                f"(opportunity score {investment['opportunity_score']:.0f}/100)"
            )
        
        if climate.get('available'):
            parts_list.append(
                f"Climate risk: {climate['risk_label']} (score {climate['composite_score']:.2f})"
            )
        
        if parts_list:
            parts.append(
                "Based on current market analysis: " + ", ".join(parts_list) + ". "
                + (_data_basis_note(market) if market.get('available') else '') +
                "Investment decision should depend on your risk tolerance and horizon."
            )
        else:
            parts.append(
                f"I don't have sufficient data for {location} to make a recommendation. "
                "Please consult with a local real estate broker."
            )
    
    elif intent == 'forecast_inquiry':
        if forecast.get('available'):
            source_label = _format_source_tag(forecast.get('source_tag', ''))
            parts.append(
                f"The 12-month forecast for {location} projects "
                f"{forecast['price_change_12m_pct']:.1f}% price change "
                f"(extrapolated from EstateMind's price benchmarks). "
                f"[Source: {source_label}]"
            )
        else:
            parts.append(f"No forecast data available for {location}.")
    
    elif intent == 'climate_question':
        if climate.get('available'):
            source_label = _format_source_tag(climate.get('source_tag', ''))
            parts.append(
                f"The climate risk in {location} is rated {climate['risk_label']} "
                f"with a composite score of {climate['composite_score']:.2f}. "
                f"Primary factors: flood ({climate['flood_risk']:.2f}), "
                f"heat ({climate['heat_stress']:.2f}), "
                f"coastal erosion ({climate['coastal_erosion']:.2f}). "
                f"[Source: {source_label}]"
            )
        else:
            parts.append(f"No climate data available for {location}.")
    
    else:
        parts.append(
            f"I can help with questions about {location}'s market, climate, or investment potential. "
            "What would you like to know?"
        )
    
    return " ".join(parts)


@api_view(['GET'])
@permission_classes([AllowAny])
def chat_session(request):
    """
    GET /api/chatbot/session/?session_id=xxx
    Returns session context and conversation metadata.
    """
    session_id = request.GET.get('session_id')
    
    if not session_id:
        return Response(
            {'error': 'session_id required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        session_obj = ChatbotSession.objects.get(session_id=session_id)
        memory_key = f'chat_memory_{session_id}'
        memory_data = cache.get(memory_key)
        
        return Response({
            'session_id': session_id,
            'turn_count': session_obj.turn_count,
            'started_at': session_obj.started_at.isoformat(),
            'last_active_at': session_obj.last_active_at.isoformat(),
            'primary_location': session_obj.primary_location_interest,
            'preferred_property_type': session_obj.preferred_property_type,
            'memory': memory_data or {}
        }, status=status.HTTP_200_OK)
        
    except ChatbotSession.DoesNotExist:
        return Response(
            {'error': 'Session not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes(with_defaults(FeedbackThrottle))
@csrf_exempt
def record_feedback(request):
    """
    POST /api/chatbot/feedback/
    Records user feedback (thumbs up/down) for RLHF training and monitoring.
    
    Supports two payload formats:
    
    Format 1 (by response ID):
    { "response_log_id": int, "feedback": "thumbs_up" or "thumbs_down", "feedback_text": str (optional) }
    
    Format 2 (by session & turn):
    { "session_id": str, "turn_index": int, "feedback": "thumbs_up" or "thumbs_down", "feedback_text": str (optional) }
    """
    try:
        feedback = request.data.get('feedback')
        feedback_text = request.data.get('feedback_text', '')
        
        # Validate feedback type
        if feedback not in ['thumbs_up', 'thumbs_down']:
            return Response(
                {'error': 'Invalid feedback. Must be "thumbs_up" or "thumbs_down"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to find response log
        response_log = None
        
        # Format 1: by response ID
        response_log_id = request.data.get('response_log_id')
        if response_log_id:
            # The session id (a random UUID only that conversation's client holds)
            # must match, or anyone could rate any answer and skew reward training.
            if not request.data.get('session_id'):
                return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                response_log = ChatbotResponseLog.objects.get(
                    id=response_log_id, session__session_id=request.data['session_id'])
            except ChatbotResponseLog.DoesNotExist:
                return Response(
                    {'error': f'Response log {response_log_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Format 2: by session & turn
        if not response_log:
            session_id = request.data.get('session_id')
            turn_index = request.data.get('turn_index')
            
            if session_id and turn_index is not None:
                try:
                    session = ChatbotSession.objects.get(session_id=session_id)
                    response_log = ChatbotResponseLog.objects.get(
                        session=session,
                        turn_index=turn_index
                    )
                except (ChatbotSession.DoesNotExist, ChatbotResponseLog.DoesNotExist):
                    return Response(
                        {'error': f'Response not found for session {session_id} turn {turn_index}'},
                        status=status.HTTP_404_NOT_FOUND
                    )
        
        if not response_log:
            return Response(
                {'error': 'Must provide either response_log_id or (session_id + turn_index)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Record feedback
        response_log.add_feedback(feedback, feedback_text)
        
        logger.info(
            f'Feedback recorded: response {response_log.id} → {feedback} '
            f'(session={response_log.session_id}, turn={response_log.turn_index}, '
            f'query="{response_log.query[:50]}...", '
            f'quality={response_log.quality_label}, '
            f'intent={response_log.intent})'
        )
        
        return Response({
            'status': 'recorded',
            'response_log_id': response_log.id,
            'feedback': feedback,
            'feedback_text': feedback_text[:100] if feedback_text else None,
            'recorded_at': response_log.feedback_at.isoformat(),
            'context': {
                'session_id': response_log.session.session_id,
                'turn_index': response_log.turn_index,
                'intent': response_log.intent,
                'quality': response_log.quality_label,
                'grounded': response_log.is_grounded
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as exc:
        logger.exception(f'Feedback recording error: {exc}')
        return Response(
            error_body(exc, where='chatbot'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

