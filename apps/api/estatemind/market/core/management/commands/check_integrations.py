"""Check that the configured keys work, e.g. right after rotating them.

    python manage.py check_integrations [--only stripe llm email signing]

Each check prints OK, FAIL or SKIP with a plain reason. Key values are never
printed. What each check does:

  signing  SECRET_KEY / SIMPLE_JWT_SIGNING_KEY are set, not the placeholder,
           and long enough. Local only.
  stripe   The three Stripe keys have the expected prefixes and are all test
           or all live; then one read-only call (Balance.retrieve) with the
           secret key.
  llm      Each legal LLM endpoint answers its model list with the key.
  email    Logs in to the SMTP server and logs out. Nothing is sent.

Exit status 1 if any check fails.
"""
from __future__ import annotations

import smtplib

from django.conf import settings
from django.core.management.base import BaseCommand

PLACEHOLDER_SECRET = 'django-insecure-changeme-in-production'
CHECKS = ('signing', 'stripe', 'llm', 'email')


def check_signing() -> list[tuple[str, str, str]]:
    out = []
    secret = settings.SECRET_KEY or ''
    if not secret or secret == PLACEHOLDER_SECRET:
        out.append(('FAIL', 'SECRET_KEY', 'not set (placeholder in use)'))
    elif len(secret) < 50:
        out.append(('FAIL', 'SECRET_KEY', f'too short ({len(secret)} characters, use 50 or more)'))
    else:
        out.append(('OK', 'SECRET_KEY', 'set'))
    # settings falls back to SECRET_KEY (or its hash) when this is unset, so read the variable itself
    from decouple import config
    jwt_key = config('SIMPLE_JWT_SIGNING_KEY', default='').strip()
    if not jwt_key or jwt_key == secret:
        out.append(('FAIL', 'SIMPLE_JWT_SIGNING_KEY', 'not set, or the same as SECRET_KEY'))
    else:
        out.append(('OK', 'SIMPLE_JWT_SIGNING_KEY', 'set'))
    return out


def _mode(key: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        for mode in ('test', 'live'):
            if key.startswith(f'{prefix}_{mode}_'):
                return mode
    return None


def check_stripe() -> list[tuple[str, str, str]]:
    public, secret, webhook = settings.STRIPE_PUBLIC_KEY, settings.STRIPE_SECRET_KEY, settings.STRIPE_WEBHOOK_SECRET
    if not (public or secret or webhook):
        return [('SKIP', 'Stripe', 'no Stripe keys configured (billing disabled)')]
    out = []
    pub_mode, sec_mode = _mode(public, ('pk',)), _mode(secret, ('sk', 'rk'))
    out.append(('OK' if pub_mode else 'FAIL', 'STRIPE_PUBLIC_KEY',
                f'{pub_mode} key' if pub_mode else 'expected a pk_test_ or pk_live_ key'))
    out.append(('OK' if sec_mode else 'FAIL', 'STRIPE_SECRET_KEY',
                f'{sec_mode} key' if sec_mode else 'expected an sk_ or rk_ test/live key'))
    out.append(('OK' if webhook.startswith('whsec_') else 'FAIL', 'STRIPE_WEBHOOK_SECRET',
                'set' if webhook.startswith('whsec_') else 'expected a whsec_ signing secret'))
    if pub_mode and sec_mode and pub_mode != sec_mode:
        out.append(('FAIL', 'Stripe', f'public key is {pub_mode} but secret key is {sec_mode}'))
    if sec_mode:
        import stripe
        try:
            stripe.Balance.retrieve(api_key=secret)
            out.append(('OK', 'Stripe API', 'secret key accepted'))
        except stripe.error.AuthenticationError:
            out.append(('FAIL', 'Stripe API', 'secret key rejected (revoked or mistyped)'))
        except Exception as exc:  # network and other errors: say what kind, not the details
            out.append(('FAIL', 'Stripe API', f'could not reach Stripe ({type(exc).__name__})'))
    return out


def check_llm() -> list[tuple[str, str, str]]:
    from estatemind.assistants.legal.services import llm_service

    endpoints = llm_service.endpoints()
    if not endpoints:
        return [('SKIP', 'Legal LLM', 'no endpoint configured')]
    out = []
    for status in llm_service.endpoint_status(force=True):
        name = f"Legal LLM ({status['name']})"
        out.append(('OK', name, 'endpoint answered') if status['available']
                   else ('FAIL', name, 'no answer: key rejected, or endpoint unreachable from this network'))
    return out


def check_email() -> list[tuple[str, str, str]]:
    if 'smtp' not in settings.EMAIL_BACKEND:
        return [('SKIP', 'Email', f'EMAIL_BACKEND is not SMTP ({settings.EMAIL_BACKEND.rsplit(".", 1)[-1]})')]
    if not (settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD):
        return [('FAIL', 'Email', 'EMAIL_HOST_USER or EMAIL_HOST_PASSWORD is empty')]
    try:
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10) as server:
            if settings.EMAIL_USE_TLS:
                server.starttls()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        return [('OK', 'Email', f'logged in to {settings.EMAIL_HOST}; nothing sent')]
    except smtplib.SMTPAuthenticationError:
        return [('FAIL', 'Email', 'login rejected (app password revoked or mistyped)')]
    except Exception as exc:
        return [('FAIL', 'Email', f'could not reach {settings.EMAIL_HOST} ({type(exc).__name__})')]


RUNNERS = {'signing': check_signing, 'stripe': check_stripe, 'llm': check_llm, 'email': check_email}


class Command(BaseCommand):
    help = 'Check that the configured keys work (after rotating them). Never prints key values.'

    def add_arguments(self, parser):
        parser.add_argument('--only', nargs='+', choices=CHECKS, default=list(CHECKS))

    def handle(self, *args, **options):
        failed = False
        for name in options['only']:
            for status, what, detail in RUNNERS[name]():
                failed |= status == 'FAIL'
                style = {'OK': self.style.SUCCESS, 'FAIL': self.style.ERROR}.get(status, self.style.WARNING)
                self.stdout.write(f"{style(f'{status:4}')}  {what}: {detail}")
        if failed:
            raise SystemExit(1)
