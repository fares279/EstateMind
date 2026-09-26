/**
 * Climate Intelligence
 * ClimateRiskPanel - Multi-factor climate risk scoring
 */

import React, { useEffect, useState } from 'react';
import { getClimateRisk } from '../../../services/api-modules';
import { FreshnessPill, SkeletonLoader, ErrorFallback } from '../../../components/shared/CommonComponents';

const FACTOR_CONFIG = [
  { key: 'flood_risk_score', label: 'Flood risk', weight: 0.3 },
  { key: 'heat_stress_score', label: 'Heat stress', weight: 0.25 },
  { key: 'coastal_erosion_score', label: 'Coastal erosion', weight: 0.2 },
  { key: 'infrastructure_resilience_score', label: 'Infrastructure', weight: 0.15, mitigating: true },
  { key: 'wildfire_risk_score', label: 'Wildfire risk', weight: 0.1 },
];

export const ClimateRiskPanel = ({ lat, lon, delegation }) => {
  const [climate, setClimate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadClimateRisk = async () => {
    try {
      setLoading(true);
      const data = await getClimateRisk(lat, lon, delegation);
      setClimate(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load climate risk'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!lat && !lon && !delegation) return;
    loadClimateRisk();
  }, [lat, lon, delegation]);

  if (!lat && !lon && !delegation) return null;
  if (error) return <ErrorFallback error={error} retry={loadClimateRisk} />;
  if (loading) return <SkeletonLoader variant="card" />;
  if (!climate) return null;

  const riskColor = {
    VERY_LOW: 'text-green-400',
    LOW: 'text-green-400',
    MODERATE: 'text-yellow-400',
    MODERATE_HIGH: 'text-orange-400',
    HIGH: 'text-red-400',
    VERY_HIGH: 'text-red-500',
  }[climate.risk_label];

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <div className="text-sm text-gray-400 mb-1">Climate Risk Assessment</div>
          <div className="text-xs text-gray-500">
            {climate.method === 'kriging_rbf_thin_plate_spline'
              ? `Kriging (point-level) · ${climate.surface_coverage_pct}% coverage`
              : 'Delegation average'}
          </div>
        </div>
        <FreshnessPill status={climate.freshness_status} timestamp={climate.computed_at} />
      </div>

      <div className="flex items-baseline gap-3 mb-2">
        <span className={`text-3xl font-bold ${riskColor}`}>
          {climate.risk_label.replace(/_/g, ' ')}
        </span>
        <span className="text-xl text-white">{(climate.composite_score * 10).toFixed(1)}/10</span>
      </div>

      <div className="text-sm text-gray-400 mb-5">
        95% CI: [{(climate.ci_lower_95 * 10).toFixed(1)}, {(climate.ci_upper_95 * 10).toFixed(1)}]
      </div>

      <div className="space-y-3">
        {FACTOR_CONFIG.map(({ key, label, weight, mitigating }) => {
          const score = climate.factors[key] ?? 0;
          const contribution = score * weight;
          const barWidth = Math.round(score * 100);
          const barColor = mitigating
            ? 'bg-blue-500'
            : score < 0.3
              ? 'bg-green-500'
              : score < 0.6
                ? 'bg-yellow-500'
                : 'bg-red-500';

          return (
            <div key={key}>
              <div className="flex justify-between items-center mb-1">
                <span className="text-gray-300 text-sm">
                  {label}
                  {mitigating && <span className="text-xs text-blue-400 ml-1">(mitigating)</span>}
                </span>
                <span
                  className={`text-sm font-medium ${
                    mitigating
                      ? 'text-blue-400'
                      : contribution > 0.1
                        ? 'text-red-400'
                        : 'text-green-400'
                  }`}
                >
                  {mitigating ? '-' : '+'}
                  {(contribution * 10).toFixed(1)} pts
                  <span className="text-gray-500 text-xs ml-1">({score.toFixed(2)})</span>
                </span>
              </div>
              <div className="h-1.5 bg-gray-700 rounded">
                <div className={`h-1.5 rounded ${barColor}`} style={{ width: `${barWidth}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 p-3 bg-blue-900/20 border border-blue-700/50 rounded-lg text-sm text-blue-300">
        <span className="font-medium">Climate impact on property value:</span>
        {climate.composite_score < 0.3 && ' This property is in a low-risk climate zone.'}
        {climate.composite_score >= 0.3 && climate.composite_score < 0.6 && ' Moderate climate exposure detected.'}
        {climate.composite_score >= 0.6 && ' Significant climate risk - consider assessments.'}
      </div>
    </div>
  );
};

export default ClimateRiskPanel;
