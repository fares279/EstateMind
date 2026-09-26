from rest_framework import serializers
from .models import Participant


class ParticipantSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = Participant
        fields = ['id', 'full_name', 'email', 'phone', 'region', 'role', 'role_display', 'motivation', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at', 'role_display']
        extra_kwargs = {
            'is_active': {'default': True}
        }

    def validate_email(self, value):
        if Participant.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("A participant with this email already exists.")
        return value.lower()

    def validate_motivation(self, value):
        if len(value.strip()) < 20:
            raise serializers.ValidationError("Please tell us more about your motivation (at least 20 characters).")
        return value
