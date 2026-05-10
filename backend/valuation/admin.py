"""
valuation/admin.py — AI Valuation Engine

Manages user-submitted valuation requests and their AI-generated results.
Each record captures: property inputs → pipeline output → stored history.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import ValuationRequest

_TYPE_COLOR = {
    'apartment': '#3b82f6', 'house': '#8b5cf6', 'villa': '#ec4899',
    'land': '#f59e0b', 'commercial': '#f97316', 'office': '#06b6d4', 'farm': '#84cc16',
}
_MODE_COLOR = {
    'heuristic': '#6b7280', 'ml': '#3b82f6', 'hybrid': '#8b5cf6',
    'comparable_only': '#f59e0b',
}


def _pill(text, color):
    return format_html(
        '<span style="background:{0}22;color:{0};border:1px solid {0}44;'
        'padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;white-space:nowrap">'
        '{1}</span>',
        color, text,
    )


def _money(v):
    if not v:  # None or 0
        return '—'
    if v >= 1_000_000:
        return f'{v / 1_000_000:.2f}M TND'
    if v >= 1_000:
        return f'{v / 1_000:.1f}K TND'
    return f'{v:,.0f} TND'


@admin.register(ValuationRequest)
class ValuationRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user_col', 'type_badge', 'tx_badge', 'location_col',
        'size_col', 'estimated_price_col', 'confidence_badge',
        'mode_badge', 'image_count', 'created_at',
    )
    list_filter = (
        'property_type', 'transaction_type', 'prediction_mode',
        'confidence_level', 'governorate',
        ('created_at', admin.DateFieldListFilter),
    )
    search_fields = ('user__email', 'governorate', 'city')
    readonly_fields = (
        'user', 'property_type', 'transaction_type', 'governorate', 'city', 'neighborhood',
        'size_m2', 'bedrooms', 'bathrooms', 'condition',
        'has_pool', 'has_garden', 'has_parking', 'sea_view', 'elevator',
        'description', 'image_count',
        'estimated_price', 'lower_bound', 'upper_bound', 'price_per_m2',
        'confidence', 'confidence_level', 'prediction_mode', 'response_data',
        'created_at',
    )
    ordering = ('-created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'
    show_full_result_count = False

    fieldsets = (
        ('Submitted By', {
            'fields': ('user', 'created_at'),
        }),
        ('Property Input', {
            'fields': (
                'property_type', 'transaction_type', 'condition',
                'governorate', 'city', 'neighborhood',
                'size_m2', 'bedrooms', 'bathrooms',
            ),
        }),
        ('Amenities', {
            'fields': ('has_pool', 'has_garden', 'has_parking', 'sea_view', 'elevator'),
            'classes': ('collapse',),
        }),
        ('Description & Images', {
            'fields': ('description', 'image_count'),
            'classes': ('collapse',),
        }),
        ('AI Result', {
            'fields': (
                'estimated_price', 'lower_bound', 'upper_bound', 'price_per_m2',
                'confidence', 'confidence_level', 'prediction_mode',
            ),
        }),
        ('Full Response Payload', {
            'fields': ('response_data',),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        if obj.user:
            return format_html('<span style="font-size:12px">{}</span>', obj.user.email)
        return format_html('<span style="color:#6b7280;font-size:11px">Anonymous</span>')

    @admin.display(description='Type', ordering='property_type')
    def type_badge(self, obj):
        return _pill(obj.property_type.capitalize(), _TYPE_COLOR.get(obj.property_type, '#6b7280'))

    @admin.display(description='Tx', ordering='transaction_type')
    def tx_badge(self, obj):
        return _pill('Sale', '#3b82f6') if obj.transaction_type == 'sale' else _pill('Rent', '#8b5cf6')

    @admin.display(description='Location')
    def location_col(self, obj):
        parts = [p for p in [obj.governorate, obj.city] if p]
        return ', '.join(parts) if parts else '—'

    @admin.display(description='Area', ordering='size_m2')
    def size_col(self, obj):
        return format_html('{} m²', f'{obj.size_m2:,.0f}') if obj.size_m2 else '—'

    @admin.display(description='Estimated Price', ordering='estimated_price')
    def estimated_price_col(self, obj):
        return format_html(
            '<b style="color:#fff">{}</b>',
            _money(obj.estimated_price),
        )

    @admin.display(description='Confidence', ordering='confidence')
    def confidence_badge(self, obj):
        v = obj.confidence or 0
        c = '#22c55e' if v >= 80 else '#f59e0b' if v >= 65 else '#ef4444'
        return _pill(f'{v}%', c)

    @admin.display(description='Mode', ordering='prediction_mode')
    def mode_badge(self, obj):
        return _pill(obj.prediction_mode, _MODE_COLOR.get(obj.prediction_mode, '#6b7280'))
