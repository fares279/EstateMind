from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('valuation', '0003_delegationforecast'),
    ]

    operations = [
        # 1. Drop old unique_together before touching the columns it covers
        migrations.AlterUniqueTogether(
            name='delegationforecast',
            unique_together=set(),
        ),

        # 2. Add property_type column (default='apartment' fills existing rows)
        migrations.AddField(
            model_name='delegationforecast',
            name='property_type',
            field=models.CharField(
                choices=[
                    ('apartment', 'Apartment'),
                    ('house', 'House'),
                    ('commercial', 'Commercial'),
                    ('land', 'Land'),
                ],
                default='apartment',
                db_index=True,
                max_length=20,
            ),
        ),

        # 3. New unique_together that includes property_type
        migrations.AlterUniqueTogether(
            name='delegationforecast',
            unique_together={('delegation_name', 'forecast_origin', 'horizon_idx', 'property_type')},
        ),

        # 4. Update ordering
        migrations.AlterModelOptions(
            name='delegationforecast',
            options={'ordering': ['delegation_name', 'property_type', 'horizon_idx']},
        ),

        # 5. Create DelegationPriceData table
        migrations.CreateModel(
            name='DelegationPriceData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delegation_name', models.CharField(db_index=True, max_length=255)),
                ('governorate', models.CharField(db_index=True, max_length=100)),
                ('property_type', models.CharField(
                    choices=[
                        ('apartment', 'Apartment'),
                        ('house', 'House'),
                        ('commercial', 'Commercial'),
                        ('land', 'Land'),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ('price_min', models.FloatField()),
                ('price_avg', models.FloatField()),
                ('price_max', models.FloatField()),
                ('annual_trend_pct', models.FloatField()),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['governorate', 'delegation_name', 'property_type'],
            },
        ),

        # 6. Unique constraint on DelegationPriceData
        migrations.AlterUniqueTogether(
            name='delegationpricedata',
            unique_together={('delegation_name', 'property_type')},
        ),
    ]
