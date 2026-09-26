"""
Serializers for simulation models.
Used for JSON serialization in REST API endpoints.
"""

from rest_framework import serializers
from .models import SimulationRun, AgentCalibrationProfile


class SimulationJobSerializer(serializers.ModelSerializer):
    """
    Serializes basic simulation job info (for list/history views).
    """
    
    job_id = serializers.CharField(source='run_id', read_only=True)
    
    class Meta:
        model = SimulationRun
        fields = [
            'job_id',
            'scenario_type',
            'status',
            'n_runs',
            'n_agents',
            'created_at',
            'started_at',
            'completed_at',
        ]
        read_only_fields = fields


class SimulationRunSerializer(serializers.ModelSerializer):
    """
    Full serializer for simulation runs.
    """
    
    job_id = serializers.CharField(source='run_id', read_only=True)
    
    class Meta:
        model = SimulationRun
        fields = [
            'job_id',
            'user',
            'scenario_type',
            'scenario_config',
            'status',
            'n_runs',
            'n_agents',
            'seed_base',
            'validation_result',
            'ensemble_output',
            'stochastic_tests',
            'reproducibility_passed',
            'variance_cv',
            'calibration_mape',
            'calibration_quality',
            'rl_policy_test_results',
            'created_at',
            'started_at',
            'completed_at',
            'updated_at',
        ]
        read_only_fields = [
            'job_id', 'user', 'status', 'validation_result',
            'ensemble_output', 'stochastic_tests',
            'reproducibility_passed', 'variance_cv', 'calibration_mape',
            'calibration_quality', 'rl_policy_test_results',
            'created_at', 'started_at', 'completed_at', 'updated_at',
        ]


class SimulationResultsSerializer(serializers.Serializer):
    """
    Serializes simulation results for API output.
    """
    
    job_id = serializers.CharField()
    completed_at = serializers.DateTimeField()
    ensemble_output = serializers.JSONField()
    stochastic_tests = serializers.JSONField()
    rl_policy_test_results = serializers.JSONField(required=False, allow_null=True)
    calibration_quality = serializers.CharField(required=False, allow_null=True)


class AgentCalibrationProfileSerializer(serializers.ModelSerializer):
    """
    Serializes agent calibration profiles.
    """
    
    class Meta:
        model = AgentCalibrationProfile
        fields = [
            'id',
            'agent_type',
            'calibration_date',
            'is_active',
            'reward_weights',
            'directional_accuracy',
            'mean_price_mape',
            'calibration_quality',
            'training_transactions',
            'training_date_range_start',
            'training_date_range_end',
            'calibration_method',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at'
        ]
