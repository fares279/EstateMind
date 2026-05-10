"""
users/admin.py — Platform Users

Manages registered users, activity logs, saved properties,
valuation history, and portfolio assets.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import Portfolio, SavedProperty, User, UserActivity, UserValuation


def _pill(text, color):
    return format_html(
        '<span style="background:{0}22;color:{0};border:1px solid {0}44;'
        'padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;white-space:nowrap">'
        '{1}</span>',
        color, text,
    )


_PLAN_COLORS = {
    'free':     '#6b7280',
    'pro':      '#3b82f6',
    'premium':  '#8b5cf6',
    'investor': '#f59e0b',
}
_ROLE_COLORS = {
    'viewer':   '#6b7280',
    'investor': '#f59e0b',
    'premium':  '#8b5cf6',
    'pro':      '#3b82f6',
    'admin':    '#ef4444',
}
_ACTIVITY_COLORS = {
    'valuation':    '#3b82f6',
    'analysis':     '#8b5cf6',
    'simulation':   '#f97316',
    'legal':        '#06b6d4',
    'explore':      '#22c55e',
    'save_property':'#f59e0b',
    'cta_click':    '#6b7280',
}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'email', 'full_name', 'plan_badge', 'role_badge',
        'verified_badge', 'is_staff', 'created_at',
    )
    list_filter  = ('plan', 'role', 'is_staff', 'is_active', 'is_email_verified')
    search_fields = ('email', 'full_name', 'phone')
    ordering = ('-created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Credentials', {
            'fields': ('email', 'password', 'is_email_verified'),
        }),
        ('Profile', {
            'fields': ('full_name', 'phone', 'profile_image'),
        }),
        ('Plan & Role', {
            'fields': ('plan', 'plan_expires_at', 'role'),
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Preferences', {
            'fields': ('preferences',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_login', 'last_login_ip'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login', 'last_login_ip')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'plan', 'role'),
        }),
    )

    @admin.display(description='Plan', ordering='plan')
    def plan_badge(self, obj):
        c = _PLAN_COLORS.get(obj.plan, '#6b7280')
        return _pill(obj.get_plan_display() if hasattr(obj, 'get_plan_display') else obj.plan.capitalize(), c)

    @admin.display(description='Role', ordering='role')
    def role_badge(self, obj):
        c = _ROLE_COLORS.get(obj.role, '#6b7280')
        return _pill(obj.role.capitalize(), c)

    @admin.display(description='Verified', boolean=True, ordering='is_email_verified')
    def verified_badge(self, obj):
        return obj.is_email_verified


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'activity_badge', 'feature', 'created_at')
    list_filter  = ('activity_type', ('created_at', admin.DateFieldListFilter))
    search_fields = ('user__email', 'feature')
    ordering = ('-created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'
    readonly_fields = ('user', 'activity_type', 'feature', 'metadata', 'created_at')

    def has_add_permission(self, request):
        return False

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        return format_html('<span style="font-size:12px">{}</span>', obj.user.email if obj.user else '—')

    @admin.display(description='Activity', ordering='activity_type')
    def activity_badge(self, obj):
        c = _ACTIVITY_COLORS.get(obj.activity_type, '#6b7280')
        return _pill(obj.get_activity_type_display(), c)


@admin.register(SavedProperty)
class SavedPropertyAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'title_col', 'price_col', 'location', 'created_at')
    list_filter  = (('created_at', admin.DateFieldListFilter),)
    search_fields = ('user__email', 'property_id', 'title', 'location')
    ordering = ('-created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'
    readonly_fields = ('user', 'property_id', 'title', 'price', 'location', 'created_at')

    def has_add_permission(self, request):
        return False

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        return format_html('<span style="font-size:12px">{}</span>', obj.user.email if obj.user else '—')

    @admin.display(description='Property', ordering='title')
    def title_col(self, obj):
        t = (obj.title or obj.property_id or '—')[:60]
        return t

    @admin.display(description='Price', ordering='price')
    def price_col(self, obj):
        if not obj.price:
            return '—'
        if obj.price >= 1_000_000:
            return f'{obj.price / 1_000_000:.2f}M TND'
        if obj.price >= 1_000:
            return f'{obj.price / 1_000:.1f}K TND'
        return f'{obj.price:,.0f} TND'


@admin.register(UserValuation)
class UserValuationAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'estimated_price_col', 'location_col', 'surface_col', 'created_at')
    list_filter  = (('created_at', admin.DateFieldListFilter),)
    search_fields = ('user__email', 'input_location')
    ordering = ('-created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'
    readonly_fields = ('user', 'property_id', 'estimated_price', 'input_surface', 'input_location', 'created_at')

    def has_add_permission(self, request):
        return False

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        return format_html('<span style="font-size:12px">{}</span>', obj.user.email if obj.user else '—')

    @admin.display(description='Estimated Price', ordering='estimated_price')
    def estimated_price_col(self, obj):
        v = obj.estimated_price
        if not v:
            return '—'
        c = '#22c55e' if v >= 500_000 else '#3b82f6' if v >= 200_000 else '#f59e0b'
        if v >= 1_000_000:
            label = f'{v / 1_000_000:.2f}M TND'
        elif v >= 1_000:
            label = f'{v / 1_000:.1f}K TND'
        else:
            label = f'{v:,.0f} TND'
        return format_html('<b style="color:{}">{}</b>', c, label)

    @admin.display(description='Location', ordering='input_location')
    def location_col(self, obj):
        return obj.input_location or '—'

    @admin.display(description='Area', ordering='input_surface')
    def surface_col(self, obj):
        return format_html('{} m²', f'{obj.input_surface:,.0f}') if obj.input_surface else '—'


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'property_name', 'purchase_col', 'value_col', 'gain_col', 'rent_col', 'yield_col', 'created_at')
    list_filter  = (('created_at', admin.DateFieldListFilter),)
    search_fields = ('user__email', 'property_name')
    ordering = ('-created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'

    def _fmt(self, v):
        if not v:
            return '—'
        if v >= 1_000_000:
            return f'{v / 1_000_000:.2f}M'
        if v >= 1_000:
            return f'{v / 1_000:.1f}K'
        return f'{v:,.0f}'

    @admin.display(description='User', ordering='user__email')
    def user_col(self, obj):
        return format_html('<span style="font-size:12px">{}</span>', obj.user.email if obj.user else '—')

    @admin.display(description='Purchase Price', ordering='purchase_price')
    def purchase_col(self, obj):
        return self._fmt(obj.purchase_price)

    @admin.display(description='Current Value', ordering='current_value')
    def value_col(self, obj):
        return format_html('<b>{}</b>', self._fmt(obj.current_value))

    @admin.display(description='Gain/Loss')
    def gain_col(self, obj):
        if not obj.purchase_price or not obj.current_value:
            return '—'
        gain = obj.current_value - obj.purchase_price
        pct = gain / obj.purchase_price * 100
        c = '#22c55e' if gain >= 0 else '#ef4444'
        sign = '+' if gain >= 0 else ''
        return format_html('<span style="color:{};font-weight:600">{}{}%</span>', c, sign, f'{pct:.1f}')

    @admin.display(description='Monthly Rent', ordering='monthly_rent')
    def rent_col(self, obj):
        return self._fmt(obj.monthly_rent) if obj.monthly_rent else '—'

    @admin.display(description='Gross Yield')
    def yield_col(self, obj):
        if not obj.monthly_rent or not obj.current_value:
            return '—'
        annual_yield = (obj.monthly_rent * 12) / obj.current_value * 100
        c = '#22c55e' if annual_yield >= 6 else '#f59e0b' if annual_yield >= 4 else '#ef4444'
        return format_html('<span style="color:{};font-weight:600">{}%</span>', c, f'{annual_yield:.1f}')
