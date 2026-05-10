"""
billing/admin.py — Billing & Payments

Manages Stripe customers, payment records, and active subscriptions.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Payment, StripeCustomer, Subscription

_STATUS_COLORS = {
    'active':    '#22c55e',
    'trialing':  '#3b82f6',
    'past_due':  '#f59e0b',
    'cancelled': '#ef4444',
    'incomplete':'#6b7280',
    'succeeded': '#22c55e',
    'pending':   '#f59e0b',
    'failed':    '#ef4444',
    'refunded':  '#8b5cf6',
}
_PLAN_COLORS = {
    'free':     '#6b7280',
    'pro':      '#3b82f6',
    'premium':  '#8b5cf6',
    'investor': '#f59e0b',
}


def _pill(text, color):
    return format_html(
        '<span style="background:{0}22;color:{0};border:1px solid {0}44;'
        'padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;white-space:nowrap">'
        '{1}</span>',
        color, text,
    )


def _money(v):
    if not v:
        return '—'
    if v >= 1_000:
        return f'{v / 1_000:.2f}K {getattr(v, "currency", "TND")}'
    return f'{v:,.2f}'


@admin.register(StripeCustomer)
class StripeCustomerAdmin(admin.ModelAdmin):
    list_display  = ('user_col', 'stripe_id_col', 'created_at')
    search_fields = ('user__email', 'stripe_customer_id')
    readonly_fields = ('user', 'stripe_customer_id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    list_per_page = 50

    fieldsets = (
        ('Customer', {'fields': ('user', 'stripe_customer_id')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        return format_html('<span style="font-size:12px">{}</span>', obj.user.email if obj.user else '—')

    @admin.display(description='Stripe Customer ID')
    def stripe_id_col(self, obj):
        cid = obj.stripe_customer_id or '—'
        return format_html('<span style="font-family:monospace;font-size:11px;color:#9ca3af">{}</span>', cid)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = (
        'user_col', 'plan_badge', 'amount_col',
        'status_badge', 'created_at',
    )
    list_filter   = ('plan', 'status', ('created_at', admin.DateFieldListFilter))
    search_fields = ('user__email', 'stripe_payment_intent_id')
    readonly_fields = (
        'user', 'plan', 'amount', 'status',
        'stripe_payment_intent_id', 'created_at', 'updated_at',
    )
    ordering = ('-created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Transaction', {'fields': ('user', 'plan', 'amount', 'status')}),
        ('Stripe Reference', {'fields': ('stripe_payment_intent_id',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        return format_html('<span style="font-size:12px">{}</span>', obj.user.email if obj.user else '—')

    @admin.display(description='Plan', ordering='plan')
    def plan_badge(self, obj):
        c = _PLAN_COLORS.get(obj.plan, '#6b7280')
        return _pill(obj.plan.capitalize(), c)

    @admin.display(description='Amount', ordering='amount')
    def amount_col(self, obj):
        v = float(obj.amount or 0)
        c = '#22c55e' if v > 0 else '#6b7280'
        return format_html('<b style="color:{}">{}</b>', c, f'{v:,.2f}')

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        c = _STATUS_COLORS.get(obj.status, '#6b7280')
        return _pill(obj.status.capitalize(), c)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = (
        'user_col', 'plan_badge', 'status_badge',
        'period_end_col', 'created_at',
    )
    list_filter   = ('plan', 'status', ('created_at', admin.DateFieldListFilter))
    search_fields = ('user__email', 'stripe_subscription_id')
    readonly_fields = (
        'user', 'plan', 'status',
        'stripe_subscription_id', 'current_period_end',
        'created_at', 'updated_at',
    )
    ordering = ('-created_at',)
    list_per_page = 50

    fieldsets = (
        ('Subscription', {'fields': ('user', 'plan', 'status', 'current_period_end')}),
        ('Stripe Reference', {'fields': ('stripe_subscription_id',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        return format_html('<span style="font-size:12px">{}</span>', obj.user.email if obj.user else '—')

    @admin.display(description='Plan', ordering='plan')
    def plan_badge(self, obj):
        c = _PLAN_COLORS.get(obj.plan, '#6b7280')
        return _pill(obj.plan.capitalize(), c)

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        c = _STATUS_COLORS.get(obj.status, '#6b7280')
        return _pill(obj.status.replace('_', ' ').capitalize(), c)

    @admin.display(description='Period End', ordering='current_period_end')
    def period_end_col(self, obj):
        if not obj.current_period_end:
            return '—'
        return format_html(
            '<span style="font-size:12px">{}</span>',
            obj.current_period_end.strftime('%Y-%m-%d'),
        )
