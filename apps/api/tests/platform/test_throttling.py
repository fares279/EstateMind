import datetime as dt
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from estatemind.assistants.legal.views import LegalAskView, LegalFeedbackView
from estatemind.platform import throttling as t
from estatemind.platform.users.models import OTPLocked
from estatemind.platform.users.views import CustomTokenObtainPairView, UserViewSet

User = get_user_model()


class ThrottleWiringTests(TestCase):
    def test_sensitive_endpoints_have_tight_scopes(self):
        expected = {'register': t.RegisterThrottle, 'verify_otp': t.OTPThrottle, 'resend_otp': t.OTPThrottle,
                    'verify_email': t.OTPThrottle, 'resend_verification_email': t.OTPThrottle,
                    'forgot_password': t.PasswordResetThrottle, 'reset_password': t.PasswordResetThrottle}
        for action, throttle in expected.items():
            self.assertIn(throttle, getattr(UserViewSet, action).kwargs['throttle_classes'], action)
        self.assertIn(t.LoginThrottle, CustomTokenObtainPairView.throttle_classes)
        self.assertIn(t.LegalAskThrottle, LegalAskView.throttle_classes)
        self.assertIn(t.FeedbackThrottle, LegalFeedbackView.throttle_classes)


class ThrottleBehaviourTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_login_is_limited_to_10_per_minute(self):
        User.objects.create_user(email='a@example.com', password='pw12345!x', full_name='A')
        codes = [self.client.post('/api/auth/token/', {'email': 'a@example.com', 'password': 'wrong'}).status_code
                 for _ in range(11)]
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(codes[10], 429)

    def test_otp_verify_is_limited_to_5_per_minute(self):
        User.objects.create_user(email='b@example.com', password='pw12345!x', full_name='B')
        codes = [self.client.post('/api/auth/verify_otp/', {'email': 'b@example.com', 'otp': '000000'}).status_code
                 for _ in range(6)]
        self.assertNotIn(429, codes[:5])
        self.assertEqual(codes[5], 429)

    def test_chat_is_limited_to_20_per_minute(self):
        codes = [self.client.post('/api/chatbot/message/', {'message': 'Hello'}, format='json').status_code
                 for _ in range(21)]
        self.assertEqual(codes[:20], [200] * 20)
        self.assertEqual(codes[20], 429)

    def test_normal_browsing_is_not_throttled(self):
        # a page load fires a burst of reads; 60 anonymous GETs stay well under 300/min
        codes = {self.client.get('/api/simulate/scenarios/').status_code for _ in range(10)}
        codes |= {self.client.get('/api/climate/summary/').status_code for _ in range(50)}
        self.assertEqual(codes, {200})


class OTPTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='otp@example.com', password='pw12345!x', full_name='O')

    def _fail(self, n):
        for _ in range(n):
            self.assertFalse(self.user.verify_otp('not-it')[0])

    def test_code_comes_from_secrets(self):
        with mock.patch('secrets.randbelow', return_value=123) as randbelow:
            self.assertEqual(self.user.generate_otp(), '100123')
        randbelow.assert_called_once_with(900_000)

    def test_resend_does_not_reset_wrong_guesses(self):
        self.user.generate_otp()
        self._fail(3)
        self.user.generate_otp()
        self.assertEqual(self.user.otp_attempts, 3)

    def test_lockout_hides_whether_the_code_was_right(self):
        code = self.user.generate_otp()
        self._fail(5)
        ok, message = self.user.verify_otp(code)
        self.assertFalse(ok)
        self.assertEqual(message, self.user.verify_otp('999999')[1])  # same answer, right or wrong
        self.assertFalse(self.user.is_email_verified)
        with self.assertRaises(OTPLocked):
            self.user.generate_otp()

    def test_new_code_after_the_lockout(self):
        self.user.generate_otp()
        self._fail(5)
        self.user.otp_created_at = timezone.now() - dt.timedelta(minutes=16)
        code = self.user.generate_otp()
        self.assertEqual(self.user.otp_attempts, 0)
        self.assertTrue(self.user.verify_otp(code)[0])

    def test_resend_endpoint_reports_lockout(self):
        self.user.generate_otp()
        self._fail(5)
        response = APIClient().post('/api/auth/resend_otp/', {'email': 'otp@example.com'})
        self.assertEqual(response.status_code, 429)
        self.assertIn('Try again in', response.json()['error'])
