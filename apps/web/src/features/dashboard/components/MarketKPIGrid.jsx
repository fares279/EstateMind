/**
 * KPI Dashboard - Fresh KPI Cards
 * Shows KPI values with freshness and anomaly detection
 */

import React, { useState, useEffect } from 'react';
import { getKpiFreshness } from '../../../services/api-modules';
import { FreshnessPill, TrendBadge, AnomalyAlert, SkeletonLoader, ErrorFallback } from '../../../components/shared/CommonComponents';

const humanizeKpiName = (name) =>
  String(name || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (ch) => ch.toUpperCase());

const normalizeKpis = (payload) => {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (Array.isArray(payload?.kpis)) {
    return payload.kpis;
  }

  if (payload && typeof payload === 'object') {
    return Object.entries(payload)
      .filter(([, value]) => value && typeof value === 'object')
      .map(([kpiName, meta]) => ({
        label: humanizeKpiName(kpiName),
        value: Number(meta.row_count ?? 0),
        unit: 'listings',  // Changed from 'rows' to show active property listings
        trend_pct: 0,
        freshness_status: meta.status || 'UNKNOWN',
        last_updated: meta.computed_at,
        is_anomaly: false,
        anomaly_message: meta.notes || '',
      }));
  }

  return [];
};

export const FreshKPICard = ({ kpi }) => {
  const { label, value, unit, trend_pct, freshness_status, last_updated, is_anomaly, anomaly_message } = kpi;

  const isStale = freshness_status === 'STALE' || freshness_status === 'CRITICAL';

  return (
    <div
      className={`bg-gray-750 border rounded-lg p-4 transition-all ${
        isStale ? 'opacity-60 border-amber-600/70' : 'border-gray-700'
      } ${is_anomaly ? 'border-red-700' : ''}`}
      title={isStale ? 'Data is stale and may not reflect current market conditions' : ''}
    >
      {is_anomaly && <AnomalyAlert message={anomaly_message || 'Anomaly detected'} severity="warning" />}
      
      {isStale && !is_anomaly && (
        <div className="mb-2 text-xs text-amber-500 flex items-center gap-1">
          <span>⚠</span>
          <span>Stale data</span>
        </div>
      )}

      <div className="flex justify-between items-start mb-2">
        <div className="text-sm text-gray-400">{label}</div>
        <FreshnessPill status={freshness_status} timestamp={last_updated} />
      </div>

      <div className="text-3xl font-bold text-white mb-2">
        {value.toLocaleString()} <span className="text-sm text-gray-500">{unit}</span>
      </div>

      <div>
        <TrendBadge change={trend_pct} label="vs last month" />
      </div>
    </div>
  );
};

export const KPIGrid = ({ refresh = true }) => {
  const [kpis, setKpis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadKPIs = async () => {
    try {
      setLoading(true);
      const response = await getKpiFreshness();
      const payload = response?.data ?? response;
      setKpis(normalizeKpis(payload));
      setError(null);
    } catch (err) {
      // Distinguish 401 (authentication) errors from other errors
      const is401 = err?.response?.status === 401 || err?.status === 401;
      const errorObj = is401 
        ? { ...err, type: 'AUTH_ERROR', message: 'Authentication expired. Please log in again.' }
        : err instanceof Error ? err : new Error('Failed to load KPIs');
      setError(errorObj);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKPIs();
    if (refresh) {
      const interval = setInterval(loadKPIs, 5 * 60 * 1000); // 5 minutes
      return () => clearInterval(interval);
    }
  }, [refresh]);

  if (error) return <ErrorFallback error={error} retry={loadKPIs} />;
  if (loading)
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonLoader key={i} variant="card" lines={3} />
        ))}
      </div>
    );

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {kpis.map((kpi, i) => (
        <FreshKPICard key={i} kpi={kpi} />
      ))}
    </div>
  );
};

export default FreshKPICard;
