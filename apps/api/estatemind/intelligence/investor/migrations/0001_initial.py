from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PortfolioAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('property_name', models.CharField(max_length=200)),
                ('property_type', models.CharField(choices=[('apartment', 'Apartment'), ('house', 'House'), ('commercial', 'Commercial'), ('land', 'Land')], default='apartment', max_length=20)),
                ('governorate', models.CharField(max_length=100)),
                ('delegation', models.CharField(max_length=100)),
                ('surface_m2', models.FloatField()),
                ('room_count', models.IntegerField(default=3)),
                ('floor_level', models.IntegerField(default=0)),
                ('amenity_score', models.FloatField(default=1.0)),
                ('acquisition_price_tnd', models.FloatField()),
                ('acquisition_date', models.DateField()),
                ('current_value_tnd', models.FloatField(blank=True, null=True)),
                ('is_rented', models.BooleanField(default=False)),
                ('monthly_rent_tnd', models.FloatField(default=0.0)),
                ('monthly_opex_tnd', models.FloatField(default=0.0)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='investor_portfolio_assets', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ScanResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('listing_price_tnd', models.FloatField()),
                ('surface_m2', models.FloatField()),
                ('property_type', models.CharField(max_length=20)),
                ('governorate', models.CharField(max_length=100)),
                ('delegation', models.CharField(max_length=100)),
                ('room_count', models.IntegerField(default=3)),
                ('undervaluation_label', models.CharField(blank=True, max_length=30)),
                ('undervaluation_proba', models.FloatField(default=0.0)),
                ('buy_signal', models.CharField(blank=True, max_length=20)),
                ('p_buy', models.FloatField(default=0.0)),
                ('gross_yield_pct', models.FloatField(default=0.0)),
                ('opportunity_score', models.FloatField(default=0.0)),
                ('investment_grade', models.CharField(blank=True, max_length=5)),
                ('full_result', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scan_results', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
