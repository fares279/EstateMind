from django.apps import AppConfig


class CampaignConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estatemind.platform.campaign'
    label = 'campaign'
    verbose_name = 'Campaign & Outreach'
