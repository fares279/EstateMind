"""API views for user authentication"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from core.models import Property, PriceTrend
from campaign.models import Participant

from .serializers import (
    UserSerializer, RegisterSerializer, ChangePasswordSerializer,
    EmailVerificationSerializer, ResendVerificationEmailSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer,
    UserPreferencesSerializer, OTPVerificationSerializer, UserActivitySerializer,
    SavedPropertySerializer, UserValuationSerializer, PortfolioSerializer
)
from .emails import send_verification_email, send_password_reset_email, send_welcome_email
from .permissions import RequiresPro, RequiresInvestor
from .models import UserActivity, SavedProperty, UserValuation, Portfolio

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer that includes user data"""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['full_name'] = user.full_name
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom login endpoint that uses email instead of username"""
    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    User management endpoints
    """
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def register(self, request):
        """
        Register a new user
        """
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # OTP is generated in serializer.save()
            
            return Response(
                {
                    'message': 'User registered successfully. Please enter the OTP sent to your email.',
                    'user': UserSerializer(user).data,
                    'otp_required': True,
                    'email': user.email
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def verify_otp(self, request):
        """
        Verify OTP during registration
        """
        serializer = OTPVerificationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    'message': 'Email verified successfully!',
                    'user': UserSerializer(user).data
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def resend_otp(self, request):
        """
        Resend OTP to email
        """
        email = request.data.get('email')
        if not email:
            return Response({'email': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            if user.is_email_verified:
                return Response({'message': 'Email is already verified'}, status=status.HTTP_200_OK)
            
            otp = user.generate_otp()
            # Send OTP via email
            try:
                send_verification_email(user, otp)
            except Exception as e:
                print(f"Email send error: {e}")
            
            return Response(
                {'message': 'OTP sent to your email. Please check your inbox.'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response({'email': 'No account found with this email.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def verify_email(self, request):
        """
        Verify email using token
        """
        serializer = EmailVerificationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Send welcome email
            try:
                send_welcome_email(user)
            except Exception as e:
                print(f"Email send error: {e}")
            
            return Response(
                {
                    'message': 'Email verified successfully!',
                    'user': UserSerializer(user).data
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def resend_verification_email(self, request):
        """
        Resend verification email
        """
        serializer = ResendVerificationEmailSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data.get('email')
            try:
                user = User.objects.get(email=user)
                user.generate_email_verification_token()
                send_verification_email(user, user.email_verification_token)
            except Exception as e:
                print(f"Error: {e}")
            
            return Response(
                {'message': 'Verification email sent. Please check your inbox.'},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def forgot_password(self, request):
        """
        Request password reset
        """
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(email=serializer.validated_data['email'])
                user.generate_password_reset_token()
                send_password_reset_email(user, user.password_reset_token)
            except User.DoesNotExist:
                pass  # Don't reveal if email exists
            except Exception as e:
                print(f"Email send error: {e}")
            
            return Response(
                {'message': 'If this email exists, you will receive a password reset link.'},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def reset_password(self, request):
        """
        Reset password using token
        """
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {'message': 'Password reset successfully! You can now login.'},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """
        Get current authenticated user
        """
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['PUT', 'PATCH'], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        """
        Update current user profile
        """
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'message': 'Profile updated successfully',
                    'user': serializer.data
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        """
        Change current user password
        """
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'Password changed successfully'},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['GET', 'PUT', 'PATCH'], permission_classes=[IsAuthenticated])
    def preferences(self, request):
        """
        Get or update user preferences
        """
        user = request.user
        
        if request.method == 'GET':
            serializer = UserPreferencesSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        # PUT or PATCH
        serializer = UserPreferencesSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'Preferences updated successfully'},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """
        Logout user (token is handled by frontend deletion)
        """
        return Response(
            {'message': 'Logged out successfully'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated], url_path='delete-account')
    def delete_account(self, request):
        """Delete the authenticated user account after password confirmation."""
        password = request.data.get('password', '')
        if not password:
            return Response({'password': 'Password is required'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        if not user.check_password(password):
            return Response({'password': 'Incorrect password'}, status=status.HTTP_400_BAD_REQUEST)

        user.delete()
        return Response({'message': 'Account deleted successfully'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated], url_path='activity')
    def activity(self, request):
        """Track user activity for AI Activity Center."""
        serializer = UserActivitySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        activity = UserActivity.objects.create(
            user=request.user,
            activity_type=validated['activity_type'],
            feature=validated['feature'],
            metadata=validated.get('metadata', {}),
        )
        return Response(
            {
                'id': activity.id,
                'message': 'Activity recorded successfully',
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated], url_path='upgrade-plan')
    def upgrade_plan(self, request):
        """Legacy endpoint kept for compatibility. Redirects to secure billing flow."""
        target_plan = request.data.get('plan', '').lower().strip()
        if target_plan not in {'pro', 'investor'}:
            return Response({'plan': 'Target plan must be pro or investor'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'message': 'Direct upgrades are disabled. Use Stripe checkout session endpoint.',
                'target_plan': target_plan,
                'checkout_endpoint': '/api/billing/create-checkout-session/',
            },
            status=status.HTTP_409_CONFLICT,
        )

    @action(detail=False, methods=['GET', 'POST'], permission_classes=[IsAuthenticated], url_path='saved-properties')
    def saved_properties(self, request):
        """CRUD-lite endpoint for saved properties data loop."""
        if request.method == 'GET':
            items = SavedProperty.objects.filter(user=request.user)
            serializer = SavedPropertySerializer(items, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = SavedPropertySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj, _ = SavedProperty.objects.update_or_create(
            user=request.user,
            property_id=serializer.validated_data['property_id'],
            defaults={
                'title': serializer.validated_data.get('title', ''),
                'price': serializer.validated_data.get('price'),
                'location': serializer.validated_data.get('location', ''),
            },
        )
        return Response(SavedPropertySerializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated], url_path='saved-properties/remove')
    def remove_saved_property(self, request):
        property_id = request.data.get('property_id')
        if not property_id:
            return Response({'property_id': 'This field is required'}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = SavedProperty.objects.filter(user=request.user, property_id=property_id).delete()
        if not deleted:
            return Response({'message': 'Saved property not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'message': 'Saved property removed'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['GET', 'POST'], permission_classes=[IsAuthenticated], url_path='valuations-history')
    def valuations_history(self, request):
        """Store and retrieve user valuation records."""
        if request.method == 'GET':
            items = UserValuation.objects.filter(user=request.user)[:50]
            serializer = UserValuationSerializer(items, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = UserValuationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        valuation = serializer.save(user=request.user)
        UserActivity.objects.create(
            user=request.user,
            activity_type='valuation',
            feature='valuate',
            metadata={
                'property_id': valuation.property_id,
                'estimated_price': valuation.estimated_price,
            },
        )
        return Response(UserValuationSerializer(valuation).data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=['GET', 'POST'],
        permission_classes=[IsAuthenticated, RequiresInvestor],
        url_path='portfolio',
    )
    def portfolio(self, request):
        """Investor portfolio records powering ROI and yield metrics."""
        if request.method == 'GET':
            items = Portfolio.objects.filter(user=request.user)
            serializer = PortfolioSerializer(items, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = PortfolioSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        asset = serializer.save(user=request.user)
        return Response(PortfolioSerializer(asset).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated], url_path='dashboard')
    def dashboard(self, request):
        """Aggregated dashboard payload for all dashboard phases."""
        user = request.user
        prefs = user.preferences or {}

        activities = UserActivity.objects.filter(user=user)
        activity_counts = activities.values('activity_type').annotate(total=Count('id'))
        counts_map = {row['activity_type']: row['total'] for row in activity_counts}

        selected_region = prefs.get('region')
        region_properties = Property.objects.filter(is_active=True)
        if selected_region:
            region_properties = region_properties.filter(region__governorate__iexact=selected_region)

        market_avg_price = region_properties.aggregate(avg=Avg('price')).get('avg')
        latest_trends = PriceTrend.objects.order_by('-date')[:3]

        saved_properties_qs = SavedProperty.objects.filter(user=user)
        valuation_history_qs = UserValuation.objects.filter(user=user)
        portfolio_qs = Portfolio.objects.filter(user=user)

        saved_properties = SavedPropertySerializer(saved_properties_qs[:20], many=True).data
        tracked_properties = []
        valuation_history = UserValuationSerializer(valuation_history_qs[:20], many=True).data
        legal_sessions = prefs.get('legal_sessions', [])
        simulation_runs = prefs.get('simulation_runs', [])

        participant = Participant.objects.filter(email__iexact=user.email).first()
        community_role = participant.role if participant else 'learner'

        free_limit = 3
        valuations_done = valuation_history_qs.count()
        saved_count = saved_properties_qs.count()

        portfolio_aggregate = portfolio_qs.aggregate(
            total_current=Sum('current_value'),
            total_purchase=Sum('purchase_price'),
            total_rent=Sum('monthly_rent'),
        )
        total_current = float(portfolio_aggregate.get('total_current') or 0)
        total_purchase = float(portfolio_aggregate.get('total_purchase') or 0)
        total_rent = float(portfolio_aggregate.get('total_rent') or 0)
        roi_value = total_current - total_purchase
        roi_percent = (roi_value / total_purchase * 100) if total_purchase > 0 else 0
        yield_percent = (total_rent * 12 / total_purchase * 100) if total_purchase > 0 else 0

        upgrade_triggers = []

        if user.plan == 'free' and valuations_done >= free_limit:
            upgrade_triggers.append({
                'type': 'limit_reached',
                'headline': "You've reached your free valuation limit",
                'message': "You've reached your free valuation limit",
                'cta': 'Upgrade to Pro to continue',
                'target_plan': 'pro',
            })

        if user.plan == 'free' and saved_count >= 5:
            upgrade_triggers.append({
                'type': 'saved_properties_signal',
                'headline': "You're actively saving opportunities - unlock deeper valuation analytics",
                'message': 'Track ROI and opportunities on your saved properties.',
                'cta': 'Upgrade to Pro (250 TND)',
                'target_plan': 'pro',
            })

        if user.plan in {'free', 'pro'} and saved_count >= 5:
            upgrade_triggers.append({
                'type': 'investment_intent',
                'headline': 'Turn your saved properties into an investment cockpit',
                'message': 'Track ROI and opportunities on your saved properties.',
                'cta': 'Upgrade to Investor',
                'target_plan': 'investor',
            })

        if user.plan == 'pro' and saved_count >= 5:
            upgrade_triggers.append({
                'type': 'portfolio_prompt',
                'headline': "You are tracking many properties - manage returns in Investor portfolio",
                'message': 'You are using advanced analytics - unlock portfolio tools.',
                'cta': 'Upgrade to Investor (500 TND)',
                'target_plan': 'investor',
            })

        if user.plan == 'pro' and valuations_done >= 10:
            upgrade_triggers.append({
                'type': 'power_user',
                'headline': 'Power user detected from valuation activity',
                'message': 'You are using advanced analytics - unlock portfolio tools.',
                'cta': 'Upgrade to Investor',
                'target_plan': 'investor',
            })

        cta_clicks = counts_map.get('cta_click', 0)

        personalization = {
            'plan': user.plan,
            'region': selected_region or 'Tunisia',
            'behavior_profile': (
                'investor_focused'
                if counts_map.get('analysis', 0) + counts_map.get('valuation', 0) > 12
                else 'explorer'
            ),
            'suggested_actions': [
                'Prices trending up in your watched areas - consider acting early.'
                if latest_trends.exists() else 'Add a preferred region to unlock localized insights.',
                'Track more listings to improve recommendation quality.',
            ],
        }

        response = {
            'overview': {
                'full_name': user.full_name or user.email,
                'email': user.email,
                'plan': user.plan,
                'is_email_verified': user.is_email_verified,
                'is_plan_active': user.is_plan_active,
            },
            'insights': {
                'region': selected_region or 'Tunisia',
                'avg_price': market_avg_price,
                'trend_snapshots': [
                    {
                        'property_type': t.property_type,
                        'trend_direction': t.trend_direction,
                        'forecast_3m': t.forecast_3m,
                    }
                    for t in latest_trends
                ],
            },
            'saved_tracked': {
                'saved_properties': saved_properties,
                'tracked_properties': tracked_properties,
                'valuation_history': valuation_history,
                'saved_count': saved_count,
                'valuations_count': valuations_done,
            },
            'ai_activity': {
                'valuations': valuations_done,
                'analyses': counts_map.get('analysis', 0),
                'simulations': counts_map.get('simulation', 0),
                'legal_sessions': counts_map.get('legal', 0),
                'cta_clicks': cta_clicks,
            },
            'investor_panel': {
                'enabled': user.plan == 'investor',
                'portfolio_count': portfolio_qs.count(),
                'portfolio_value': total_current,
                'roi_value': roi_value,
                'roi_percent': round(roi_percent, 2),
                'yield_percent': round(yield_percent, 2),
                'risk_level': prefs.get('portfolio_risk_level', 'medium'),
            },
            'legal_center': {
                'saved_sessions': legal_sessions,
                'ongoing_processes': prefs.get('legal_processes', []),
                'document_checklist': prefs.get('document_checklist', []),
            },
            'simulation_center': {
                'saved_scenarios': simulation_runs,
            },
            'community': {
                'role': community_role,
                'contributions': prefs.get('community_contributions', 0),
                'activities': prefs.get('community_activities', 0),
            },
            'upgrade_triggers': upgrade_triggers,
            'feature_nudges': {
                'valuate': {
                    'show_limit_warning': user.plan == 'free' and valuations_done >= free_limit,
                    'valuation_count': valuations_done,
                },
                'invest': {
                    'saved_properties_count': saved_count,
                    'has_investment_intent': saved_count >= 3,
                },
                'simulate': {
                    'simulation_count': counts_map.get('simulation', 0),
                },
                'legal': {
                    'legal_interactions': counts_map.get('legal', 0),
                },
            },
            'conversion_metrics': {
                'cta_clicks': cta_clicks,
                'valuations_count': valuations_done,
                'saved_properties_count': saved_count,
                'portfolio_assets_count': portfolio_qs.count(),
            },
            'personalization': personalization,
        }
        return Response(response, status=status.HTTP_200_OK)
