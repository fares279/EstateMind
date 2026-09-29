from io import StringIO
from unittest.mock import patch

import stripe
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from estatemind.market.core.management.commands import check_integrations as ci

GOOD = {'STRIPE_PUBLIC_KEY': 'pk_test_' + 'a' * 20, 'STRIPE_SECRET_KEY': 'sk_test_' + 'b' * 20,
        'STRIPE_WEBHOOK_SECRET': 'whsec_' + 'c' * 20}


def _run(*only):
    out = StringIO()
    try:
        call_command('check_integrations', '--only', *only, stdout=out)
        code = 0
    except SystemExit as exc:
        code = exc.code
    return out.getvalue(), code


class StripeCheckTests(SimpleTestCase):
    @override_settings(**GOOD)
    def test_working_keys_pass_and_are_never_printed(self):
        with patch.object(stripe.Balance, 'retrieve') as retrieve:
            text, code = _run('stripe')
        retrieve.assert_called_once()
        self.assertEqual(code, 0)
        self.assertIn('secret key accepted', text)
        for value in GOOD.values():
            self.assertNotIn(value, text)

    @override_settings(**GOOD)
    def test_revoked_secret_key_fails(self):
        with patch.object(stripe.Balance, 'retrieve', side_effect=stripe.error.AuthenticationError('no')):
            text, code = _run('stripe')
        self.assertEqual(code, 1)
        self.assertIn('rejected', text)

    @override_settings(**{**GOOD, 'STRIPE_PUBLIC_KEY': 'pk_live_' + 'a' * 20})
    def test_mixed_test_and_live_keys_fail(self):
        with patch.object(stripe.Balance, 'retrieve'):
            text, code = _run('stripe')
        self.assertEqual(code, 1)
        self.assertIn('public key is live but secret key is test', text)

    @override_settings(STRIPE_PUBLIC_KEY='', STRIPE_SECRET_KEY='', STRIPE_WEBHOOK_SECRET='')
    def test_no_keys_is_skipped(self):
        text, code = _run('stripe')
        self.assertEqual(code, 0)
        self.assertIn('SKIP', text)


class EmailCheckTests(SimpleTestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.example.com',
                       EMAIL_PORT=587, EMAIL_USE_TLS=True, EMAIL_HOST_USER='u@example.com',
                       EMAIL_HOST_PASSWORD='app-password-value')
    def test_login_without_sending(self):
        with patch.object(ci.smtplib, 'SMTP') as smtp:
            text, code = _run('email')
        server = smtp.return_value.__enter__.return_value
        server.login.assert_called_once_with('u@example.com', 'app-password-value')
        server.sendmail.assert_not_called()
        server.send_message.assert_not_called()
        self.assertEqual(code, 0)
        self.assertNotIn('app-password-value', text)


class SigningCheckTests(SimpleTestCase):
    @override_settings(SECRET_KEY=ci.PLACEHOLDER_SECRET)
    def test_placeholder_secret_fails(self):
        text, code = _run('signing')
        self.assertEqual(code, 1)
        self.assertIn('placeholder', text)
