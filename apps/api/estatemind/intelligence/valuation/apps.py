from django.apps import AppConfig


class ValuationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estatemind.intelligence.valuation'
    label = 'valuation'
    verbose_name = 'AI Valuation Engine'
