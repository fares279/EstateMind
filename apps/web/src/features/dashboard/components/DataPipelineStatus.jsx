/**
 * Data Pipeline Status
 * Shows market data pipeline health and freshness
 */

import React, { useState, useEffect } from 'react';
import { getScraperPipelineHealth } from '../../../services/api-modules';
import { FreshnessPill, SkeletonLoader, ErrorFallback } from '../../../components/common/CommonComponents';

export const DataFreshnessHeader = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadPipelineHealth = async () => {
    try {
      setLoading(true);
      const health = await getScraperPipelineHealth();
      setData(health);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load pipeline health'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPipelineHealth();
    const interval = setInterval(loadPipelineHealth, 30 * 60 * 1000); // 30 minutes
    return () => clearInterval(interval);
  }, []);

  if (error) return <ErrorFallback error={error} retry={loadPipelineHealth} />;
  if (loading) return <SkeletonLoader variant="text" lines={1} />;
  if (!data) return null;

  return (
    <div className="bg-gray-750 border border-gray-700 rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-8 text-sm">
          <div>
            <span className="text-gray-400">Listings:</span>{' '}
            <span className="text-white font-semibold">{data.total_listings.toLocaleString()}</span>
          </div>
          <div>
            <span className="text-gray-400">Delegations:</span>{' '}
            <span className="text-white font-semibold">{data.delegation_coverage}</span>
          </div>
          <div>
            <span className="text-gray-400">Active Sources:</span>{' '}
            <span className="text-white font-semibold">{data.active_sources}</span>
          </div>
        </div>
        <FreshnessPill status={data.freshness_status} timestamp={data.last_updated} />
      </div>
    </div>
  );
};

export default DataFreshnessHeader;
