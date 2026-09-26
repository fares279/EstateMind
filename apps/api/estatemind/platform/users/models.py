"""Custom User model for email-based authentication"""

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
import uuid


class CustomUserManager(UserManager):
    """Custom user manager that uses email instead of username"""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with email and password"""
        if not email:
            raise ValueError('Email is required')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with email and password"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model that uses email as the primary identifier"""
    
    # User roles
    ROLE_CHOICES = [
        ('viewer', 'Viewer - Free/Demo'),
        ('investor', 'Investor - Active User'),
        ('premium', 'Premium - Power User'),
        ('pro', 'Pro - Investor'),
        ('admin', 'Admin'),
    ]
    
    username = None  # Remove username field
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    profile_image = models.URLField(blank=True, null=True)
    
    # Email verification
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=255, blank=True, null=True, unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    
    # OTP verification for registration
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    otp_attempts = models.IntegerField(default=0)
    
    # Password reset
    password_reset_token = models.CharField(max_length=255, blank=True, null=True, unique=True)
    password_reset_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Role & Access
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    
    # Plan information
    plan = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('pro', 'Pro'),
            ('premium', 'Premium'),
            ('investor', 'Investor'),
        ],
        default='free'
    )
    plan_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Preferences JSON
    preferences = models.JSONField(default=dict, blank=True)  # Stores user settings
    
    # Activity
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Empty because email is used for login

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['email_verification_token']),
            models.Index(fields=['password_reset_token']),
        ]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.full_name or self.email

    def get_short_name(self):
        return self.email.split('@')[0]
    
    def generate_email_verification_token(self):
        """Generate unique token for email verification"""
        token = str(uuid.uuid4())
        self.email_verification_token = token
        self.save()
        return token
    
    def generate_otp(self):
        """Generate a 6-digit OTP for email verification"""
        import random
        from django.utils import timezone
        
        otp = str(random.randint(100000, 999999))
        self.otp = otp
        self.otp_created_at = timezone.now()
        self.otp_attempts = 0
        self.save()
        return otp
    
    def verify_otp(self, otp_code):
        """Verify OTP and mark email as verified"""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.otp or self.otp != otp_code:
            self.otp_attempts += 1
            self.save()
            return False, "Invalid OTP"
        
        # Check if OTP expired (valid for 10 minutes)
        if self.otp_created_at:
            if timezone.now() - self.otp_created_at > timedelta(minutes=10):
                return False, "OTP expired"
        
        # Check attempt limit
        if self.otp_attempts >= 5:
            return False, "Too many failed attempts"
        
        # Mark email as verified
        self.is_email_verified = True
        self.email_verified_at = timezone.now()
        self.otp = None
        self.otp_created_at = None
        self.otp_attempts = 0
        self.save()
        
        return True, "Email verified successfully"
    
    def generate_password_reset_token(self):
        """Generate unique token for password reset"""
        from django.utils import timezone
        from datetime import timedelta
        
        token = str(uuid.uuid4())
        self.password_reset_token = token
        self.password_reset_expires_at = timezone.now() + timedelta(hours=24)
        self.save()
        return token
    
    def is_password_reset_token_valid(self):
        """Check if password reset token is still valid"""
        from django.utils import timezone
        
        if not self.password_reset_token:
            return False
        
        if not self.password_reset_expires_at:
            return False
        
        return timezone.now() < self.password_reset_expires_at
    
    @property
    def is_plan_active(self):
        """Check if user's plan is still active"""
        from django.utils import timezone
        
        if not self.plan_expires_at:
            return self.plan != 'free'  # Free plan has no expiration
        
        return timezone.now() < self.plan_expires_at


class UserActivity(models.Model):
    """Track user activity for dashboard insights and upgrade triggers."""

    ACTIVITY_TYPES = [
        ('valuation', 'Valuation'),
        ('analysis', 'Analysis'),
        ('simulation', 'Simulation'),
        ('legal', 'Legal Session'),
        ('explore', 'Explore'),
        ('save_property', 'Save Property'),
        ('cta_click', 'CTA Click'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    feature = models.CharField(max_length=50)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Activity'
        verbose_name_plural = 'User Activities'
        indexes = [
            models.Index(fields=['user', 'activity_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.activity_type}"


class SavedProperty(models.Model):
    """Saved properties used for dashboard intent and recommendation signals."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_properties')
    property_id = models.CharField(max_length=100)
    title = models.CharField(max_length=255, blank=True)
    price = models.FloatField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Saved Property'
        verbose_name_plural = 'Saved Properties'
        constraints = [
            models.UniqueConstraint(fields=['user', 'property_id'], name='unique_saved_property_per_user')
        ]
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} saved {self.property_id}"


class UserValuation(models.Model):
    """User-facing valuation history powering activity analytics and upgrade triggers."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_valuations')
    property_id = models.CharField(max_length=100, null=True, blank=True)
    estimated_price = models.FloatField()
    input_surface = models.FloatField(null=True, blank=True)
    input_location = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'input_location']),
        ]

    def __str__(self):
        return f"{self.user.email} valuation {self.estimated_price}"


class Portfolio(models.Model):
    """Investor portfolio records used to compute ROI and yield."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolio_assets')
    property_name = models.CharField(max_length=255)
    purchase_price = models.FloatField()
    current_value = models.FloatField()
    monthly_rent = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Portfolio Asset'
        verbose_name_plural = 'Portfolio Assets'
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} portfolio {self.property_name}"
