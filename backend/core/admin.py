"""
core/admin.py — EstateMind Market Data & Intelligence

Covers the Gold-layer unified property database and all derived intelligence
models that downstream features consume.

Pipeline:
  scraper.ScrapedListing  -->  core.Property  -->  all platform features
        (Bronze / Silver)          (Gold)
"""

from django.contrib import admin
from django.db.models import Avg, Count, Q
from django.utils.html import format_html

from .models import (
    ClimateRisk,
    Delegation,
    DelegationMarketSegment,
    DelegationMarketSnapshot,
    PriceTrend,
    Property,
    Region,
    Valuation,
)

# ─── palette helpers ──────────────────────────────────────────────────────────

_RISK_COLOR  = {'low': '#22c55e', 'medium': '#f59e0b', 'high': '#ef4444'}
_TREND_COLOR = {'rising': '#22c55e', 'stable': '#6b7280', 'falling': '#ef4444'}
_TYPE_COLOR  = {
    'apartment':  '#3b82f6',
    'house':      '#8b5cf6',
    'commercial': '#f97316',
    'land':       '#f59e0b',
}


def _money(v):
    if not v:  # None or 0 — no price on record
        return '—'
    if v >= 1_000_000:
        return f'{v / 1_000_000:.2f}M TND'
    if v >= 1_000:
        return f'{v / 1_000:.1f}K TND'
    return f'{v:,.0f} TND'


def _pill(text, color):
    return format_html(
        '<span style="background:{0}22;color:{0};border:1px solid {0}44;'
        'padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;white-space:nowrap">'
        '{1}</span>',
        color, text,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GEOGRAPHY  (Regions & Delegations)
# ─────────────────────────────────────────────────────────────────────────────

class DelegationInline(admin.TabularInline):
    model = Delegation
    extra = 0
    fields = ('name', 'population', 'centroid_lat', 'centroid_lon')
    readonly_fields = ('name',)
    show_change_link = True
    ordering = ('name',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display  = ('governorate', 'active_listings', 'avg_price_m2', 'delegation_count', 'climate_badge', 'population', 'coords')
    search_fields = ('governorate',)
    readonly_fields = ('created_at',)
    ordering      = ('governorate',)
    inlines       = [DelegationInline]

    fieldsets = (
        ('Geography', {'fields': ('governorate', 'latitude', 'longitude')}),
        ('Market', {'fields': ('avg_price_per_sqm', 'population')}),
        ('Meta', {'fields': ('created_at',)}),
    )

    @admin.display(description='Active Listings', ordering='_props')
    def active_listings(self, obj):
        n = obj.property_set.filter(is_active=True).count()
        c = '#22c55e' if n > 100 else '#f59e0b' if n > 20 else '#6b7280'
        return format_html('<b style="color:{}">{}</b>', c, f'{n:,}')

    @admin.display(description='Delegations', ordering='_dels')
    def delegation_count(self, obj):
        return obj.delegations.count()

    @admin.display(description='Avg TND/m²')
    def avg_price_m2(self, obj):
        return _money(obj.avg_price_per_sqm)

    @admin.display(description='Climate')
    def climate_badge(self, obj):
        try:
            r = obj.climate_risk
            return _pill(f'Flood: {r.flood_risk}', _RISK_COLOR.get(r.flood_risk, '#6b7280'))
        except (ClimateRisk.DoesNotExist, AttributeError):
            return format_html('<span style="color:#6b7280;font-size:11px">—</span>')

    @admin.display(description='Coords')
    def coords(self, obj):
        if obj.latitude and obj.longitude:
            return format_html('<span style="font-size:11px;color:#9ca3af">{}, {}</span>', f'{obj.latitude:.3f}', f'{obj.longitude:.3f}')
        return '—'


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):
    list_display  = (
        'name', 'region', 'coastal_badge', 'population_col',
        'apt_avg_col', 'apt_trend_col',
        'house_avg_col', 'land_avg_col',
        'active_listings', 'updated_at',
    )
    list_filter   = ('region', 'is_coastal')
    search_fields = ('name', 'region__governorate')
    readonly_fields = ('created_at', 'updated_at')
    ordering      = ('region__governorate', 'name')
    list_per_page = 50

    fieldsets = (
        ('Location', {
            'fields': ('region', 'name', 'is_coastal', 'population'),
        }),
        ('Geospatial', {
            'fields': ('centroid_lat', 'centroid_lon', 'geojson_polygon'),
            'classes': ('collapse',),
        }),
        ('Apartment Benchmark (TND/m²)', {
            'fields': (
                ('apt_min_tnd', 'apt_avg_tnd', 'apt_max_tnd', 'apt_trend_pct'),
            ),
        }),
        ('House Benchmark (TND/m²)', {
            'fields': (
                ('house_min_tnd', 'house_avg_tnd', 'house_max_tnd', 'house_trend_pct'),
            ),
        }),
        ('Commercial Benchmark (TND/m²)', {
            'fields': (
                ('comm_min_tnd', 'comm_avg_tnd', 'comm_max_tnd', 'comm_trend_pct'),
            ),
        }),
        ('Land Benchmark (TND/m²)', {
            'fields': (
                ('land_min_tnd', 'land_avg_tnd', 'land_max_tnd', 'land_trend_pct'),
            ),
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Coastal', boolean=True, ordering='is_coastal')
    def coastal_badge(self, obj):
        return obj.is_coastal

    @admin.display(description='Population', ordering='population')
    def population_col(self, obj):
        if not obj.population:
            return '—'
        if obj.population >= 1_000_000:
            return format_html('<span style="font-size:12px">{}M</span>', f'{obj.population / 1_000_000:.1f}')
        if obj.population >= 1_000:
            return format_html('<span style="font-size:12px">{}K</span>', f'{obj.population / 1_000:.0f}')
        return f'{obj.population:,}'

    @admin.display(description='Apt Avg TND/m²', ordering='apt_avg_tnd')
    def apt_avg_col(self, obj):
        v = obj.apt_avg_tnd
        if not v:
            return '—'
        c = '#22c55e' if v >= 2500 else '#3b82f6' if v >= 1500 else '#f59e0b'
        return format_html('<b style="color:{}">{}</b>', c, f'{v:,.0f}')

    @admin.display(description='Apt Trend', ordering='apt_trend_pct')
    def apt_trend_col(self, obj):
        v = obj.apt_trend_pct
        if v is None:
            return '—'
        pct = v * 100
        sign = '+' if pct >= 0 else ''
        c = '#22c55e' if pct > 0 else '#ef4444' if pct < -3 else '#f59e0b'
        arrow = '↑' if pct > 0 else '↓' if pct < 0 else '→'
        return _pill(f'{arrow} {sign}{pct:.0f}%', c)

    @admin.display(description='House Avg TND/m²', ordering='house_avg_tnd')
    def house_avg_col(self, obj):
        v = obj.house_avg_tnd
        return format_html('<span style="font-size:12px">{}</span>', f'{v:,.0f}') if v else '—'

    @admin.display(description='Land Avg TND/m²', ordering='land_avg_tnd')
    def land_avg_col(self, obj):
        v = obj.land_avg_tnd
        return format_html('<span style="font-size:12px">{}</span>', f'{v:,.0f}') if v else '—'

    @admin.display(description='Active Listings', ordering='_props')
    def active_listings(self, obj):
        n = obj.region.property_set.filter(is_active=True).count() if obj.region_id else 0
        return format_html('<b>{}</b>', f'{n:,}') if n else '—'


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED PROPERTY DATABASE  (Gold Layer)
# Single source of truth for all platform features.
# Populated exclusively by the scraper pipeline (Bronze → Silver → Gold).
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display  = (
        'title_col', 'type_badge', 'tx_badge', 'region', 'delegation',
        'price_col', 'area_col', 'ppm2_col', 'bedrooms',
        'source_badge', 'status_badge', 'scraped_at',
    )
    list_filter   = (
        'property_type', 'transaction_type', 'region',
        'is_active', 'source',
        ('scraped_at', admin.DateFieldListFilter),
    )
    search_fields = ('title', 'location_raw', 'external_id', 'region__governorate', 'delegation__name')
    readonly_fields = ('external_id', 'price_per_sqm', 'scraped_at', 'created_at', 'updated_at')
    ordering      = ('-scraped_at',)
    list_per_page = 50
    date_hierarchy = 'scraped_at'
    show_full_result_count = False

    fieldsets = (
        ('Identity', {'fields': ('external_id', 'title', 'source', 'is_active')}),
        ('Classification', {'fields': ('property_type', 'transaction_type', 'currency')}),
        ('Location', {'fields': ('region', 'delegation', 'location_raw', 'latitude', 'longitude')}),
        ('Financials', {'fields': ('price', 'area_sqm', 'price_per_sqm')}),
        ('Attributes', {'fields': ('rooms', 'bedrooms', 'bathrooms', 'description')}),
        ('Media', {'fields': ('image_url',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('posted_at', 'scraped_at', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Title')
    def title_col(self, obj):
        t = (obj.title or '—')[:52]
        return t + '…' if len(obj.title or '') > 52 else t

    @admin.display(description='Type', ordering='property_type')
    def type_badge(self, obj):
        return _pill(obj.property_type.capitalize(), _TYPE_COLOR.get(obj.property_type, '#6b7280'))

    @admin.display(description='Tx', ordering='transaction_type')
    def tx_badge(self, obj):
        return _pill('Sale', '#3b82f6') if obj.transaction_type == 'sale' else _pill('Rent', '#8b5cf6')

    @admin.display(description='Price', ordering='price')
    def price_col(self, obj):
        return _money(obj.price)

    @admin.display(description='Area', ordering='area_sqm')
    def area_col(self, obj):
        return format_html('{} m²', f'{obj.area_sqm:,.0f}') if obj.area_sqm else '—'

    @admin.display(description='TND/m²', ordering='price_per_sqm')
    def ppm2_col(self, obj):
        return f'{obj.price_per_sqm:,.0f}' if obj.price_per_sqm else '—'

    @admin.display(description='Source', ordering='source')
    def source_badge(self, obj):
        colors = {
            'mubawab': '#06b6d4', 'tayara': '#f59e0b',
            'tunisie_annonce': '#8b5cf6', 'tecnocasa': '#22c55e',
            'bigdatis': '#f97316', 'manual': '#6b7280',
        }
        return _pill(obj.source, colors.get(obj.source, '#6b7280'))

    @admin.display(description='Status', boolean=True, ordering='is_active')
    def status_badge(self, obj):
        return obj.is_active


# ─────────────────────────────────────────────────────────────────────────────
# AI MODEL PREDICTIONS  (stored per-property valuations)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Valuation)
class ValuationAdmin(admin.ModelAdmin):
    list_display  = ('property_col', 'predicted_price_col', 'confidence_badge', 'comparable_count', 'model_version', 'created_at')
    search_fields = ('property__title', 'property__region__governorate', 'model_version')
    readonly_fields = ('property', 'predicted_price', 'mape_confidence', 'comparable_count', 'model_version', 'created_at')
    ordering      = ('-created_at',)
    list_per_page = 50

    fieldsets = (
        ('Property', {'fields': ('property',)}),
        ('Prediction', {'fields': ('predicted_price', 'mape_confidence', 'comparable_count', 'model_version')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )

    @admin.display(description='Property', ordering='property__title')
    def property_col(self, obj):
        t = (obj.property.title if obj.property else '—')
        return t[:50] + '…' if len(t) > 50 else t

    @admin.display(description='Predicted Price', ordering='predicted_price')
    def predicted_price_col(self, obj):
        return _money(obj.predicted_price)

    @admin.display(description='Confidence', ordering='mape_confidence')
    def confidence_badge(self, obj):
        v = obj.mape_confidence or 0
        c = '#22c55e' if v >= 80 else '#f59e0b' if v >= 65 else '#ef4444'
        return _pill(f'{v:.0f}%', c)


# ─────────────────────────────────────────────────────────────────────────────
# PRICE TRENDS  (time-series forecasting)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(PriceTrend)
class PriceTrendAdmin(admin.ModelAdmin):
    list_display  = ('region', 'property_type', 'date', 'avg_price_col', 'trend_badge', 'forecast_3m_col', 'forecast_6m_col', 'forecast_12m_col')
    list_filter   = ('region', 'property_type', 'trend_direction')
    search_fields = ('region__governorate',)
    readonly_fields = ('created_at',)
    ordering      = ('-date', 'region__governorate')
    date_hierarchy = 'date'

    fieldsets = (
        ('Scope', {'fields': ('region', 'property_type', 'date')}),
        ('Current Market', {'fields': ('avg_price', 'trend_direction')}),
        ('Forecasts', {'fields': ('forecast_3m', 'forecast_6m', 'forecast_12m')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )

    @admin.display(description='Avg Price', ordering='avg_price')
    def avg_price_col(self, obj):
        return _money(obj.avg_price)

    @admin.display(description='Trend', ordering='trend_direction')
    def trend_badge(self, obj):
        c = _TREND_COLOR.get(obj.trend_direction, '#6b7280')
        icons = {'rising': '↑', 'stable': '→', 'falling': '↓'}
        icon = icons.get(obj.trend_direction, '')
        return _pill(f'{icon} {obj.trend_direction.capitalize()}', c)

    @admin.display(description='+3M')
    def forecast_3m_col(self, obj):
        return _money(obj.forecast_3m)

    @admin.display(description='+6M')
    def forecast_6m_col(self, obj):
        return _money(obj.forecast_6m)

    @admin.display(description='+12M')
    def forecast_12m_col(self, obj):
        return _money(obj.forecast_12m)


# ─────────────────────────────────────────────────────────────────────────────
# CLIMATE RISK  (Environmental intelligence layer)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ClimateRisk)
class ClimateRiskAdmin(admin.ModelAdmin):
    list_display  = (
        'region_col', 'climate_region_badge', 'coastal_badge',
        'flood_badge', 'heat_badge', 'drought_badge',
        'risk_category_badge', 'sustainability_gauge',
        'price_adj_col', 'scenario_trend', 'updated_at',
    )
    list_filter   = (
        'risk_category', 'flood_risk', 'heat_stress_risk', 'drought_risk',
        'earthquake_risk', 'is_coastal', 'climate_region',
    )
    search_fields = ('region__governorate',)
    readonly_fields = (
        'region', 'lat', 'lon', 'is_coastal', 'climate_region',
        'flood_risk', 'heat_stress_risk', 'drought_risk', 'earthquake_risk',
        'flood_risk_score', 'heat_risk_score', 'drought_risk_score', 'earthquake_risk_score',
        'combined_risk_score', 'risk_category',
        'sustainability_score', 'sustainability_grade', 'livability_score', 'infrastructure_score',
        'avg_temp_c', 'max_summer_temp_c', 'avg_rainfall_mm', 'days_above_35c', 'sea_level_exposure',
        'price_adjustment_pct',
        'scenario_baseline', 'scenario_2c', 'scenario_4c',
        'updated_at',
    )
    ordering = ('region__governorate',)

    fieldsets = (
        ('Location', {
            'fields': ('region', 'climate_region', 'is_coastal', 'lat', 'lon'),
        }),
        ('Risk Levels', {
            'fields': (
                ('flood_risk', 'flood_risk_score'),
                ('heat_stress_risk', 'heat_risk_score'),
                ('drought_risk', 'drought_risk_score'),
                ('earthquake_risk', 'earthquake_risk_score'),
                'combined_risk_score', 'risk_category',
            ),
        }),
        ('Sustainability & Liveability', {
            'fields': (
                'sustainability_score', 'sustainability_grade',
                'livability_score', 'infrastructure_score',
            ),
        }),
        ('Climate Baseline Metrics', {
            'fields': (
                'avg_temp_c', 'max_summer_temp_c',
                'avg_rainfall_mm', 'days_above_35c', 'sea_level_exposure',
            ),
            'classes': ('collapse',),
        }),
        ('Price Impact', {
            'fields': ('price_adjustment_pct',),
        }),
        ('Climate Scenarios', {
            'fields': ('scenario_baseline', 'scenario_2c', 'scenario_4c'),
        }),
        ('Timestamps', {'fields': ('updated_at',)}),
    )

    @admin.display(description='Governorate', ordering='region__governorate')
    def region_col(self, obj):
        return format_html('<b>{}</b>', obj.region.governorate)

    @admin.display(description='Region', ordering='climate_region')
    def climate_region_badge(self, obj):
        region_colors = {
            'North': '#3b82f6', 'North-East': '#06b6d4', 'North-West': '#8b5cf6',
            'Center': '#f59e0b', 'Center-East': '#f97316', 'Center-West': '#ec4899',
            'South': '#ef4444', 'South-East': '#dc2626', 'South-West': '#b45309',
        }
        c = region_colors.get(obj.climate_region, '#6b7280')
        return _pill(obj.climate_region or '—', c) if obj.climate_region else '—'

    @admin.display(description='Coastal', boolean=True, ordering='is_coastal')
    def coastal_badge(self, obj):
        return obj.is_coastal

    @admin.display(description='Flood', ordering='flood_risk')
    def flood_badge(self, obj):
        return _pill(f'🌊 {obj.flood_risk.replace("_", " ").capitalize()}', _RISK_COLOR.get(obj.flood_risk, '#6b7280'))

    @admin.display(description='Heat', ordering='heat_stress_risk')
    def heat_badge(self, obj):
        return _pill(f'☀️ {obj.heat_stress_risk.replace("_", " ").capitalize()}', _RISK_COLOR.get(obj.heat_stress_risk, '#6b7280'))

    @admin.display(description='Drought', ordering='drought_risk')
    def drought_badge(self, obj):
        return _pill(f'💧 {obj.drought_risk.replace("_", " ").capitalize()}', _RISK_COLOR.get(obj.drought_risk, '#6b7280'))

    @admin.display(description='Category', ordering='risk_category')
    def risk_category_badge(self, obj):
        cat_colors = {
            'Low': '#22c55e', 'Moderate': '#f59e0b',
            'High': '#ef4444', 'Very High': '#7f1d1d',
        }
        c = cat_colors.get(obj.risk_category, '#6b7280')
        return _pill(obj.risk_category or '—', c)

    @admin.display(description='Sustainability', ordering='sustainability_score')
    def sustainability_gauge(self, obj):
        v = obj.sustainability_score or 0
        c = '#22c55e' if v >= 75 else '#f59e0b' if v >= 55 else '#ef4444'
        grade = obj.sustainability_grade or '?'
        return format_html(
            '<div style="display:flex;align-items:center;gap:6px">'
            '<div style="width:70px;background:#1f2937;border-radius:4px;height:7px;overflow:hidden">'
            '<div style="width:{}%;background:{};height:100%;border-radius:4px"></div></div>'
            '<span style="font-size:11px;font-weight:700;color:{}">{} {}</span></div>',
            int(v), c, c, f'{v:.0f}', grade,
        )

    @admin.display(description='Price Impact', ordering='price_adjustment_pct')
    def price_adj_col(self, obj):
        v = obj.price_adjustment_pct
        if v is None:
            return '—'
        c = '#22c55e' if v > 0 else '#ef4444' if v < -5 else '#f59e0b'
        sign = '+' if v >= 0 else ''
        return _pill(f'{sign}{v:.1f}%', c)

    @admin.display(description='+2°C / +4°C', ordering='scenario_2c')
    def scenario_trend(self, obj):
        b  = obj.scenario_baseline
        s2 = obj.scenario_2c
        s4 = obj.scenario_4c
        if b is None or s2 is None or s4 is None:
            return '—'
        d2 = round(s2 - b, 1)
        d4 = round(s4 - b, 1)
        c2 = '#22c55e' if d2 >= 0 else '#ef4444'
        c4 = '#22c55e' if d4 >= 0 else '#ef4444'
        sign2 = '+' if d2 >= 0 else ''
        sign4 = '+' if d4 >= 0 else ''
        return format_html(
            '<span style="color:{};font-size:11px;font-weight:600">{}{}</span>'
            '<span style="color:#6b7280;margin:0 4px">/</span>'
            '<span style="color:{};font-size:11px;font-weight:600">{}{}</span>',
            c2, sign2, d2, c4, sign4, d4,
        )


# ─────────────────────────────────────────────────────────────────────────────
# DELEGATION MARKET SNAPSHOTS  (Features 2 & 5 — per-delegation analytics)
# ─────────────────────────────────────────────────────────────────────────────

class DelegationMarketSegmentInline(admin.TabularInline):
    model   = DelegationMarketSegment
    extra   = 0
    fields  = ('property_type', 'transaction_type', 'listing_count', 'median_price', 'avg_price_per_sqm', 'trend_direction')
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DelegationMarketSnapshot)
class DelegationMarketSnapshotAdmin(admin.ModelAdmin):
    list_display  = (
        'delegation', 'gov_col', 'as_of_date',
        'listing_count', 'median_sale_col', 'median_rent_col',
        'ppm2_col', 'trend_badge', 'updated_at',
    )
    list_filter   = ('delegation__region', 'trend_direction', 'as_of_date')
    search_fields = ('delegation__name', 'delegation__region__governorate')
    readonly_fields = ('updated_at',)
    ordering      = ('-as_of_date', 'delegation__region__governorate', 'delegation__name')
    date_hierarchy = 'as_of_date'
    inlines       = [DelegationMarketSegmentInline]

    fieldsets = (
        ('Scope', {'fields': ('delegation', 'as_of_date')}),
        ('Volume', {'fields': ('listing_count', 'sale_listing_count', 'rent_listing_count')}),
        ('Sale Prices', {'fields': ('median_sale_price', 'avg_sale_price', 'median_price_per_sqm')}),
        ('Rent Prices', {'fields': ('median_rent_price', 'avg_rent_price')}),
        ('Dynamics', {'fields': ('supply_pressure', 'median_days_on_market', 'price_per_sqm_distribution')}),
        ('Climate', {'fields': ('climate_risk_level', 'heat_risk_level', 'sustainability_score')}),
        ('Forecast', {'fields': ('trend_direction', 'forecast_3m', 'forecast_6m', 'forecast_12m')}),
        ('Timestamps', {'fields': ('updated_at',)}),
    )

    @admin.display(description='Governorate', ordering='delegation__region__governorate')
    def gov_col(self, obj):
        return obj.delegation.region.governorate if obj.delegation else '—'

    @admin.display(description='Median Sale', ordering='median_sale_price')
    def median_sale_col(self, obj):
        return _money(obj.median_sale_price)

    @admin.display(description='Median Rent', ordering='median_rent_price')
    def median_rent_col(self, obj):
        return _money(obj.median_rent_price)

    @admin.display(description='TND/m²', ordering='median_price_per_sqm')
    def ppm2_col(self, obj):
        return f'{obj.median_price_per_sqm:,.0f}' if obj.median_price_per_sqm else '—'

    @admin.display(description='Trend', ordering='trend_direction')
    def trend_badge(self, obj):
        if not obj.trend_direction:
            return '—'
        c = _TREND_COLOR.get(obj.trend_direction, '#6b7280')
        icons = {'rising': '↑', 'stable': '→', 'falling': '↓'}
        return _pill(f"{icons.get(obj.trend_direction,'')} {obj.trend_direction.capitalize()}", c)


@admin.register(DelegationMarketSegment)
class DelegationMarketSegmentAdmin(admin.ModelAdmin):
    list_display  = (
        'delegation_col', 'property_type', 'transaction_type',
        'listing_count', 'median_price_col', 'avg_ppm2_col', 'trend_badge',
    )
    list_filter   = ('property_type', 'transaction_type', 'trend_direction', 'snapshot__delegation__region')
    search_fields = ('snapshot__delegation__name', 'snapshot__delegation__region__governorate')
    readonly_fields = (
        'snapshot', 'property_type', 'transaction_type', 'listing_count',
        'median_price', 'avg_price', 'median_price_per_sqm', 'avg_price_per_sqm',
        'min_price', 'max_price', 'avg_surface_sqm', 'median_surface_sqm',
        'median_days_on_market', 'trend_direction', 'forecast_3m', 'forecast_6m', 'forecast_12m',
    )
    ordering = ('snapshot__delegation__region__governorate', 'snapshot__delegation__name', 'property_type')

    @admin.display(description='Delegation')
    def delegation_col(self, obj):
        if obj.snapshot and obj.snapshot.delegation:
            d = obj.snapshot.delegation
            return f'{d.name} ({d.region.governorate})'
        return '—'

    @admin.display(description='Median Price', ordering='median_price')
    def median_price_col(self, obj):
        return _money(obj.median_price)

    @admin.display(description='Avg TND/m²', ordering='avg_price_per_sqm')
    def avg_ppm2_col(self, obj):
        return f'{obj.avg_price_per_sqm:,.0f}' if obj.avg_price_per_sqm else '—'

    @admin.display(description='Trend', ordering='trend_direction')
    def trend_badge(self, obj):
        if not obj.trend_direction:
            return '—'
        return _pill(obj.trend_direction.capitalize(), _TREND_COLOR.get(obj.trend_direction, '#6b7280'))
