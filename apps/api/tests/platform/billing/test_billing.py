import hashlib
import hmac
import json
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from estatemind.platform.billing import views as billing_views
from estatemind.platform.billing.models import StripeCustomer, Subscription

User = get_user_model()
SECRET = 'whsec_test_secret'
PERIOD = {'current_period_start': 1767225600, 'current_period_end': 1769904000}  # 2026-01-01 .. 2026-02-01


def _signed(event: dict) -> tuple[bytes, str]:
    payload = json.dumps(event).encode()
    ts = int(time.time())
    sig = hmac.new(SECRET.encode(), f'{ts}.'.encode() + payload, hashlib.sha256).hexdigest()
    return payload, f't={ts},v1={sig}'


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
class _WebhookCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='buyer@example.com', password='pw12345!x', full_name='Buyer')
        StripeCustomer.objects.create(user=self.user, stripe_customer_id='cus_123')

    def _post(self, event, signature=None):
        payload, header = _signed(event)
        return self.client.post('/api/billing/webhook/stripe/', data=payload, content_type='application/json',
                                HTTP_STRIPE_SIGNATURE=signature or header)

    def _event(self, type_, obj):
        return {'id': 'evt_1', 'object': 'event', 'type': type_, 'data': {'object': obj}}

    def _subscribe(self, status='active'):
        return Subscription.objects.create(user=self.user, stripe_subscription_id='sub_123', plan='pro', status=status,
                                           current_period_start='2026-01-01T00:00Z', current_period_end='2026-02-01T00:00Z')


class StripeWebhookTests(_WebhookCase):
    def test_bad_signature_is_rejected(self):
        response = self._post(self._event('checkout.session.completed', {}), signature='t=1,v1=deadbeef')
        self.assertEqual(response.status_code, 400)

    def test_checkout_completed_upgrades_plan_and_records_subscription(self):
        session = {'id': 'cs_1', 'subscription': 'sub_123', 'metadata': {'user_id': str(self.user.id), 'plan': 'pro'}}
        with mock.patch.object(billing_views.stripe.Subscription, 'retrieve',
                               return_value={'id': 'sub_123', **PERIOD}):
            response = self._post(self._event('checkout.session.completed', session))
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, 'pro')
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual((sub.status, sub.stripe_subscription_id), ('active', 'sub_123'))
        self.assertEqual(sub.current_period_end.year, 2026)

    def test_payment_failed_then_succeeded(self):
        self._subscribe()
        invoice = {'customer': 'cus_123', 'subscription': 'sub_123'}
        self._post(self._event('invoice.payment_failed', invoice))
        self.assertEqual(Subscription.objects.get(user=self.user).status, 'past_due')
        self._post(self._event('invoice.payment_succeeded', invoice))
        self.assertEqual(Subscription.objects.get(user=self.user).status, 'active')

    def test_subscription_deleted_downgrades_to_free(self):
        self._subscribe()
        self.user.plan = 'pro'
        self.user.save()
        self._post(self._event('customer.subscription.deleted', {'id': 'sub_123', 'customer': 'cus_123'}))
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, 'free')
        self.assertEqual(Subscription.objects.get(user=self.user).status, 'canceled')

    def test_subscription_updated_maps_status(self):
        self._subscribe()
        self._post(self._event('customer.subscription.updated',
                               {'id': 'sub_123', 'customer': 'cus_123', 'status': 'unpaid', **PERIOD}))
        self.assertEqual(Subscription.objects.get(user=self.user).status, 'past_due')


class BillingEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='member@example.com', password='pw12345!x', full_name='Member')

    def test_requires_authentication(self):
        self.assertEqual(self.client.get('/api/billing/subscription-status/').status_code, 401)

    def test_subscription_status_without_subscription(self):
        self.client.force_authenticate(self.user)
        response = self.client.get('/api/billing/subscription-status/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['plan'], 'free')

    @override_settings(DEBUG=False)
    def test_dev_upgrade_is_hidden_outside_debug(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post('/api/billing/dev-upgrade/', {'plan': 'pro'}).status_code, 404)

    @override_settings(DEBUG=True)
    def test_dev_upgrade_in_debug(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post('/api/billing/dev-upgrade/', {'plan': 'bogus'}).status_code, 400)
        self.assertEqual(self.client.post('/api/billing/dev-upgrade/', {'plan': 'investor'}).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, 'investor')


class CurrentStripeApiShapeTests(_WebhookCase):
    """Payload shapes from Stripe API 2025-03-31+: periods on items, invoice subscription under parent."""

    def test_subscription_updated_with_period_on_items(self):
        self._subscribe()
        self._post(self._event('customer.subscription.updated', {
            'id': 'sub_123', 'customer': 'cus_123', 'status': 'past_due', 'items': {'data': [dict(PERIOD)]}}))
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.status, 'past_due')
        self.assertEqual(sub.current_period_end.month, 2)

    def test_invoice_with_parent_subscription(self):
        self._subscribe()
        self._post(self._event('invoice.payment_failed', {
            'customer': 'cus_123', 'parent': {'subscription_details': {'subscription': 'sub_123'}}}))
        self.assertEqual(Subscription.objects.get(user=self.user).status, 'past_due')
