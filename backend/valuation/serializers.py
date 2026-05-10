from rest_framework import serializers
from .models import ValuationRequest


class ValuationInputSerializer(serializers.Serializer):
    PROPERTY_TYPES  = ['apartment', 'house', 'commercial', 'land']
    TRANSACTION_TYPES = ['sale', 'rent']

    property_type    = serializers.ChoiceField(choices=PROPERTY_TYPES, default='apartment')
    transaction_type = serializers.ChoiceField(choices=TRANSACTION_TYPES, default='sale')
    governorate      = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    delegation       = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    city             = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    neighborhood     = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    size_m2          = serializers.FloatField(min_value=1, max_value=200_000, required=False, default=100)
    bedrooms         = serializers.IntegerField(min_value=0, max_value=50, required=False, allow_null=True)
    bathrooms        = serializers.IntegerField(min_value=0, max_value=20, required=False, allow_null=True)
    condition        = serializers.CharField(max_length=50, required=False, allow_blank=True, default='good')
    has_pool         = serializers.BooleanField(required=False, default=False)
    has_garden       = serializers.BooleanField(required=False, default=False)
    has_parking      = serializers.BooleanField(required=False, default=False)
    sea_view         = serializers.BooleanField(required=False, default=False)
    elevator         = serializers.BooleanField(required=False, default=False)
    description      = serializers.CharField(max_length=10_000, required=False, allow_blank=True, default='')
    image_count      = serializers.IntegerField(min_value=0, max_value=30, required=False, default=0)

    def validate_condition(self, value):
        return value.lower().replace('_', ' ').strip()


class ValuationHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ValuationRequest
        fields = [
            'id', 'property_type', 'transaction_type', 'governorate', 'city',
            'size_m2', 'bedrooms', 'estimated_price', 'lower_bound', 'upper_bound',
            'confidence', 'confidence_level', 'prediction_mode', 'created_at',
        ]
        read_only_fields = ['__all__']
