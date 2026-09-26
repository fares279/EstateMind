# Generated migration for simulator hardening requirements
# Adds fields to SimulationRun and creates AgentCalibrationProfile model

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.utils.timezone
from datetime import date


class Migration(migrations.Migration):

    dependencies = [
        ('simulation', '0002_alter_simulationrun_options'),  # Replace with actual previous migration
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add new fields to SimulationRun
        migrations.AddField(
            model_name='simulationrun',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='scenario_type',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='scenario_config',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='validation_result',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='n_runs',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='n_agents',
            field=models.IntegerField(default=500),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='seed_base',
            field=models.IntegerField(default=42),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='ensemble_output',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='stochastic_tests',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='reproducibility_passed',
            field=models.BooleanField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='variance_cv',
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='calibration_mape',
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='calibration_quality',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='rl_policy_test_results',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='celery_task_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        
        # Add indexes for new fields
        migrations.AddIndex(
            model_name='simulationrun',
            index=models.Index(fields=['user', 'status'], name='simulation_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='simulationrun',
            index=models.Index(fields=['scenario_type', 'completed_at'], name='simulation_scenario_completed_idx'),
        ),
        
        # Create AgentCalibrationProfile model
        migrations.CreateModel(
            name='AgentCalibrationProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('agent_type', models.CharField(
                    choices=[('buyer', 'Buyer Agent'), ('seller', 'Seller Agent'), 
                            ('developer', 'Developer Agent'), ('speculator', 'Speculator Agent')],
                    max_length=20
                )),
                ('calibration_date', models.DateField(default=date.today, db_index=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('reward_weights', models.JSONField()),
                ('directional_accuracy', models.FloatField()),
                ('mean_price_mape', models.FloatField()),
                ('calibration_quality', models.CharField(
                    choices=[('GOOD', 'Well-calibrated (Good)'), ('ACCEPTABLE', 'Acceptable'), 
                            ('POOR', 'Miscalibrated (Poor)')],
                    max_length=20
                )),
                ('training_transactions', models.IntegerField()),
                ('training_date_range_start', models.DateField()),
                ('training_date_range_end', models.DateField()),
                ('calibration_method', models.CharField(max_length=50)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Agent Calibration Profile',
                'verbose_name_plural': 'Agent Calibration Profiles',
                'ordering': ['-calibration_date', 'agent_type'],
            },
        ),
        
        # Indexes for AgentCalibrationProfile
        migrations.AddIndex(
            model_name='agentcalibrationprofile',
            index=models.Index(fields=['agent_type', 'is_active'], name='calib_agent_active_idx'),
        ),
        migrations.AddIndex(
            model_name='agentcalibrationprofile',
            index=models.Index(fields=['calibration_date', 'is_active'], name='calib_date_active_idx'),
        ),
        
        # Unique constraint
        migrations.AlterUniqueTogether(
            name='agentcalibrationprofile',
            unique_together={('agent_type', 'calibration_date')},
        ),
    ]
