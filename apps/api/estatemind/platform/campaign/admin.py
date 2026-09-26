"""
campaign/admin.py — Campaign & Outreach

Manages participants for the #Aaref_Bledek campaign and future outreach programmes.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Participant

_ROLE_COLOR = {
    'learner': '#3b82f6', 'contributor': '#22c55e',
    'volunteer': '#f59e0b', 'ambassador': '#ec4899',
}


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display  = ('full_name', 'email', 'phone', 'region', 'role_badge', 'status_badge', 'created_at')
    list_filter   = ('role', 'region', 'is_active', ('created_at', admin.DateFieldListFilter))
    search_fields = ('full_name', 'email', 'phone', 'region')
    readonly_fields = ('created_at',)
    ordering      = ('-created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Identity', {'fields': ('full_name', 'email', 'phone')}),
        ('Profile', {'fields': ('region', 'role', 'motivation')}),
        ('Status', {'fields': ('is_active', 'created_at')}),
    )

    actions = ['mark_active', 'mark_inactive']

    @admin.display(description='Role', ordering='role')
    def role_badge(self, obj):
        color = _ROLE_COLOR.get(obj.role, '#6b7280')
        return format_html(
            '<span style="background:{0}22;color:{0};border:1px solid {0}44;'
            'padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600">{1}</span>',
            color, obj.get_role_display(),
        )

    @admin.display(description='Status', boolean=True, ordering='is_active')
    def status_badge(self, obj):
        return obj.is_active

    @admin.action(description='Mark selected participants as active')
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} participant(s) marked as active.')

    @admin.action(description='Mark selected participants as inactive')
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} participant(s) marked as inactive.')
