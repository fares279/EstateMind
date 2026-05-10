"""Email utilities for sending verification and password reset emails"""

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings


def send_verification_email(user, otp_or_token):
    """Send email verification OTP or token to user"""
    
    subject = 'Verify Your EstateMind Email Address'
    
    context = {
        'user_name': user.get_full_name(),
        'otp': otp_or_token if len(str(otp_or_token)) == 6 else None,
        'verification_url': f"{settings.FRONTEND_URL}/auth/verify-email?token={otp_or_token}" if len(str(otp_or_token)) > 6 else None,
        'support_email': 'support@estatemind.tn'
    }
    
    try:
        html_message = render_to_string('emails/verify_email.html', context)
        plain_message = strip_tags(html_message)
    except:
        # Fallback if template not found
        if context['otp']:
            plain_message = f"Hello {user.get_full_name()},\n\nYour OTP is: {context['otp']}\n\nThis code expires in 10 minutes.\n\nBest regards,\nEstateMind Team"
        else:
            plain_message = f"Hello {user.get_full_name()},\n\nPlease verify your email by clicking: {context['verification_url']}\n\nBest regards,\nEstateMind Team"
        html_message = plain_message
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_welcome_email(user):
    """Send welcome email to newly verified user"""
    
    subject = 'Welcome to EstateMind!'
    
    context = {
        'user_name': user.get_full_name(),
        'platform_url': settings.FRONTEND_URL,
        'support_email': 'support@estatemind.tn'
    }
    
    try:
        html_message = render_to_string('emails/welcome.html', context)
        plain_message = strip_tags(html_message)
    except:
        plain_message = f"Hello {user.get_full_name()},\n\nWelcome to EstateMind! Start exploring real estate opportunities now.\n\nBest regards,\nEstateMind Team"
        html_message = plain_message
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_password_reset_email(user, token):
    """Send password reset email to user"""
    
    subject = 'Reset Your EstateMind Password'
    
    reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
    
    context = {
        'user_name': user.get_full_name(),
        'reset_url': reset_url,
        'support_email': 'support@estatemind.tn'
    }
    
    try:
        html_message = render_to_string('emails/password_reset.html', context)
        plain_message = strip_tags(html_message)
    except:
        plain_message = f"Hello {user.get_full_name()},\n\nClick here to reset your password: {reset_url}\n\nThis link expires in 24 hours.\n\nBest regards,\nEstateMind Team"
        html_message = plain_message
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )
