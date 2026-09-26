"""
simulation/admin.py — Multi-Agent Real Estate Simulator

Read-only admin for monitoring simulation runs. Runs are created exclusively
via the REST API; the admin provides observability and audit trails.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import SimulationRun

_STATUS_COLORS = {
    'pending':  '#6b7280',
    'running':  '#3b82f6',
    'complete': '#22c55e',
    'error':    '#ef4444',
}
_STATUS_ICONS = {
    'pending':  '⏳',
    'running':  '⚙',
    'complete': '✓',
    'error':    '✗',
}
_SCALE_COLORS = {
    'tiny':   '#6b7280',
    'medium': '#3b82f6',
    'large':  '#8b5cf6',
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
    if v >= 1_000_000:
        return f'{v / 1_000_000:.2f}M TND'
    if v >= 1_000:
        return f'{v / 1_000:.1f}K TND'
    return f'{v:,.0f} TND'


@admin.register(SimulationRun)
class SimulationRunAdmin(admin.ModelAdmin):
    list_display = (
        'run_id_short', 'scenario_badge', 'scale_badge',
        'status_badge', 'progress_bar',
        'total_transactions', 'avg_price_col',
        'duration_col', 'created_at',
    )
    list_filter  = ('status', 'scenario_name', 'agent_scale')
    search_fields = ('run_id', 'scenario_name')
    readonly_fields = (
        'run_id', 'scenario_name', 'agent_scale', 'num_months',
        'status', 'current_month', 'total_transactions', 'avg_transaction_price',
        'error_message',
        'created_at', 'started_at', 'completed_at', 'updated_at',
        'monthly_states', 'agent_outcomes', 'final_metrics',
    )
    ordering = ('-created_at',)
    list_per_page = 30
    date_hierarchy = 'created_at'
    show_full_result_count = False

    fieldsets = (
        ('Simulation Identity', {
            'fields': ('run_id', 'scenario_name', 'agent_scale', 'num_months'),
        }),
        ('Progress', {
            'fields': ('status', 'current_month', 'error_message'),
        }),
        ('Results', {
            'fields': ('total_transactions', 'avg_transaction_price'),
        }),
        ('Timeseries & Agent Data', {
            'fields': ('monthly_states', 'agent_outcomes', 'final_metrics'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description='Run ID')
    def run_id_short(self, obj):
        uid = str(obj.run_id)
        return format_html(
            '<span style="font-family:monospace;font-size:11px;color:#9ca3af">{}</span>',
            uid[:8] + '…',
        )

    @admin.display(description='Scenario', ordering='scenario_name')
    def scenario_badge(self, obj):
        scenario_colors = {
            'baseline':           '#6366f1',
            'infrastructure_push':'#10b981',
            'interest_rate_hike': '#f59e0b',
            'liquidity_crunch':   '#ef4444',
            'policy_tightening':  '#8b5cf6',
            'monetary_easing':    '#06b6d4',
            'supply_expansion':   '#84cc16',
            'speculative_boom':   '#f97316',
            'climate_stress':     '#64748b',
        }
        c = scenario_colors.get(obj.scenario_name, '#6b7280')
        label = obj.scenario_name.replace('_', ' ').title()
        return _pill(label, c)

    @admin.display(description='Scale', ordering='agent_scale')
    def scale_badge(self, obj):
        c = _SCALE_COLORS.get(obj.agent_scale, '#6b7280')
        return _pill(obj.agent_scale.capitalize(), c)

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        c = _STATUS_COLORS.get(obj.status, '#6b7280')
        icon = _STATUS_ICONS.get(obj.status, '')
        return _pill(f'{icon} {obj.status.capitalize()}', c)

    @admin.display(description='Progress', ordering='current_month')
    def progress_bar(self, obj):
        pct = round(obj.current_month / max(1, obj.num_months) * 100)
        bar_color = _STATUS_COLORS.get(obj.status, '#6b7280')
        return format_html(
            '<div style="display:flex;align-items:center;gap:6px">'
            '<div style="width:80px;background:#1f2937;border-radius:4px;height:7px;overflow:hidden">'
            '<div style="width:{0}%;background:{1};height:100%;border-radius:4px"></div></div>'
            '<span style="font-size:11px;color:#9ca3af">{2}/{3}</span>'
            '</div>',
            pct, bar_color, obj.current_month, obj.num_months,
        )

    @admin.display(description='Avg Price', ordering='avg_transaction_price')
    def avg_price_col(self, obj):
        return _money(float(obj.avg_transaction_price or 0) or None)

    @admin.display(description='Duration')
    def duration_col(self, obj):
        if not obj.started_at:
            return '—'
        end = obj.completed_at or obj.updated_at
        if not end:
            return '—'
        delta = end - obj.started_at
        secs = int(delta.total_seconds())
        if secs < 60:
            return format_html('<span style="font-size:12px">{}s</span>', secs)
        return format_html('<span style="font-size:12px">{}m</span>', f'{secs / 60:.1f}')
