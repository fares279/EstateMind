import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ValuationRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('property_type',    models.CharField(max_length=20, choices=[('apartment','Apartment'),('house','House'),('villa','Villa'),('land','Land'),('commercial','Commercial'),('office','Office'),('farm','Farm')])),
                ('transaction_type', models.CharField(max_length=10, choices=[('sale','Sale'),('rent','Rent')], default='sale')),
                ('governorate',      models.CharField(max_length=100, blank=True)),
                ('city',             models.CharField(max_length=100, blank=True)),
                ('neighborhood',     models.CharField(max_length=100, blank=True)),
                ('size_m2',          models.FloatField(null=True, blank=True)),
                ('bedrooms',         models.IntegerField(null=True, blank=True)),
                ('bathrooms',        models.IntegerField(null=True, blank=True)),
                ('condition',        models.CharField(max_length=30, blank=True)),
                ('has_pool',         models.BooleanField(default=False)),
                ('has_garden',       models.BooleanField(default=False)),
                ('has_parking',      models.BooleanField(default=False)),
                ('sea_view',         models.BooleanField(default=False)),
                ('elevator',         models.BooleanField(default=False)),
                ('description',      models.TextField(blank=True)),
                ('image_count',      models.IntegerField(default=0)),
                ('estimated_price',  models.FloatField()),
                ('lower_bound',      models.FloatField()),
                ('upper_bound',      models.FloatField()),
                ('price_per_m2',     models.FloatField(null=True, blank=True)),
                ('confidence',       models.IntegerField(default=50)),
                ('confidence_level', models.CharField(max_length=20, default='Medium')),
                ('prediction_mode',  models.CharField(max_length=50, default='heuristic')),
                ('response_data',    models.JSONField(default=dict)),
                ('created_at',       models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='valuation_requests',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
