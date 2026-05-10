"""Serializers for user authentication and profile management"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .emails import send_verification_email, send_welcome_email
from .models import SavedProperty, UserValuation, Portfolio

User = get_user_model()


class UserActivitySerializer(serializers.Serializer):
    """Serializer for activity tracking payload."""

    activity_type = serializers.ChoiceField(
        choices=['valuation', 'analysis', 'simulation', 'legal', 'explore', 'save_property', 'cta_click']
    )
    feature = serializers.CharField(max_length=50)
    metadata = serializers.JSONField(required=False)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'phone', 'profile_image',
            'is_email_verified', 'role', 'plan', 'plan_expires_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_email_verified', 'created_at', 'updated_at']


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text='Password must be at least 8 characters with uppercase, lowercase, numbers, and special characters'
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    full_name = serializers.CharField(required=True, allow_blank=False)
    
    class Meta:
        model = User
        fields = ['email', 'full_name', 'password', 'password_confirm', 'phone']
    
    def validate(self, data):
        """Validate passwords match and meet requirements"""
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password': 'Passwords do not match'})
        
        if len(data['password']) < 8:
            raise serializers.ValidationError({'password': 'Password must be at least 8 characters'})
        
        # Validate password strength
        try:
            validate_password(data['password'])
        except ValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        
        # Check email uniqueness
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({'email': 'This email is already registered'})
        
        return data
    
    def create(self, validated_data):
        """Create user and generate OTP"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        email = validated_data.pop('email')
        full_name = validated_data.pop('full_name')
        
        user = User.objects.create_user(
            email=email,
            full_name=full_name,
            password=password,
            **validated_data
        )
        
        # Generate OTP for email verification
        user.generate_otp()
        
        # Send verification email with OTP
        send_verification_email(user, user.otp)
        
        return user


class OTPVerificationSerializer(serializers.Serializer):
    """Serializer for OTP verification"""
    
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    
    def validate(self, data):
        """Validate OTP"""
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError('No account found with this email')
        
        success, message = user.verify_otp(data['otp'])
        if not success:
            raise serializers.ValidationError({'otp': message})
        
        self.user = user
        return data
    
    def save(self):
        """Return verified user and send welcome email"""
        # Send welcome email after verification
        send_welcome_email(self.user)
        return self.user


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification via token"""
    
    token = serializers.CharField()
    
    def validate(self, data):
        """Validate token"""
        try:
            user = User.objects.get(email_verification_token=data['token'])
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid verification token')
        
        user.is_email_verified = True
        user.email_verification_token = None
        user.save()
        
        self.user = user
        return data
    
    def save(self):
        """Return verified user"""
        return self.user


class ResendVerificationEmailSerializer(serializers.Serializer):
    """Serializer for resending verification email"""
    
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Validate email exists"""
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError('No account found with this email')
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change"""
    
    old_password = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    
    def validate(self, data):
        """Validate old password and new passwords match"""
        user = self.context['request'].user
        
        if not user.check_password(data['old_password']):
            raise serializers.ValidationError({'old_password': 'Incorrect password'})
        
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password': 'Passwords do not match'})
        
        if len(data['password']) < 8:
            raise serializers.ValidationError({'password': 'Password must be at least 8 characters'})
        
        try:
            validate_password(data['password'])
        except ValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        
        return data
    
    def save(self):
        """Update password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['password'])
        user.save()
        return user


class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for forgot password request"""
    
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Validate email exists (but don't reveal this info)"""
        return value


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for password reset via token"""
    
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    
    def validate(self, data):
        """Validate token and passwords"""
        try:
            user = User.objects.get(password_reset_token=data['token'])
        except User.DoesNotExist:
            raise serializers.ValidationError({'token': 'Invalid reset token'})
        
        if not user.is_password_reset_token_valid():
            raise serializers.ValidationError({'token': 'Reset token has expired'})
        
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password': 'Passwords do not match'})
        
        if len(data['password']) < 8:
            raise serializers.ValidationError({'password': 'Password must be at least 8 characters'})
        
        try:
            validate_password(data['password'])
        except ValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        
        self.user = user
        return data
    
    def save(self):
        """Reset password"""
        self.user.set_password(self.validated_data['password'])
        self.user.password_reset_token = None
        self.user.password_reset_expires_at = None
        self.user.save()
        return self.user


class UserPreferencesSerializer(serializers.ModelSerializer):
    """Serializer for user preferences"""
    
    class Meta:
        model = User
        fields = ['preferences']


class SavedPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedProperty
        fields = ['id', 'property_id', 'title', 'price', 'location', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserValuationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserValuation
        fields = [
            'id', 'property_id', 'estimated_price', 'input_surface',
            'input_location', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = [
            'id', 'property_name', 'purchase_price', 'current_value',
            'monthly_rent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
