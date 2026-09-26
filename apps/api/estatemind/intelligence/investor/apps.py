from django.apps import AppConfig


class InvestorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estatemind.intelligence.investor'
    label = 'investor'
    verbose_name = 'Investor Intelligence'
