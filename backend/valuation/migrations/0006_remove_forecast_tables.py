"""
Remove DelegationForecast and DelegationPriceData from the valuation app.
These models have been moved to the dedicated `forecast` app.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valuation', '0005_fix_unique_constraints_for_ezzouhour'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='delegationforecast',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='delegationpricedata',
            unique_together=set(),
        ),
        migrations.DeleteModel(name='DelegationForecast'),
        migrations.DeleteModel(name='DelegationPriceData'),
    ]
