/**
 * Pipeline Health & Metrics Dashboard Component
 * 
 * Visualizes the 3-stage scraper-agent architecture:
 * - Bronze: Data collection and scraper health
 * - Silver: Normalization, deduplication, validation
 * - Gold: Market intelligence aggregation
 * 
 * Shows KPIs, alerts, and recommendations for data quality
 */

import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  AlertCircle,
  TrendingUp,
  Database,
  Zap,
  Clock,
  BarChart3,
} from 'lucide-react';
import api from '../../../services/api';

const PipelineHealthDashboard = () => {
  const [healthData, setHealthData] = useState(null);
  const [qualityData, setQualityData] = useState(null);
  const [scraperHealth, setScraperHealth] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDashboardData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchDashboardData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [healthRes, qualityRes, scraperRes, incidentRes] = await Promise.all([
        api.get('/scraper/health/dashboard/'),
        api.get('/scraper/health/data-quality/'),
        api.get('/scraper/health/scraper-agents/'),
        api.get('/scraper/health/incidents/'),
      ]);

      setHealthData(healthRes.data);
      setQualityData(qualityRes.data);
      setScraperHealth(scraperRes.data || []);
      setIncidents(incidentRes.data?.incidents || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard data');
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-lg">
        <AlertTriangle className="inline mr-2 text-red-600" />
        <span className="text-red-800">Error: {error}</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Pipeline Health Dashboard</h1>
        <button
          onClick={fetchDashboardData}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Refresh Now
        </button>
      </div>

      {/* Overall Pipeline Health */}
      {healthData && (
        <PipelineOverviewCard healthData={healthData} />
      )}

      {/* Incidents Alert */}
      {incidents.length > 0 && (
        <IncidentCard incidents={incidents} />
      )}

      {/* Three-Stage Pipeline Metrics */}
      <div className="grid grid-cols-3 gap-6">
        {healthData?.bronze_status && (
          <StageCard
            stage="bronze"
            title="Bronze: Data Collection"
            data={healthData.bronze_status}
            icon={<Database className="w-6 h-6 text-orange-500" />}
          />
        )}
        {healthData?.silver_status && (
          <StageCard
            stage="silver"
            title="Silver: Normalization"
            data={healthData.silver_status}
            icon={<Zap className="w-6 h-6 text-yellow-500" />}
          />
        )}
        {healthData?.gold_status && (
          <StageCard
            stage="gold"
            title="Gold: Market Intelligence"
            data={healthData.gold_status}
            icon={<TrendingUp className="w-6 h-6 text-green-500" />}
          />
        )}
      </div>

      {/* Data Quality Report */}
      {qualityData && (
        <DataQualitySection qualityData={qualityData} />
      )}

      {/* Scraper Health */}
      <ScraperHealthSection scraperHealth={scraperHealth} />

      {/* Recommendations */}
      {qualityData?.recommendations && qualityData.recommendations.length > 0 && (
        <RecommendationsCard recommendations={qualityData.recommendations} />
      )}
    </div>
  );
};

// ============================================================================
// Subcomponents
// ============================================================================

const PipelineOverviewCard = ({ healthData }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-50 border-green-200';
      case 'degraded':
        return 'bg-yellow-50 border-yellow-200';
      case 'unhealthy':
        return 'bg-red-50 border-red-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-8 h-8 text-green-500" />;
      case 'degraded':
        return <AlertCircle className="w-8 h-8 text-yellow-500" />;
      case 'unhealthy':
        return <AlertTriangle className="w-8 h-8 text-red-500" />;
      default:
        return null;
    }
  };

  return (
    <div className={`p-6 border-l-4 rounded-lg ${getStatusColor(healthData.pipeline_status)}`}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold mb-2">Overall Pipeline Status</h2>
          <div className="flex items-center space-x-4">
            {getStatusIcon(healthData.pipeline_status)}
            <div>
              <p className="text-sm text-gray-600">Health Score</p>
              <p className="text-2xl font-bold">
                {healthData.overall_health_score.toFixed(1)}/100
              </p>
            </div>
            <div className="ml-8">
              <p className="text-sm text-gray-600">Status</p>
              <p className="text-lg font-semibold capitalize">{healthData.pipeline_status}</p>
            </div>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-600">Last Complete Run</p>
          <p className="text-sm">
            {healthData.last_complete_run
              ? new Date(healthData.last_complete_run).toLocaleString()
              : 'Never'}
          </p>
        </div>
      </div>
      {healthData.alerts.length > 0 && (
        <div className="mt-4 space-y-2">
          {healthData.alerts.map((alert, idx) => (
            <div key={idx} className="text-sm text-gray-700">
              <AlertCircle className="w-4 h-4 inline mr-2" />
              {alert}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const IncidentCard = ({ incidents }) => {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-6">
      <div className="flex items-center mb-4">
        <AlertTriangle className="w-6 h-6 text-red-600 mr-3" />
        <h3 className="text-lg font-semibold text-red-900">
          Active Incidents ({incidents.length})
        </h3>
      </div>
      <div className="space-y-3">
        {incidents.map((incident, idx) => (
          <div key={idx} className="bg-white p-3 rounded border border-red-100">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-gray-900">{incident.message}</p>
                <p className="text-sm text-gray-500 mt-1">
                  Source: {incident.source} · Type: {incident.type}
                </p>
              </div>
              <span className={`px-2 py-1 text-xs font-semibold rounded ${
                incident.severity === 'high' ? 'bg-red-100 text-red-800' :
                incident.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                'bg-blue-100 text-blue-800'
              }`}>
                {incident.severity.toUpperCase()}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const StageCard = ({ stage, title, data, icon }) => {
  const MetricItem = ({ label, value, unit = '' }) => (
    <div className="mb-3">
      <p className="text-xs text-gray-600">{label}</p>
      <p className="text-lg font-semibold">
        {typeof value === 'number' ? value.toFixed(1) : value}{unit}
      </p>
    </div>
  );

  return (
    <div className="bg-white rounded-lg shadow p-6 border-l-4 border-opacity-50"
         style={{
           borderLeftColor: stage === 'bronze' ? '#f97316' :
                           stage === 'silver' ? '#eab308' :
                           '#22c55e'
         }}>
      <div className="flex items-center justify-between mb-4">
        {icon}
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>

      {stage === 'bronze' && (
        <>
          <MetricItem label="URLs Discovered" value={data.total_urls_discovered} />
          <MetricItem label="Records Scraped" value={data.total_records_scraped} />
          <MetricItem label="Success Rate" value={data.overall_success_rate_pct} unit="%" />
          <MetricItem label="Active Scrapers" value={data.scraper_count} />
        </>
      )}

      {stage === 'silver' && (
        <>
          <MetricItem label="Records Received" value={data.records_received} />
          <MetricItem label="Normalized" value={data.records_normalized} />
          <MetricItem label="Pass Rate" value={data.pass_rate_pct} unit="%" />
          <MetricItem label="Duplicates Found" value={data.records_duplicates_found} />
          <MetricItem label="Unique Properties" value={data.unified_property_ids_assigned} />
        </>
      )}

      {stage === 'gold' && (
        <>
          <MetricItem label="Records Processed" value={data.records_processed} />
          <MetricItem label="Delegations Analyzed" value={data.delegations_analyzed} />
          <MetricItem label="Governorates" value={data.governorates_analyzed} />
          <p className="text-xs text-gray-500 mt-4">Snapshot: {data.snapshot_version}</p>
        </>
      )}
    </div>
  );
};

const DataQualitySection = ({ qualityData }) => {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-6 flex items-center">
        <BarChart3 className="w-5 h-5 mr-2 text-blue-500" />
        Data Quality Metrics
      </h3>

      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Geocoding Quality */}
        <div>
          <h4 className="font-medium text-gray-900 mb-3">Geocoding Accuracy</h4>
          <div className="space-y-2">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm text-gray-600">Polygon-Level</span>
                <span className="text-sm font-semibold">
                  {qualityData.geocoding_quality.polygon_level_pct.toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-green-500 h-2 rounded-full"
                  style={{width: `${qualityData.geocoding_quality.polygon_level_pct}%`}}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm text-gray-600">Centroid-Level</span>
                <span className="text-sm font-semibold">
                  {qualityData.geocoding_quality.centroid_level_pct.toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-yellow-500 h-2 rounded-full"
                  style={{width: `${qualityData.geocoding_quality.centroid_level_pct}%`}}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm text-gray-600">Missing</span>
                <span className="text-sm font-semibold">
                  {qualityData.geocoding_quality.missing_pct.toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-red-500 h-2 rounded-full"
                  style={{width: `${qualityData.geocoding_quality.missing_pct}%`}}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Schema Validation */}
        <div>
          <h4 className="font-medium text-gray-900 mb-3">Validation & Deduplication</h4>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm text-gray-600">Schema Pass Rate</span>
                <span className="text-sm font-semibold">
                  {qualityData.schema_validation_pass_rate.toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full"
                  style={{width: `${qualityData.schema_validation_pass_rate}%`}}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm text-gray-600">Duplicate Rate</span>
                <span className="text-sm font-semibold">
                  {qualityData.duplicate_rate_pct.toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-purple-500 h-2 rounded-full"
                  style={{width: `${Math.min(qualityData.duplicate_rate_pct, 100)}%`}}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Data Drift */}
      <div className="bg-gray-50 p-4 rounded">
        <h4 className="font-medium text-gray-900 mb-3 flex items-center">
          <TrendingUp className="w-4 h-4 mr-2" />
          Data Drift Detection (PSI Monitoring)
        </h4>
        {qualityData.data_drift_detected && (
          <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mb-3">
            <p className="text-sm text-yellow-800 font-medium">
              ⚠️ Data drift detected! Downstream models may need attention.
            </p>
          </div>
        )}
        <div className="space-y-2 text-sm">
          {Object.entries(qualityData.psi_metrics).map(([feature, psi]) => (
            <div key={feature} className="flex justify-between">
              <span className="text-gray-600">{feature}:</span>
              <span className={`font-semibold ${psi > 0.10 ? 'text-red-600' : 'text-green-600'}`}>
                {psi.toFixed(4)} {psi > 0.10 && '⚠️'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const ScraperHealthSection = ({ scraperHealth }) => {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-6 flex items-center">
        <Zap className="w-5 h-5 mr-2 text-blue-500" />
        Scraper Agent Health
      </h3>

      <div className="space-y-4">
        {scraperHealth.map((scraper) => (
          <div key={scraper.scraper_name} className="border rounded-lg p-4">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h4 className="font-semibold text-gray-900">{scraper.scraper_name}</h4>
                <p className="text-sm text-gray-500">{scraper.source_name}</p>
              </div>
              <div className="text-right">
                <div className="inline-block px-3 py-1 rounded-full text-sm font-semibold"
                     style={{
                       backgroundColor: scraper.status === 'healthy' ? '#dcfce7' :
                                      scraper.status === 'degraded' ? '#fef3c7' :
                                      '#fee2e2',
                       color: scraper.status === 'healthy' ? '#166534' :
                              scraper.status === 'degraded' ? '#92400e' :
                              '#991b1b'
                     }}>
                  {scraper.health_score.toFixed(1)}/100
                </div>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4 mb-3 text-sm">
              <div>
                <p className="text-gray-600">Success Rate</p>
                <p className="font-semibold">{scraper.success_rate_pct.toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-gray-600">Data Age</p>
                <p className="font-semibold">{scraper.avg_data_age_hours.toFixed(1)}h</p>
              </div>
              <div>
                <p className="text-gray-600">Field Coverage</p>
                <p className="font-semibold">{scraper.field_coverage_pct.toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-gray-600">Last Run</p>
                <p className="font-semibold text-xs">
                  {scraper.last_execution
                    ? new Date(scraper.last_execution).toLocaleTimeString()
                    : 'Never'}
                </p>
              </div>
            </div>

            {scraper.alerts.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded p-2">
                {scraper.alerts.map((alert, idx) => (
                  <p key={idx} className="text-xs text-yellow-800">⚠️ {alert}</p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const RecommendationsCard = ({ recommendations }) => {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-blue-900 mb-4 flex items-center">
        <AlertCircle className="w-5 h-5 mr-2" />
        Recommendations
      </h3>
      <ul className="space-y-3">
        {recommendations.map((rec, idx) => (
          <li key={idx} className="text-sm text-blue-800 flex items-start">
            <span className="mr-3">→</span>
            <span>{rec}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default PipelineHealthDashboard;
