"""Email utilities for sending verification and password reset emails"""

from urllib.parse import urlparse

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings


def _normalize_frontend_url(raw_url: str | None) -> str:
    """Return a safe frontend base URL.

    The environment may contain a comma-separated list of origins (used for
    CORS) or an accidentally malformed value. Pick the first non-empty entry,
    ensure a URL scheme is present, and strip any trailing slash.
    """
    if not raw_url:
        return 'http://localhost:3000'

    # If a CSV-style value was provided, use the first one
    candidates = [p.strip() for p in str(raw_url).split(',') if p.strip()]
    if not candidates:
        return 'http://localhost:3000'

    first = candidates[0]
    parsed = urlparse(first)
    if not parsed.scheme:
        # If scheme is missing, assume http
        first = 'http://' + first

    # Remove trailing slash for consistent concatenation
    return first.rstrip('/')


# Precompute platform_url once so all emails use the same normalized value
_PLATFORM_URL = _normalize_frontend_url(getattr(settings, 'FRONTEND_URL', None))


def send_verification_email(user, otp_or_token):
    """Send email verification OTP or token to user"""

    subject = 'Verify Your EstateMind Email Address'

    verification_url = None
    if len(str(otp_or_token)) > 6:
        # The web app serves /verify-otp (apps/web/src/App.js)
        verification_url = f"{_PLATFORM_URL}/verify-otp?token={otp_or_token}"

    context = {
        'user_name': user.get_full_name(),
        'otp': otp_or_token if len(str(otp_or_token)) == 6 else None,
        'verification_url': verification_url,
        'support_email': 'support@estatemind.tn',
        'platform_url': _PLATFORM_URL,
    }

    try:
        html_message = render_to_string('emails/verify_email.html', context)
        plain_message = strip_tags(html_message)
    except Exception:
        # Fallback if template not found
        if context['otp']:
            plain_message = (
                f"Hello {user.get_full_name()},\n\n"
                f"Your OTP is: {context['otp']}\n\n"
                "This code expires in 10 minutes.\n\n"
                "Best regards,\nEstateMind Team"
            )
        else:
            plain_message = (
                f"Hello {user.get_full_name()},\n\n"
                f"Please verify your email by clicking: {context['verification_url']}\n\n"
                "Best regards,\nEstateMind Team"
            )
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
        'platform_url': _PLATFORM_URL,
        'support_email': 'support@estatemind.tn',
    }

    try:
        html_message = render_to_string('emails/welcome.html', context)
        plain_message = strip_tags(html_message)
    except Exception:
        plain_message = (
            f"Hello {user.get_full_name()},\n\n"
            "Welcome to EstateMind! Start exploring real estate opportunities now.\n\n"
            "Best regards,\nEstateMind Team"
        )
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

    # Frontend uses /reset-password (no /auth prefix)
    reset_url = f"{_PLATFORM_URL}/reset-password?token={token}"

    context = {
        'user_name': user.get_full_name(),
        'reset_url': reset_url,
        'support_email': 'support@estatemind.tn',
        'platform_url': _PLATFORM_URL,
    }

    try:
        html_message = render_to_string('emails/password_reset.html', context)
        plain_message = strip_tags(html_message)
    except Exception:
        plain_message = (
            f"Hello {user.get_full_name()},\n\n"
            f"Click here to reset your password: {reset_url}\n\n"
            "This link expires in 24 hours.\n\n"
            "Best regards,\nEstateMind Team"
        )
        html_message = plain_message

    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )
