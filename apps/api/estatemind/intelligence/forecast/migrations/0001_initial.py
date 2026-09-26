from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='DelegationPriceData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delegation_name', models.CharField(db_index=True, max_length=255)),
                ('governorate',     models.CharField(db_index=True, max_length=100)),
                ('property_type',   models.CharField(choices=[('apartment','Apartment'),('house','House'),('commercial','Commercial'),('land','Land')], db_index=True, max_length=20)),
                ('price_min',        models.FloatField()),
                ('price_avg',        models.FloatField()),
                ('price_max',        models.FloatField()),
                ('annual_trend_pct', models.FloatField()),
                ('notes',            models.TextField(blank=True)),
            ],
            options={
                'ordering': ['governorate', 'delegation_name', 'property_type'],
            },
        ),
        migrations.AddIndex(
            model_name='delegationpricedata',
            index=models.Index(fields=['governorate', 'property_type'], name='forecast_dp_gov_pt_idx'),
        ),
        migrations.AddIndex(
            model_name='delegationpricedata',
            index=models.Index(fields=['property_type', 'price_avg'], name='forecast_dp_pt_avg_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='delegationpricedata',
            unique_together={('delegation_name', 'governorate', 'property_type')},
        ),

        migrations.CreateModel(
            name='DelegationForecast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delegation_name',        models.CharField(db_index=True, max_length=255)),
                ('governorate',            models.CharField(blank=True, db_index=True, max_length=100)),
                ('property_type',          models.CharField(choices=[('apartment','Apartment'),('house','House'),('commercial','Commercial'),('land','Land')], db_index=True, default='apartment', max_length=20)),
                ('forecast_origin',        models.DateField()),
                ('forecast_month',         models.DateField()),
                ('horizon_idx',            models.IntegerField()),
                ('predicted_price_per_m2', models.FloatField()),
                ('model_mape_pct',         models.FloatField(default=2.5)),
                ('model_version',          models.CharField(default='csv_v2', max_length=50)),
                ('created_at',             models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['delegation_name', 'property_type', 'horizon_idx'],
            },
        ),
        migrations.AddIndex(
            model_name='delegationforecast',
            index=models.Index(fields=['delegation_name', 'forecast_origin', 'property_type'], name='forecast_df_del_orig_pt_idx'),
        ),
        migrations.AddIndex(
            model_name='delegationforecast',
            index=models.Index(fields=['governorate', 'horizon_idx', 'property_type'], name='forecast_df_gov_h_pt_idx'),
        ),
        migrations.AddIndex(
            model_name='delegationforecast',
            index=models.Index(fields=['property_type', 'horizon_idx'], name='forecast_df_pt_h_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='delegationforecast',
            unique_together={('delegation_name', 'governorate', 'forecast_origin', 'horizon_idx', 'property_type')},
        ),
    ]
