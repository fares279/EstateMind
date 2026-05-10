from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Count
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import threading
from .models import Participant
from .serializers import ParticipantSerializer


class ParticipantViewSet(viewsets.ModelViewSet):
    queryset = Participant.objects.filter(is_active=True)
    serializer_class = ParticipantSerializer
    permission_classes = [AllowAny]
    http_method_names = ['get', 'post']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Ensure is_active defaults to True if not provided
            if 'is_active' not in request.data:
                serializer.validated_data['is_active'] = True
            participant = serializer.save()
            
            # Send welcome email without blocking registration
            threading.Thread(target=self._send_welcome_email, args=(participant,), daemon=True).start()
            
            return Response(
                {'success': True, 'message': 'Welcome to #Aaref_Bledek! Check your email for confirmation shortly.', 'data': ParticipantSerializer(participant).data},
                status=status.HTTP_201_CREATED
            )
        return Response(
            {'success': False, 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def _send_welcome_email(self, participant):
        """Send a professional welcome email to the new participant"""
        # Role descriptions and emojis
        role_descriptions = {
            'learner': 'Learn about real estate market dynamics, pricing trends, and investment strategies through our comprehensive resources and community insights.',
            'contributor': 'Share your expertise, help verify data, and contribute insights that improve our market intelligence platform for the community.',
            'volunteer': 'Conduct research, analyze market data, and help us uncover deeper insights about Tunisia\'s real estate landscape.',
            'ambassador': 'Lead community engagement, represent EstateMind in your region, and help grow the #Aaref_Bledek movement.',
        }
        
        role_emojis = {
            'learner': '📚',
            'contributor': '🤝',
            'volunteer': '🔬',
            'ambassador': '🌟',
        }
        
        context = {
            'full_name': participant.full_name.split()[0],  # First name only
            'role_display': participant.get_role_display(),
            'role_emoji': role_emojis.get(participant.role, '✨'),
            'role_description': role_descriptions.get(participant.role, 'Join our community and help shape Tunisia\'s real estate future.'),
            'platform_url': settings.FRONTEND_URL,
        }
        
        # Render email template
        html_message = render_to_string('emails/campaign_welcome.html', context)
        
        try:
            send_mail(
                subject='Welcome to #Aaref_Bledek Campaign! 🎉',
                message=f'Welcome to #Aaref_Bledek, {participant.full_name}!',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[participant.email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            # Log the error but don't fail the registration
            print(f"Error sending welcome email to {participant.email}: {str(e)}")



@api_view(['GET'])
def campaign_stats(request):
    """Campaign statistics endpoint"""
    total = Participant.objects.filter(is_active=True).count()
    roles = Participant.objects.values('role').annotate(count=Count('role'))
    role_dict = {item['role']: item['count'] for item in roles}
    return Response({
        'total_participants': total,
        'learners': role_dict.get('learner', 0),
        'contributors': role_dict.get('contributor', 0),
        'volunteers': role_dict.get('volunteer', 0),
        'ambassadors': role_dict.get('ambassador', 0),
    })
