from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_snapshot_listing_provenance'),
    ]

    operations = [
        migrations.AddField(model_name='property', name='price_imputed', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='property', name='area_imputed', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='property', name='rooms_imputed', field=models.BooleanField(default=False)),
    ]
