from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valuation', '0004_add_property_type_and_price_data'),
    ]

    operations = [
        # Fix DelegationPriceData: add governorate to unique key
        migrations.AlterUniqueTogether(
            name='delegationpricedata',
            unique_together={('delegation_name', 'governorate', 'property_type')},
        ),

        # Fix DelegationForecast: add governorate to unique key
        migrations.AlterUniqueTogether(
            name='delegationforecast',
            unique_together={('delegation_name', 'governorate', 'forecast_origin', 'horizon_idx', 'property_type')},
        ),
    ]
