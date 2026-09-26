"""
forecast/admin.py — Price Forecasting

Manages delegation-level price data and 12-month AI forecasts.
Both models are populated by the generate_forecasts management command.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import DelegationForecast, DelegationPriceData

_TYPE_COLORS = {
    'apartment':  '#3b82f6',
    'house':      '#8b5cf6',
    'commercial': '#f97316',
    'land':       '#f59e0b',
}
_TREND_COLORS = {'rising': '#22c55e', 'stable': '#6b7280', 'falling': '#ef4444'}


def _pill(text, color):
    return format_html(
        '<span style="background:{0}22;color:{0};border:1px solid {0}44;'
        'padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;white-space:nowrap">'
        '{1}</span>',
        color, text,
    )


@admin.register(DelegationPriceData)
class DelegationPriceDataAdmin(admin.ModelAdmin):
    list_display  = (
        'delegation_name', 'governorate', 'type_badge',
        'price_min_col', 'price_avg_col', 'price_max_col', 'trend_badge',
    )
    list_filter   = ('governorate', 'property_type')
    search_fields = ('delegation_name', 'governorate')
    ordering      = ('governorate', 'delegation_name', 'property_type')
    list_per_page = 50

    @admin.display(description='Type', ordering='property_type')
    def type_badge(self, obj):
        return _pill(obj.property_type.capitalize(), _TYPE_COLORS.get(obj.property_type, '#6b7280'))

    @admin.display(description='Min TND/m²', ordering='price_min')
    def price_min_col(self, obj):
        return format_html('<span style="font-size:12px;color:#9ca3af">{}</span>', f'{obj.price_min:,.0f}')

    @admin.display(description='Avg TND/m²', ordering='price_avg')
    def price_avg_col(self, obj):
        v = obj.price_avg
        c = '#22c55e' if v >= 2500 else '#3b82f6' if v >= 1500 else '#f59e0b'
        return format_html('<b style="color:{}">{}</b>', c, f'{v:,.0f}')

    @admin.display(description='Max TND/m²', ordering='price_max')
    def price_max_col(self, obj):
        return format_html('<span style="font-size:12px;color:#9ca3af">{}</span>', f'{obj.price_max:,.0f}')

    @admin.display(description='Annual Trend', ordering='annual_trend_pct')
    def trend_badge(self, obj):
        v = obj.annual_trend_pct
        pct = v * 100 if abs(v) <= 1 else v
        sign = '+' if pct >= 0 else ''
        arrow = '↑' if pct > 0 else '↓' if pct < 0 else '→'
        c = '#22c55e' if pct > 0 else '#ef4444' if pct < -3 else '#f59e0b'
        return _pill(f'{arrow} {sign}{pct:.1f}%', c)


@admin.register(DelegationForecast)
class DelegationForecastAdmin(admin.ModelAdmin):
    list_display  = (
        'delegation_name', 'governorate', 'type_badge',
        'horizon_idx', 'forecast_month', 'predicted_price_col',
        'mape_col', 'model_version',
    )
    list_filter   = ('governorate', 'property_type', 'model_version')
    search_fields = ('delegation_name', 'governorate')
    ordering      = ('delegation_name', 'property_type', 'horizon_idx')
    list_per_page = 50

    @admin.display(description='Type', ordering='property_type')
    def type_badge(self, obj):
        return _pill(obj.property_type.capitalize(), _TYPE_COLORS.get(obj.property_type, '#6b7280'))

    @admin.display(description='Predicted TND/m²', ordering='predicted_price_per_m2')
    def predicted_price_col(self, obj):
        tnd = obj.predicted_price_per_m2 / 1000
        return format_html('<b>{}</b>', f'{tnd:,.0f}')

    @admin.display(description='MAPE %', ordering='model_mape_pct')
    def mape_col(self, obj):
        v = obj.model_mape_pct
        c = '#22c55e' if v <= 2 else '#f59e0b' if v <= 5 else '#ef4444'
        return _pill(f'{v:.1f}%', c)
