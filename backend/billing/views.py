import stripe
import logging
from decimal import Decimal
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from .models import Payment, Subscription, StripeCustomer
from .serializers import (
    PaymentSerializer, SubscriptionSerializer, CheckoutSessionSerializer,
    CheckoutSessionResponseSerializer, StripeCustomerSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class BillingViewSet(viewsets.ViewSet):
    """Billing and payment endpoints"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='create-checkout-session')
    def create_checkout_session(self, request):
        """
        Create a Stripe checkout session for subscription upgrade.
        
        Request body:
        {
            "plan": "pro" or "investor"
        }
        """
        serializer = CheckoutSessionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        plan = serializer.validated_data['plan']
        user = request.user

        # Define pricing for each plan
        prices = {
            'pro': {
                'amount': 2500,  # $25.00 USD
                'currency': 'usd',
                'description': 'Pro Plan - $25.00/month',
                'product': 'EstateMind Pro Plan'
            },
            'investor': {
                'amount': 5000,  # $50.00 USD
                'currency': 'usd',
                'description': 'Investor Plan - $50.00/month',
                'product': 'EstateMind Investor Plan'
            }
        }

        if plan not in prices:
            return Response(
                {'error': f'Invalid plan: {plan}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pricing = prices[plan]

        try:
            # Get or create Stripe customer
            stripe_customer, created = StripeCustomer.objects.get_or_create(
                user=user,
                defaults={'stripe_customer_id': f'cust_{user.id}_{timezone.now().timestamp()}'}
            )

            # If this is a new customer, create it in Stripe
            if created:
                stripe_cust = stripe.Customer.create(
                    email=user.email,
                    name=user.full_name or user.email,
                    metadata={'user_id': str(user.id), 'email': user.email}
                )
                stripe_customer.stripe_customer_id = stripe_cust.id
                stripe_customer.save()
            else:
                # Verify or update existing customer
                try:
                    stripe_cust = stripe.Customer.retrieve(stripe_customer.stripe_customer_id)
                except stripe.error.InvalidRequestError:
                    # Customer doesn't exist in Stripe, create new
                    stripe_cust = stripe.Customer.create(
                        email=user.email,
                        name=user.full_name or user.email,
                        metadata={'user_id': str(user.id), 'email': user.email}
                    )
                    stripe_customer.stripe_customer_id = stripe_cust.id
                    stripe_customer.save()

            # Create PaymentIntent for embedded payment form
            intent = stripe.PaymentIntent.create(
                customer=stripe_customer.stripe_customer_id,
                amount=pricing['amount'],
                currency=pricing['currency'],
                payment_method_types=['card'],
                metadata={
                    'user_id': str(user.id),
                    'plan': plan,
                    'email': user.email,
                    'subscription_type': 'monthly'
                },
                description=pricing['description'],
                statement_descriptor_suffix=plan.upper()
            )

            logger.info(f"Payment intent created for user {user.email}, plan {plan}, intent_id {intent.id}")

            return Response(
                {
                    'client_secret': intent.client_secret,
                    'intent_id': intent.id,
                    'amount': pricing['amount'],
                    'currency': pricing['currency'],
                    'plan': plan,
                    'email': user.email
                },
                status=status.HTTP_200_OK
            )

        except stripe.error.CardError as e:
            logger.error(f"Card error: {e.user_message}")
            return Response(
                {'error': f'Card declined: {e.user_message}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except stripe.error.RateLimitError:
            logger.error("Rate limit error with Stripe API")
            return Response(
                {'error': 'Too many requests to payment service. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid request to Stripe: {e}")
            return Response(
                {'error': f'Invalid payment request: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except stripe.error.AuthenticationError:
            logger.error("Stripe API authentication failed — check STRIPE_SECRET_KEY")
            return Response(
                {'error': 'Payment service is not configured. Please contact support.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except stripe.error.APIConnectionError:
            logger.error("Stripe API connection error")
            return Response(
                {'error': 'Payment service unavailable. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return Response(
                {'error': 'Payment processing error. Please try again later.'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            logger.error(f"Unexpected error in create_checkout_session: {e}")
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='confirm-payment')
    def confirm_payment(self, request):
        """
        Confirm payment after user completes Payment Element form.
        
        Request body:
        {
            "intent_id": "pi_xxxxx",
            "plan": "pro" or "investor"
        }
        """
        intent_id = request.data.get('intent_id')
        plan = request.data.get('plan')
        user = request.user

        if not intent_id or not plan:
            return Response(
                {'error': 'Missing intent_id or plan'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Retrieve the payment intent to verify it's succeeded
            intent = stripe.PaymentIntent.retrieve(intent_id)
            
            if intent.status != 'succeeded':
                return Response(
                    {'error': f'Payment not completed. Status: {intent.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update user subscription
            user.plan = plan
            user.plan_expires_at = timezone.now() + timedelta(days=30)
            user.save(update_fields=['plan', 'plan_expires_at'])

            # Log the payment
            Payment.objects.create(
                user=user,
                stripe_payment_intent_id=intent.id,
                amount=Decimal(intent.amount / 100),  # Convert from cents to currency amount
                currency=intent.currency.upper(),
                status='completed',
                plan=plan
            )

            logger.info(f"Payment confirmed for user {user.email}, plan {plan}, intent_id {intent_id}")

            return Response(
                {
                    'success': True,
                    'plan': plan,
                    'message': f'Successfully upgraded to {plan} plan',
                    'plan_expires_at': user.plan_expires_at.isoformat()
                },
                status=status.HTTP_200_OK
            )

        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid payment intent: {e}")
            return Response(
                {'error': f'Invalid payment intent: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error confirming payment: {e}")
            return Response(
                {'error': 'Error confirming payment. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='dev-upgrade')
    def dev_upgrade(self, request):
        """Direct plan upgrade without Stripe — only available when DEBUG=True."""
        if not settings.DEBUG:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        plan = request.data.get('plan')
        valid_plans = ['pro', 'investor', 'premium']
        if plan not in valid_plans:
            return Response(
                {'error': f'Invalid plan. Choose from: {", ".join(valid_plans)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        user.plan = plan
        user.plan_expires_at = timezone.now() + timedelta(days=30)
        user.save(update_fields=['plan', 'plan_expires_at'])

        logger.info(f"[DEV] User {user.email} directly upgraded to {plan}")
        return Response(
            {'success': True, 'plan': plan, 'message': f'[Dev mode] Plan upgraded to {plan}'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='payment-history')
    def payment_history(self, request):
        """Get user's payment history"""
        user = request.user
        payments = Payment.objects.filter(user=user).order_by('-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='subscription-status')
    def subscription_status(self, request):
        """Get current subscription status"""
        user = request.user
        
        try:
            subscription = Subscription.objects.get(user=user)
            serializer = SubscriptionSerializer(subscription)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Subscription.DoesNotExist:
            return Response(
                {'message': 'No active subscription', 'plan': user.plan},
                status=status.HTTP_200_OK
            )


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """
    Handle Stripe webhook events.
    
    CRITICAL: This endpoint must be called by Stripe with proper signature verification.
    Only process events after verifying the webhook signature.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.warning("Invalid webhook payload")
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid webhook signature")
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    # Handle events
    try:
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            handle_checkout_session_completed(session)
            
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            handle_subscription_updated(subscription)
            
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            handle_subscription_deleted(subscription)
            
        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            handle_invoice_payment_succeeded(invoice)
            
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            handle_invoice_payment_failed(invoice)

        return JsonResponse({'status': 'success'}, status=200)

    except Exception as e:
        logger.error(f"Error processing webhook event: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def handle_checkout_session_completed(session):
    """
    Process completed checkout session.
    This is where a user's plan is upgraded after successful payment.
    """
    try:
        user_id = session.get('metadata', {}).get('user_id')
        plan = session.get('metadata', {}).get('plan')
        
        if not user_id or not plan:
            logger.error(f"Missing metadata in session {session['id']}")
            return

        user = User.objects.get(id=user_id)
        
        # Get subscription from session
        subscription_id = session.get('subscription')
        
        if subscription_id:
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update user plan
            user.plan = plan
            user.plan_expires_at = timezone.now() + timedelta(days=30)
            user.save(update_fields=['plan', 'plan_expires_at', 'updated_at'])
            
            # Create/update subscription record
            period_start = timezone.datetime.fromtimestamp(
                stripe_subscription['current_period_start'], tz=timezone.utc
            )
            period_end = timezone.datetime.fromtimestamp(
                stripe_subscription['current_period_end'], tz=timezone.utc
            )
            
            Subscription.objects.update_or_create(
                user=user,
                defaults={
                    'stripe_subscription_id': subscription_id,
                    'plan': plan,
                    'status': 'active',
                    'current_period_start': period_start,
                    'current_period_end': period_end,
                }
            )
            
            logger.info(f"User {user.email} upgraded to {plan} plan (subscription: {subscription_id})")
        
        return True
        
    except User.DoesNotExist:
        logger.error(f"User not found for session {session['id']}")
        return False
    except Exception as e:
        logger.error(f"Error handling checkout completion: {e}")
        return False


def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    try:
        stripe_customer_id = subscription.get('customer')
        stripe_subscription_id = subscription.get('id')
        
        stripe_customer = StripeCustomer.objects.get(stripe_customer_id=stripe_customer_id)
        user = stripe_customer.user
        
        status_value = subscription.get('status')
        period_start = timezone.datetime.fromtimestamp(
            subscription['current_period_start'], tz=timezone.utc
        )
        period_end = timezone.datetime.fromtimestamp(
            subscription['current_period_end'], tz=timezone.utc
        )
        
        # Map Stripe status to our status
        status_map = {
            'active': 'active',
            'past_due': 'past_due',
            'unpaid': 'past_due',
            'canceled': 'canceled',
            'incomplete': 'active',
            'incomplete_expired': 'expired',
        }
        
        our_status = status_map.get(status_value, 'active')
        
        Subscription.objects.update_or_create(
            user=user,
            defaults={
                'stripe_subscription_id': stripe_subscription_id,
                'status': our_status,
                'current_period_start': period_start,
                'current_period_end': period_end,
            }
        )
        
        logger.info(f"Subscription updated for user {user.email}: {our_status}")
        
    except StripeCustomer.DoesNotExist:
        logger.warning(f"Stripe customer {stripe_customer_id} not found")
    except Exception as e:
        logger.error(f"Error handling subscription update: {e}")


def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    try:
        stripe_customer_id = subscription.get('customer')
        stripe_customer = StripeCustomer.objects.get(stripe_customer_id=stripe_customer_id)
        user = stripe_customer.user
        
        # Update subscription status
        try:
            sub = Subscription.objects.get(user=user)
            sub.status = 'canceled'
            sub.canceled_at = timezone.now()
            sub.save(update_fields=['status', 'canceled_at', 'updated_at'])
        except Subscription.DoesNotExist:
            pass
        
        # Downgrade user plan to free
        user.plan = 'free'
        user.plan_expires_at = timezone.now()
        user.save(update_fields=['plan', 'plan_expires_at', 'updated_at'])
        
        logger.info(f"Subscription canceled for user {user.email}, plan downgraded to free")
        
    except StripeCustomer.DoesNotExist:
        logger.warning(f"Stripe customer {stripe_customer_id} not found")
    except Exception as e:
        logger.error(f"Error handling subscription deletion: {e}")


def handle_invoice_payment_succeeded(invoice):
    """Handle successful invoice payment (subscription renewal)"""
    try:
        stripe_customer_id = invoice.get('customer')
        stripe_customer = StripeCustomer.objects.get(stripe_customer_id=stripe_customer_id)
        user = stripe_customer.user
        
        # Get subscription
        subscription_id = invoice.get('subscription')
        if subscription_id:
            try:
                sub = Subscription.objects.get(user=user, stripe_subscription_id=subscription_id)
                # Subscription is already active, just update the status
                if sub.status == 'past_due':
                    sub.status = 'active'
                    sub.save(update_fields=['status', 'updated_at'])
                    logger.info(f"Subscription payment succeeded for {user.email}, status changed to active")
            except Subscription.DoesNotExist:
                pass
        
    except StripeCustomer.DoesNotExist:
        logger.warning(f"Stripe customer {stripe_customer_id} not found")
    except Exception as e:
        logger.error(f"Error handling invoice payment: {e}")


def handle_invoice_payment_failed(invoice):
    """Handle failed invoice payment"""
    try:
        stripe_customer_id = invoice.get('customer')
        stripe_customer = StripeCustomer.objects.get(stripe_customer_id=stripe_customer_id)
        user = stripe_customer.user
        
        # Get subscription
        subscription_id = invoice.get('subscription')
        if subscription_id:
            try:
                sub = Subscription.objects.get(user=user, stripe_subscription_id=subscription_id)
                sub.status = 'past_due'
                sub.save(update_fields=['status', 'updated_at'])
                logger.warning(f"Invoice payment failed for {user.email}, subscription marked as past_due")
            except Subscription.DoesNotExist:
                pass
        
    except StripeCustomer.DoesNotExist:
        logger.warning(f"Stripe customer {stripe_customer_id} not found")
    except Exception as e:
        logger.error(f"Error handling failed invoice payment: {e}")
