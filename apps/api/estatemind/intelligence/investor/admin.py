"""
investor/admin.py — Investor Intelligence

Manages investor portfolio assets and listing scan results.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import PortfolioAsset, ScanResult

_TYPE_COLORS = {
    'apartment':  '#3b82f6',
    'house':      '#8b5cf6',
    'commercial': '#f97316',
    'land':       '#f59e0b',
}
_GRADE_COLORS = {
    'A': '#22c55e', 'B': '#84cc16',
    'C': '#f59e0b', 'D': '#f97316',
    'F': '#ef4444',
}
_SIGNAL_COLORS = {
    'strong_buy': '#22c55e',
    'buy':        '#84cc16',
    'hold':       '#f59e0b',
    'avoid':      '#ef4444',
}


def _pill(text, color):
    return format_html(
        '<span style="background:{0}22;color:{0};border:1px solid {0}44;'
        'padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;white-space:nowrap">'
        '{1}</span>',
        color, text,
    )


def _money(v):
    if not v and v != 0:
        return '—'
    if v >= 1_000_000:
        return f'{v / 1_000_000:.2f}M TND'
    if v >= 1_000:
        return f'{v / 1_000:.1f}K TND'
    return f'{v:,.0f} TND'


@admin.register(PortfolioAsset)
class PortfolioAssetAdmin(admin.ModelAdmin):
    list_display = (
        'user_col', 'property_name', 'type_badge',
        'location_col', 'surface_col',
        'acquisition_col', 'current_val_col', 'gain_col',
        'rented_badge', 'yield_col', 'created_at',
    )
    list_filter   = ('property_type', 'governorate', 'is_rented', ('created_at', admin.DateFieldListFilter))
    search_fields = ('user__email', 'property_name', 'governorate', 'delegation')
    ordering = ('-created_at',)
    list_per_page = 40
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Property', {
            'fields': (
                'user', 'property_name', 'property_type',
                'governorate', 'delegation',
                'surface_m2', 'room_count', 'floor_level', 'amenity_score',
            ),
        }),
        ('Financials', {
            'fields': (
                'acquisition_price_tnd', 'acquisition_date', 'current_value_tnd',
                'is_rented', 'monthly_rent_tnd', 'monthly_opex_tnd',
            ),
        }),
        ('Notes', {'fields': ('notes',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        return format_html('<span style="font-size:12px">{}</span>', obj.user.email if obj.user else '—')

    @admin.display(description='Type', ordering='property_type')
    def type_badge(self, obj):
        return _pill(obj.property_type.capitalize(), _TYPE_COLORS.get(obj.property_type, '#6b7280'))

    @admin.display(description='Location')
    def location_col(self, obj):
        return f'{obj.delegation}, {obj.governorate}' if obj.delegation else obj.governorate

    @admin.display(description='Area', ordering='surface_m2')
    def surface_col(self, obj):
        return format_html('{} m²', f'{obj.surface_m2:,.0f}') if obj.surface_m2 else '—'

    @admin.display(description='Acquisition', ordering='acquisition_price_tnd')
    def acquisition_col(self, obj):
        return _money(obj.acquisition_price_tnd)

    @admin.display(description='Current Value', ordering='current_value_tnd')
    def current_val_col(self, obj):
        v = obj.current_value_tnd or obj.acquisition_price_tnd
        return format_html('<b>{}</b>', _money(v))

    @admin.display(description='Gain/Loss')
    def gain_col(self, obj):
        ap = obj.acquisition_price_tnd or 0
        cv = obj.current_value_tnd or ap
        if not ap:
            return '—'
        pct = (cv - ap) / ap * 100
        c = '#22c55e' if pct >= 0 else '#ef4444'
        sign = '+' if pct >= 0 else ''
        return format_html('<span style="color:{};font-weight:600">{}{}%</span>', c, sign, f'{pct:.1f}')

    @admin.display(description='Rented', boolean=True, ordering='is_rented')
    def rented_badge(self, obj):
        return obj.is_rented

    @admin.display(description='Gross Yield')
    def yield_col(self, obj):
        rent = obj.monthly_rent_tnd or 0
        cv = obj.current_value_tnd or obj.acquisition_price_tnd or 0
        if not rent or not cv:
            return '—'
        y = rent * 12 / cv * 100
        c = '#22c55e' if y >= 6 else '#f59e0b' if y >= 4 else '#ef4444'
        return format_html('<span style="color:{};font-weight:600">{}%</span>', c, f'{y:.1f}')


@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display = (
        'user_col', 'location_col', 'type_badge',
        'price_col', 'surface_col', 'signal_badge',
        'underval_col', 'grade_badge', 'score_col', 'yield_col', 'created_at',
    )
    list_filter  = ('property_type', 'governorate', 'investment_grade', 'buy_signal',
                    ('created_at', admin.DateFieldListFilter))
    search_fields = ('user__email', 'governorate', 'delegation')
    ordering = ('-created_at',)
    list_per_page = 40
    date_hierarchy = 'created_at'
    readonly_fields = (
        'user', 'listing_price_tnd', 'surface_m2', 'property_type',
        'governorate', 'delegation', 'room_count',
        'undervaluation_label', 'undervaluation_proba',
        'buy_signal', 'p_buy', 'gross_yield_pct', 'opportunity_score',
        'investment_grade', 'full_result', 'created_at',
    )

    fieldsets = (
        ('Input', {
            'fields': (
                'user', 'listing_price_tnd', 'surface_m2', 'property_type',
                'governorate', 'delegation', 'room_count',
            ),
        }),
        ('AI Result', {
            'fields': (
                'investment_grade', 'buy_signal', 'p_buy',
                'undervaluation_label', 'undervaluation_proba',
                'gross_yield_pct', 'opportunity_score',
            ),
        }),
        ('Full Payload', {'fields': ('full_result',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        return format_html('<span style="font-size:12px">{}</span>', obj.user.email if obj.user else 'Anonymous')

    @admin.display(description='Location')
    def location_col(self, obj):
        return f'{obj.delegation}, {obj.governorate}' if obj.delegation else obj.governorate

    @admin.display(description='Type', ordering='property_type')
    def type_badge(self, obj):
        return _pill(obj.property_type.capitalize(), _TYPE_COLORS.get(obj.property_type, '#6b7280'))

    @admin.display(description='Price', ordering='listing_price_tnd')
    def price_col(self, obj):
        return _money(obj.listing_price_tnd)

    @admin.display(description='Area', ordering='surface_m2')
    def surface_col(self, obj):
        return format_html('{} m²', f'{obj.surface_m2:,.0f}') if obj.surface_m2 else '—'

    @admin.display(description='Signal', ordering='buy_signal')
    def signal_badge(self, obj):
        if not obj.buy_signal:
            return '—'
        c = _SIGNAL_COLORS.get(obj.buy_signal, '#6b7280')
        label = obj.buy_signal.replace('_', ' ').upper()
        return _pill(label, c)

    @admin.display(description='Undervalued', ordering='undervaluation_proba')
    def underval_col(self, obj):
        v = obj.undervaluation_proba or 0
        c = '#22c55e' if v >= 0.7 else '#f59e0b' if v >= 0.4 else '#6b7280'
        return format_html('<span style="color:{};font-weight:600">{}%</span>', c, f'{v * 100:.0f}')

    @admin.display(description='Grade', ordering='investment_grade')
    def grade_badge(self, obj):
        if not obj.investment_grade:
            return '—'
        c = _GRADE_COLORS.get(obj.investment_grade, '#6b7280')
        return _pill(obj.investment_grade, c)

    @admin.display(description='Score', ordering='opportunity_score')
    def score_col(self, obj):
        v = obj.opportunity_score or 0
        c = '#22c55e' if v >= 70 else '#f59e0b' if v >= 45 else '#ef4444'
        return format_html(
            '<div style="display:flex;align-items:center;gap:5px">'
            '<div style="width:50px;background:#1f2937;border-radius:3px;height:5px;overflow:hidden">'
            '<div style="width:{0}%;background:{1};height:100%;border-radius:3px"></div></div>'
            '<span style="font-size:11px;color:{1};font-weight:600">{2:.0f}</span>'
            '</div>',
            min(v, 100), c, v,
        )

    @admin.display(description='Yield', ordering='gross_yield_pct')
    def yield_col(self, obj):
        v = obj.gross_yield_pct or 0
        if not v:
            return '—'
        c = '#22c55e' if v >= 6 else '#f59e0b' if v >= 4 else '#ef4444'
        return format_html('<span style="color:{};font-weight:600">{}%</span>', c, f'{v:.1f}')
