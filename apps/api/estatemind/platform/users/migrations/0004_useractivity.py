from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_user_managers_user_otp_user_otp_attempts_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_type', models.CharField(choices=[('valuation', 'Valuation'), ('analysis', 'Analysis'), ('simulation', 'Simulation'), ('legal', 'Legal Session'), ('explore', 'Explore'), ('save_property', 'Save Property')], max_length=30)),
                ('feature', models.CharField(max_length=50)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='useractivity',
            index=models.Index(fields=['user', 'activity_type'], name='users_userac_user_id_49d74d_idx'),
        ),
        migrations.AddIndex(
            model_name='useractivity',
            index=models.Index(fields=['created_at'], name='users_userac_created_d8fb39_idx'),
        ),
    ]
