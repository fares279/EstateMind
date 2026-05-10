from rest_framework import serializers
from .models import Payment, Subscription, StripeCustomer


class StripeCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StripeCustomer
        fields = ['stripe_customer_id', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'stripe_payment_intent_id', 'amount', 'currency', 'plan', 'status', 'created_at']
        read_only_fields = ['id', 'stripe_payment_intent_id', 'status', 'created_at']


class SubscriptionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'stripe_subscription_id', 'plan', 'status', 'is_active',
            'current_period_start', 'current_period_end', 'created_at'
        ]
        read_only_fields = ['stripe_subscription_id', 'status', 'created_at']

    def get_is_active(self, obj):
        return obj.is_active()


class CheckoutSessionSerializer(serializers.Serializer):
    """Request serializer for creating checkout session"""
    plan = serializers.ChoiceField(choices=['pro', 'investor'])
    
    
class CheckoutSessionResponseSerializer(serializers.Serializer):
    """Response serializer for checkout session"""
    checkout_url = serializers.URLField()
    session_id = serializers.CharField()
