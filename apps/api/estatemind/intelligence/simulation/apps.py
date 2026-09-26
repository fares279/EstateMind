from django.apps import AppConfig


class SimulationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = 'estatemind.intelligence.simulation'
    label = 'simulation'
    verbose_name = "Multi-Agent Real Estate Simulator"
