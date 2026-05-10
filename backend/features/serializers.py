from rest_framework import serializers
from core.models import Region, Delegation, Property, Valuation, PriceTrend, ClimateRisk


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = '__all__'


class PropertySerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source='region.governorate', read_only=True)

    class Meta:
        model = Property
        fields = ['id', 'title', 'property_type', 'price', 'area_sqm', 'region', 'region_name', 'created_at']


class ValuationSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title', read_only=True)

    class Meta:
        model = Valuation
        fields = ['id', 'property', 'property_title', 'predicted_price', 'mape_confidence']


class PriceTrendSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceTrend
        fields = '__all__'


class ClimateRiskSerializer(serializers.ModelSerializer):
    """Compact serializer — list view and map overlay."""
    governorate = serializers.CharField(source='region.governorate', read_only=True)
    region_lat  = serializers.FloatField(source='region.latitude',  read_only=True, default=None)
    region_lon  = serializers.FloatField(source='region.longitude', read_only=True, default=None)

    class Meta:
        model = ClimateRisk
        fields = [
            'id', 'governorate',
            'flood_risk', 'heat_stress_risk', 'drought_risk', 'earthquake_risk',
            'risk_category', 'combined_risk_score',
            'sustainability_score', 'sustainability_grade',
            'livability_score', 'infrastructure_score',
            'is_coastal', 'climate_region', 'lat', 'lon', 'region_lat', 'region_lon',
            'avg_temp_c', 'avg_rainfall_mm', 'days_above_35c',
            'price_adjustment_pct',
            'scenario_baseline', 'scenario_2c', 'scenario_4c',
        ]


class ClimateRiskDetailSerializer(serializers.ModelSerializer):
    """Full serializer — detail / dashboard view."""
    governorate   = serializers.CharField(source='region.governorate', read_only=True)
    region_lat    = serializers.FloatField(source='region.latitude', read_only=True)
    region_lon    = serializers.FloatField(source='region.longitude', read_only=True)

    class Meta:
        model = ClimateRisk
        fields = '__all__'
        extra_fields = ['governorate', 'region_lat', 'region_lon']


class DelegationKPISerializer(serializers.Serializer):
    delegation_id = serializers.IntegerField()
    delegation_name = serializers.CharField()
    governorate = serializers.CharField()
    listing_count = serializers.IntegerField()
    sale_count = serializers.IntegerField()
    rental_count = serializers.IntegerField()
    avg_price_tnd = serializers.FloatField()
    median_price_per_m2 = serializers.FloatField()
    avg_monthly_rental = serializers.FloatField()
    supply_pressure = serializers.FloatField()
    rent_ratio = serializers.FloatField()
    opportunity_score = serializers.FloatField()
    property_type_distribution = serializers.DictField(child=serializers.FloatField())


class MapSummarySerializer(serializers.Serializer):
    total_listings = serializers.IntegerField()
    total_delegations = serializers.IntegerField()
    avg_price_national = serializers.FloatField()
    delegations_kpis = DelegationKPISerializer(many=True)


class PropertyMapSerializer(serializers.ModelSerializer):
    governorate = serializers.CharField(source='region.governorate', read_only=True)
    delegation_name = serializers.CharField(source='delegation.name', read_only=True)
    delegation_centroid_lat = serializers.FloatField(source='delegation.centroid_lat', read_only=True, default=None)
    delegation_centroid_lon = serializers.FloatField(source='delegation.centroid_lon', read_only=True, default=None)
    region_lat = serializers.FloatField(source='region.latitude', read_only=True, default=None)
    region_lon = serializers.FloatField(source='region.longitude', read_only=True, default=None)

    class Meta:
        model = Property
        fields = [
            'id',
            'external_id',
            'title',
            'price',
            'property_type',
            'area_sqm',
            'bedrooms',
            'bathrooms',
            'latitude',
            'longitude',
            'source',
            'region',
            'delegation',
            'governorate',
            'delegation_name',
            'delegation_centroid_lat',
            'delegation_centroid_lon',
            'region_lat',
            'region_lon',
            'created_at',
        ]


class DelegationListSerializer(serializers.ModelSerializer):
    governorate = serializers.CharField(source='region.governorate', read_only=True)

    class Meta:
        model = Delegation
        fields = [
            'id',
            'name',
            'governorate',
            'population',
            'centroid_lat',
            'centroid_lon',
            'geojson_polygon',
        ]
