from django.db.models import Avg
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.models import Region, Delegation, Property, PriceTrend, ClimateRisk
from core.services.climate_intelligence import (
    fetch_live_weather,
    get_all_governorates_summary,
    compute_risk_score,
    compute_sustainability,
    climate_price_adjustment,
    GOVERNORATE_META,
    GOVERNORATE_RISK,
)
from features.services.market_analytics import DelegationAnalytics
from features.services.heatmap_generator import generate_price_heatmap, generate_demand_heatmap
from users.permissions import RequiresPro, RequiresInvestor, require_pro
from .serializers import (
    RegionSerializer, PropertySerializer,
    PriceTrendSerializer, ClimateRiskSerializer, ClimateRiskDetailSerializer,
    PropertyMapSerializer,
)


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    filterset_fields = ['governorate']


class PropertyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Property.objects.filter(is_active=True)
    serializer_class = PropertySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['region', 'property_type']
    search_fields = ['title', 'description']
    ordering_fields = ['price', 'created_at']


class PriceTrendViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Price trends and market analytics (requires Pro plan or higher).
    """
    queryset = PriceTrend.objects.all()
    serializer_class = PriceTrendSerializer
    filterset_fields = ['region', 'property_type']
    ordering_fields = ['date']
    permission_classes = [IsAuthenticated, RequiresPro]


class ClimateRiskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Climate Risk Intelligence — publicly readable.
    List:   GET /api/climate/                → all 24 governorates (compact)
    Detail: GET /api/climate/<pk>/           → full record
    Extra actions (see below):
      GET /api/climate/<pk>/weather/         → live weather + risk indices
      GET /api/climate/dashboard/            → all-cities summary (static)
      GET /api/climate/compare/             → compare ?cities=Tunis,Sousse
      GET /api/climate/scenarios/           → +2°C / +4°C projections
      GET /api/climate/regional_heatmap/    → regional aggregation
    """
    queryset = ClimateRisk.objects.select_related('region').all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ClimateRiskDetailSerializer
        return ClimateRiskSerializer

    @action(detail=True, methods=['get'], url_path='weather')
    def weather(self, request, pk=None):
        """Live weather + heat/flood/drought indices from Open-Meteo."""
        obj = self.get_object()
        gov = obj.region.governorate
        data = fetch_live_weather(gov)
        if data is None:
            return Response({'error': f'Weather data unavailable for {gov}'}, status=503)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """
        All-governorates risk summary table — static risk data, no API calls.
        Sorted by combined_risk_score ascending (safest first).
        """
        summary = get_all_governorates_summary()
        # Enrich with DB values for livability/infrastructure
        db_map = {
            cr.region.governorate: cr
            for cr in ClimateRisk.objects.select_related('region').all()
        }
        for row in summary:
            db = db_map.get(row['governorate'])
            if db:
                row['livability_score']      = db.livability_score
                row['infrastructure_score']  = db.infrastructure_score
                row['avg_temp_c']            = db.avg_temp_c
                row['avg_rainfall_mm']       = db.avg_rainfall_mm
                row['days_above_35c']        = db.days_above_35c
                row['sea_level_exposure']    = db.sea_level_exposure
                row['scenario_baseline']     = db.scenario_baseline
                row['scenario_2c']           = db.scenario_2c
                row['scenario_4c']           = db.scenario_4c
        return Response({'count': len(summary), 'results': summary})

    @action(detail=False, methods=['get'], url_path='compare')
    def compare(self, request):
        """
        Side-by-side comparison.
        ?cities=Tunis,Sousse,Sfax  (comma-separated governorate names)
        """
        raw = request.query_params.get('cities', '')
        names = [n.strip() for n in raw.split(',') if n.strip()]
        if not names:
            return Response({'error': 'Provide ?cities=Gov1,Gov2,...'}, status=400)

        db_map = {
            cr.region.governorate: cr
            for cr in ClimateRisk.objects.select_related('region').filter(
                region__governorate__in=names
            )
        }
        results = []
        for gov in names:
            score, category = compute_risk_score(gov)
            sustain, grade  = compute_sustainability(gov)
            adj, label      = climate_price_adjustment(gov)
            meta            = GOVERNORATE_META.get(gov, {})
            db              = db_map.get(gov)
            results.append({
                'governorate':          gov,
                'climate_region':       meta.get('region'),
                'is_coastal':           meta.get('coastal', False),
                'combined_risk_score':  db.combined_risk_score if db else score,
                'risk_category':        db.risk_category if db else category,
                'sustainability_score': db.sustainability_score if db else sustain,
                'sustainability_grade': db.sustainability_grade if db else grade,
                'flood_risk':           db.flood_risk if db else GOVERNORATE_RISK.get(gov, {}).get('flood', '—'),
                'heat_stress_risk':     db.heat_stress_risk if db else GOVERNORATE_RISK.get(gov, {}).get('heat', '—'),
                'drought_risk':         db.drought_risk if db else GOVERNORATE_RISK.get(gov, {}).get('drought', '—'),
                'earthquake_risk':      db.earthquake_risk if db else GOVERNORATE_RISK.get(gov, {}).get('earthquake', '—'),
                'price_adjustment_pct': db.price_adjustment_pct if db else adj,
                'price_adjustment_label': label,
                'livability_score':     db.livability_score if db else None,
                'scenario_baseline':    db.scenario_baseline if db else None,
                'scenario_2c':          db.scenario_2c if db else None,
                'scenario_4c':          db.scenario_4c if db else None,
            })
        return Response({'count': len(results), 'results': results})

    @action(detail=False, methods=['get'], url_path='scenarios')
    def scenarios(self, request):
        """Climate scenario projections for all governorates (Baseline / +2°C / +4°C)."""
        qs = ClimateRisk.objects.select_related('region').exclude(
            scenario_baseline=None,
        ).values(
            'region__governorate', 'risk_category', 'climate_region',
            'scenario_baseline', 'scenario_2c', 'scenario_4c',
            'sustainability_score', 'combined_risk_score',
        )
        results = [
            {
                'governorate':       r['region__governorate'],
                'climate_region':    r['climate_region'],
                'risk_category':     r['risk_category'],
                'baseline':          r['scenario_baseline'],
                'plus_2c':           r['scenario_2c'],
                'plus_4c':           r['scenario_4c'],
                'delta_2c':          round((r['scenario_2c'] or 0) - (r['scenario_baseline'] or 0), 2),
                'delta_4c':          round((r['scenario_4c'] or 0) - (r['scenario_baseline'] or 0), 2),
                'current_sustainability': r['sustainability_score'],
            }
            for r in qs
        ]
        results.sort(key=lambda x: x.get('delta_4c', 0))
        return Response({'count': len(results), 'results': results})

    @action(detail=False, methods=['get'], url_path='regional_heatmap')
    def regional_heatmap(self, request):
        """
        Aggregate climate risk data grouped by climate region
        (North / Center / South / etc.) for map heatmap overlays.
        """
        from django.db.models import Avg as DAvg, Count
        qs = (
            ClimateRisk.objects
            .exclude(climate_region='')
            .values('climate_region')
            .annotate(
                count=Count('id'),
                avg_risk=DAvg('combined_risk_score'),
                avg_sustain=DAvg('sustainability_score'),
                avg_adjustment=DAvg('price_adjustment_pct'),
            )
        )
        return Response({
            'regions': [
                {
                    'climate_region':      r['climate_region'],
                    'governorate_count':   r['count'],
                    'avg_risk_score':      round(r['avg_risk'] or 0, 2),
                    'avg_sustainability':  round(r['avg_sustain'] or 0, 1),
                    'avg_price_adjustment_pct': round(r['avg_adjustment'] or 0, 2),
                }
                for r in qs
            ]
        })


class MapViewSet(viewsets.ViewSet):
    """Endpoints backing the Interactive Intelligent Map."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='summary', permission_classes=[IsAuthenticated, RequiresPro])
    def summary(self, request):
        summary_payload = DelegationAnalytics.get_all_delegations_summary()
        return Response(summary_payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='delegations', permission_classes=[IsAuthenticated, RequiresPro])
    def delegations(self, request):
        governorate = (request.query_params.get('governorate') or '').strip()

        queryset = Delegation.objects.select_related('region').all()
        if governorate:
            queryset = queryset.filter(region__governorate__iexact=governorate)

        payload = [DelegationAnalytics.get_delegation_kpis(delegation.id) for delegation in queryset]
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='listings', permission_classes=[AllowAny])
    def listings(self, request):
        delegation_name = (request.query_params.get('delegation') or '').strip()
        governorate = (request.query_params.get('governorate') or '').strip()
        property_type = (request.query_params.get('property_type') or '').strip()
        min_price = request.query_params.get('price_min')
        max_price = request.query_params.get('price_max')

        queryset = Property.objects.filter(is_active=True).select_related('region', 'delegation')

        if delegation_name:
            queryset = queryset.filter(delegation__name__iexact=delegation_name)
        if governorate:
            queryset = queryset.filter(region__governorate__iexact=governorate)
        if property_type:
            queryset = queryset.filter(property_type__iexact=property_type)
        if min_price not in (None, ''):
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass
        if max_price not in (None, ''):
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass

        # Deduplicate: keep only one record per (title, price, area_sqm) combination.
        # This prevents synthetic/imported records with identical content from appearing twice.
        from django.db.models import Min
        unique_ids = (
            queryset
            .values('title', 'price', 'area_sqm')
            .annotate(keep_id=Min('id'))
            .values_list('keep_id', flat=True)
        )
        queryset = Property.objects.filter(id__in=unique_ids).select_related('region', 'delegation')

        # Re-apply ordering so results are consistent
        queryset = queryset.order_by('id')

        serialized = PropertyMapSerializer(queryset, many=True)
        return Response(
            {
                'total_count': queryset.count(),
                'results': serialized.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['get'], url_path='heat/price', permission_classes=[IsAuthenticated, RequiresPro])
    def heat_price(self, request):
        payload = generate_price_heatmap()
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='heat/demand', permission_classes=[IsAuthenticated, RequiresPro])
    def heat_demand(self, request):
        payload = generate_demand_heatmap()
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='opportunities', permission_classes=[IsAuthenticated, RequiresPro])
    def opportunities(self, request):
        min_score = request.query_params.get('min_score', '0')
        try:
            min_score = float(min_score)
        except ValueError:
            min_score = 0.0

        payload = []
        for delegation in Delegation.objects.select_related('region').all():
            kpis = DelegationAnalytics.get_delegation_kpis(delegation.id)
            if kpis.get('opportunity_score', 0.0) >= min_score:
                centroid_lat = delegation.centroid_lat
                centroid_lon = delegation.centroid_lon

                if centroid_lat is None or centroid_lon is None:
                    prop_centroid = Property.objects.filter(
                        delegation=delegation,
                        is_active=True,
                    ).aggregate(avg_lat=Avg('latitude'), avg_lon=Avg('longitude'))
                    centroid_lat = prop_centroid.get('avg_lat')
                    centroid_lon = prop_centroid.get('avg_lon')

                if (centroid_lat is None or centroid_lon is None) and delegation.region:
                    centroid_lat = delegation.region.latitude
                    centroid_lon = delegation.region.longitude

                kpis['centroid_lat'] = centroid_lat
                kpis['centroid_lon'] = centroid_lon
                payload.append(kpis)

        payload.sort(key=lambda row: row.get('opportunity_score', 0.0), reverse=True)
        return Response(payload, status=status.HTTP_200_OK)


@api_view(['GET'])
def climate_weather_by_name(request, governorate: str):
    """
    GET /api/climate/weather/<governorate>/
    Live weather + heat/flood/drought indices for a governorate by name.
    Public endpoint — no authentication required.
    """
    data = fetch_live_weather(governorate)
    if data is None:
        return Response(
            {'error': f'Governorate "{governorate}" not found or weather unavailable.'},
            status=404,
        )
    return Response(data)


@api_view(['GET'])
@require_pro
def market_stats(request):
    """Global market statistics dashboard (requires Pro plan)"""
    return Response({
        'total_properties': Property.objects.filter(is_active=True).count(),
        'regions_covered': Region.objects.count(),
        'avg_price': Property.objects.filter(is_active=True).aggregate(avg=Avg('price'))['avg'],
    })
