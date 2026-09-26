from django.apps import AppConfig


class ClimateConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estatemind.intelligence.climate'
    label = 'climate'
    verbose_name = 'Climate Intelligence'
