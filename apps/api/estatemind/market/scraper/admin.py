"""
scraper/admin.py — Data Collection Pipeline

Manages scrape sources (configurations), scrape jobs (execution logs),
and scraped listings (Bronze → Silver → Gold pipeline).
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import ScrapeJob, ScrapedListing, ScrapeSource

_STATUS_COLORS = {
    'pending':    '#6b7280',
    'running':    '#3b82f6',
    'completed':  '#22c55e',
    'failed':     '#ef4444',
    'cancelled':  '#f59e0b',
    'raw':        '#6b7280',
    'normalized': '#3b82f6',
    'imported':   '#22c55e',
    'duplicate':  '#f97316',
}
_SOURCE_COLORS = {
    'mubawab':         '#06b6d4',
    'tayara':          '#f59e0b',
    'tunisie_annonce': '#8b5cf6',
    'tecnocasa':       '#22c55e',
    'bigdatis':        '#f97316',
    'manual':          '#6b7280',
}


def _pill(text, color):
    return format_html(
        '<span style="background:{0}22;color:{0};border:1px solid {0}44;'
        'padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;white-space:nowrap">'
        '{1}</span>',
        color, text,
    )


@admin.register(ScrapeSource)
class ScrapeSourceAdmin(admin.ModelAdmin):
    list_display  = (
        'name', 'scraper_class', 'active_badge', 'max_listings',
        'schedule_col', 'last_scraped_col', 'job_count',
    )
    list_filter   = ('is_active',)
    search_fields = ('name', 'scraper_class')
    readonly_fields = ('last_scraped_at', 'created_at', 'updated_at')
    ordering = ('name',)

    fieldsets = (
        ('Source Configuration', {
            'fields': ('name', 'scraper_class', 'is_active', 'max_listings', 'schedule_hours'),
        }),
        ('Timestamps', {
            'fields': ('last_scraped_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Active', boolean=True, ordering='is_active')
    def active_badge(self, obj):
        return obj.is_active

    @admin.display(description='Schedule', ordering='schedule_hours')
    def schedule_col(self, obj):
        h = obj.schedule_hours
        if not h:
            return '—'
        return format_html('<span style="font-size:12px">Every {}h</span>', h)

    @admin.display(description='Last Scraped', ordering='last_scraped_at')
    def last_scraped_col(self, obj):
        if not obj.last_scraped_at:
            return format_html('<span style="color:#6b7280;font-size:11px">Never</span>')
        return format_html(
            '<span style="font-size:12px">{}</span>',
            obj.last_scraped_at.strftime('%Y-%m-%d %H:%M'),
        )

    @admin.display(description='Jobs')
    def job_count(self, obj):
        n = obj.jobs.count()
        return format_html('<b>{}</b>', n) if n else '—'


class ScrapeJobInline(admin.TabularInline):
    model = ScrapeJob
    extra = 0
    readonly_fields = (
        'status', 'started_at', 'finished_at',
        'records_scraped', 'records_imported', 'records_duplicates', 'records_failed',
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ScrapeJob)
class ScrapeJobAdmin(admin.ModelAdmin):
    list_display = (
        'id_col', 'source_badge', 'status_badge', 'triggered_by',
        'scraped_col', 'imported_col', 'dupes_col', 'failed_col',
        'started_at', 'duration_col',
    )
    list_filter  = ('status', 'source', 'triggered_by')
    search_fields = ('source__name', 'error_log')
    readonly_fields = (
        'source', 'status', 'triggered_by', 'started_at', 'finished_at',
        'urls_discovered', 'records_scraped', 'records_normalized',
        'records_imported', 'records_duplicates', 'records_failed',
        'error_log', 'created_at', 'updated_at',
    )
    ordering = ('-created_at',)
    list_per_page = 30
    date_hierarchy = 'created_at'
    show_full_result_count = False

    fieldsets = (
        ('Job', {'fields': ('source', 'status', 'triggered_by')}),
        ('Counters', {
            'fields': (
                'urls_discovered',
                'records_scraped', 'records_normalized',
                'records_imported', 'records_duplicates', 'records_failed',
            ),
        }),
        ('Error Log', {'fields': ('error_log',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('started_at', 'finished_at', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description='Job', ordering='id')
    def id_col(self, obj):
        return format_html('<span style="font-family:monospace;font-size:11px;color:#9ca3af">#{}</span>', obj.pk)

    @admin.display(description='Source', ordering='source__name')
    def source_badge(self, obj):
        if not obj.source:
            return '—'
        c = _SOURCE_COLORS.get(obj.source.name.lower(), '#6b7280')
        return _pill(obj.source.name, c)

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        c = _STATUS_COLORS.get(obj.status, '#6b7280')
        icons = {'completed': '✓', 'failed': '✗', 'running': '⚙', 'pending': '⏳', 'cancelled': '⊘'}
        icon = icons.get(obj.status, '')
        return _pill(f'{icon} {obj.get_status_display()}', c)

    @admin.display(description='Scraped', ordering='records_scraped')
    def scraped_col(self, obj):
        return format_html('<b>{}</b>', obj.records_scraped or 0)

    @admin.display(description='Imported', ordering='records_imported')
    def imported_col(self, obj):
        n = obj.records_imported or 0
        c = '#22c55e' if n > 0 else '#6b7280'
        return format_html('<b style="color:{}">{}</b>', c, n)

    @admin.display(description='Dupes', ordering='records_duplicates')
    def dupes_col(self, obj):
        n = obj.records_duplicates or 0
        return format_html('<span style="color:#f59e0b">{}</span>', n) if n else '—'

    @admin.display(description='Failed', ordering='records_failed')
    def failed_col(self, obj):
        n = obj.records_failed or 0
        return format_html('<span style="color:#ef4444">{}</span>', n) if n else '—'

    @admin.display(description='Duration')
    def duration_col(self, obj):
        secs = obj.duration_seconds
        if secs is None:
            return '—'
        if secs < 60:
            return format_html('<span style="font-size:12px">{}s</span>', int(secs))
        return format_html('<span style="font-size:12px">{}m</span>', f'{secs / 60:.1f}')


@admin.register(ScrapedListing)
class ScrapedListingAdmin(admin.ModelAdmin):
    list_display = (
        'short_id', 'source_badge', 'status_badge',
        'title_col', 'governorate_col', 'price_col', 'type_col', 'scraped_at',
    )
    list_filter  = ('status', 'source')
    search_fields = ('source_url', 'raw_data', 'normalized_data')
    readonly_fields = (
        'external_id', 'source', 'job', 'source_url', 'status',
        'raw_data', 'normalized_data', 'property', 'duplicate_of',
        'error_message', 'scraped_at', 'normalized_at', 'imported_at',
    )
    ordering = ('-scraped_at',)
    list_per_page = 50
    date_hierarchy = 'scraped_at'
    show_full_result_count = False

    def has_add_permission(self, request):
        return False

    @admin.display(description='ID')
    def short_id(self, obj):
        eid = (obj.external_id or '')
        return format_html(
            '<span style="font-family:monospace;font-size:11px;color:#9ca3af">{}</span>',
            eid[:12] + '…' if len(eid) > 12 else eid,
        )

    @admin.display(description='Source', ordering='source')
    def source_badge(self, obj):
        c = _SOURCE_COLORS.get((obj.source or '').lower(), '#6b7280')
        return _pill(obj.source or '—', c)

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        c = _STATUS_COLORS.get(obj.status, '#6b7280')
        return _pill(obj.get_status_display(), c)

    @admin.display(description='Title')
    def title_col(self, obj):
        t = (obj.raw_data or {}).get('title', '—')
        return (t[:55] + '…') if len(t) > 55 else t

    @admin.display(description='Governorate')
    def governorate_col(self, obj):
        return (obj.normalized_data or {}).get('governorate', '—')

    @admin.display(description='Price (TND)')
    def price_col(self, obj):
        p = (obj.normalized_data or {}).get('price_tnd')
        if not p:
            return '—'
        if p >= 1_000_000:
            return format_html('<b>{}M</b>', f'{p / 1_000_000:.2f}')
        if p >= 1_000:
            return format_html('<b>{}K</b>', f'{p / 1_000:.1f}')
        return format_html('<b>{}</b>', f'{p:,.0f}')

    @admin.display(description='Type')
    def type_col(self, obj):
        t = (obj.normalized_data or {}).get('property_type', '')
        if not t:
            return '—'
        colors = {
            'apartment': '#3b82f6', 'house': '#8b5cf6',
            'commercial': '#f97316', 'land': '#f59e0b',
        }
        return _pill(t.capitalize(), colors.get(t, '#6b7280'))
