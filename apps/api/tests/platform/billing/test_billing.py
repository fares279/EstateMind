import hashlib
import hmac
import json
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from estatemind.platform.billing import views as billing_views
from estatemind.platform.billing.models import Payment, StripeCustomer, Subscription

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
        renewed = {'id': 'sub_123', 'status': 'active', 'metadata': {'plan': 'pro'}, **PERIOD}
        with mock.patch.object(billing_views.stripe.Subscription, 'retrieve', return_value=renewed):
            self._post(self._event('invoice.payment_succeeded', invoice))
        self.assertEqual(Subscription.objects.get(user=self.user).status, 'active')
        # a paid invoice extends the plan to the end of the paid period (renewals used not to)
        self.user.refresh_from_db()
        self.assertEqual((self.user.plan, self.user.plan_expires_at.month), ('pro', 2))

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


class ConfirmPaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='payer@example.com', password='pw12345!x', full_name='Payer')
        self.client.force_authenticate(self.user)

    def _intent(self, **overrides):
        intent = {'id': 'pi_1', 'status': 'succeeded', 'amount': 2500, 'currency': 'usd',
                  'metadata': {'user_id': str(self.user.id), 'plan': 'pro'}}
        intent.update(overrides)
        return billing_views.stripe.StripeObject.construct_from(intent, 'sk_test')  # the real SDK type

    def _confirm(self, intent, plan='pro'):
        with mock.patch.object(billing_views.stripe.PaymentIntent, 'retrieve', return_value=intent):
            return self.client.post('/api/billing/confirm-payment/', {'intent_id': 'pi_1', 'plan': plan})

    def test_success_upgrades_and_records_payment(self):
        response = self._confirm(self._intent())
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, 'pro')
        payment = Payment.objects.get(stripe_payment_intent_id='pi_1')
        self.assertEqual((payment.status, str(payment.amount), payment.currency), ('succeeded', '25.00', 'USD'))

    def test_repeat_confirmation_is_idempotent(self):
        self._confirm(self._intent())
        self.user.refresh_from_db()
        first_expiry = self.user.plan_expires_at
        self.assertEqual(self._confirm(self._intent()).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan_expires_at, first_expiry)
        self.assertEqual(Payment.objects.count(), 1)

    def test_cannot_claim_a_different_plan(self):
        self.assertEqual(self._confirm(self._intent(), plan='investor').status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, 'free')

    def test_cannot_use_another_users_payment(self):
        other = self._intent(metadata={'user_id': '999999', 'plan': 'pro'})
        self.assertEqual(self._confirm(other).status_code, 403)
        self.assertFalse(Payment.objects.exists())

    def test_unfinished_payment_is_rejected(self):
        self.assertEqual(self._confirm(self._intent(status='requires_payment_method')).status_code, 400)


class PaymentIntentWebhookTests(_WebhookCase):
    def test_paid_intent_upgrades_without_confirm_payment(self):
        intent = {'id': 'pi_9', 'amount': 2500, 'currency': 'usd',
                  'metadata': {'user_id': str(self.user.id), 'plan': 'pro'}}
        self.assertEqual(self._post(self._event('payment_intent.succeeded', intent)).status_code, 200)
        self._post(self._event('payment_intent.succeeded', intent))  # Stripe retries: no double extension
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, 'pro')
        self.assertEqual(Payment.objects.filter(stripe_payment_intent_id='pi_9').count(), 1)

    def test_subscription_invoice_intent_is_left_to_invoice_events(self):
        self._post(self._event('payment_intent.succeeded', {'id': 'pi_10', 'amount': 2500, 'currency': 'usd',
                                                             'metadata': {}}))
        self.assertFalse(Payment.objects.exists())


@override_settings(STRIPE_PRICE_IDS={'pro': 'price_pro', 'investor': ''})
class SubscriptionCheckoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='sub@example.com', password='pw12345!x', full_name='Sub')
        StripeCustomer.objects.create(user=self.user, stripe_customer_id='cus_9')
        self.client.force_authenticate(self.user)

    def test_configured_price_creates_a_subscription(self):
        sub = {'id': 'sub_9', 'latest_invoice': {'confirmation_secret': {'client_secret': 'pi_x_secret_y'}}}
        with mock.patch.object(billing_views.stripe.Customer, 'retrieve', return_value={'id': 'cus_9'}), \
                mock.patch.object(billing_views.stripe.Subscription, 'create', return_value=sub) as create, \
                mock.patch.object(billing_views.stripe.PaymentIntent, 'create') as one_off:
            response = self.client.post('/api/billing/create-checkout-session/', {'plan': 'pro'})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual((body['mode'], body['client_secret'], body['subscription_id']),
                         ('subscription', 'pi_x_secret_y', 'sub_9'))
        self.assertEqual(create.call_args.kwargs['items'], [{'price': 'price_pro'}])
        one_off.assert_not_called()

    def test_confirming_the_first_invoice_activates_the_subscription(self):
        intent = billing_views.stripe.StripeObject.construct_from(
            {'id': 'pi_x', 'status': 'succeeded', 'amount': 2500, 'currency': 'usd', 'customer': 'cus_9',
             'metadata': {}}, 'sk_test')
        active = {'data': [{'id': 'sub_9', 'status': 'active', 'metadata': {'plan': 'pro'}, **PERIOD}]}
        with mock.patch.object(billing_views.stripe.PaymentIntent, 'retrieve', return_value=intent), \
                mock.patch.object(billing_views.stripe.Subscription, 'list', return_value=active):
            response = self.client.post('/api/billing/confirm-payment/', {'intent_id': 'pi_x', 'plan': 'pro'})
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, 'pro')
        self.assertEqual(Subscription.objects.get(user=self.user).stripe_subscription_id, 'sub_9')
