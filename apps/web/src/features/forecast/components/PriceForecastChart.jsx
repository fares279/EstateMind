/**
 * Forecast - 12-Month Fan Chart
 * Shows quantile price forecast with model metadata
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { getForecast } from '../../../services/api-modules';
import { ProvenanceBlock, SkeletonLoader, ErrorFallback } from '../../../components/shared/CommonComponents';

const FanChart = ({ data }) => {
  const canvasRef = useRef(null);
  const width = 600;
  const height = 300;
  const margin = { top: 20, right: 20, bottom: 30, left: 60 };

  useEffect(() => {
    if (!canvasRef.current) return;

    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) return;

    // Background
    ctx.fillStyle = '#1f2937';
    ctx.fillRect(0, 0, width, height);

    const prices = data.flatMap((d) => [d.p10, d.p25, d.p50, d.p75, d.p90]);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice;

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const scaleX = innerWidth / (data.length - 1);
    const scaleY = innerHeight / priceRange;

    const getX = (i) => margin.left + i * scaleX;
    const getY = (price) => margin.top + innerHeight - (price - minPrice) * scaleY;

    // Outer band (P10-P90)
    ctx.fillStyle = 'rgba(249, 115, 22, 0.08)';
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(data[0].p90));
    data.forEach((d, i) => ctx.lineTo(getX(i), getY(d.p90)));
    [...data].reverse().forEach((d, i) => ctx.lineTo(getX(data.length - 1 - i), getY(d.p10)));
    ctx.closePath();
    ctx.fill();

    // Inner band (P25-P75)
    ctx.fillStyle = 'rgba(249, 115, 22, 0.18)';
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(data[0].p75));
    data.forEach((d, i) => ctx.lineTo(getX(i), getY(d.p75)));
    [...data].reverse().forEach((d, i) => ctx.lineTo(getX(data.length - 1 - i), getY(d.p25)));
    ctx.closePath();
    ctx.fill();

    // Median line
    ctx.strokeStyle = '#f97316';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    data.forEach((d, i) => {
      if (i === 0) ctx.moveTo(getX(i), getY(d.p50));
      else ctx.lineTo(getX(i), getY(d.p50));
    });
    ctx.stroke();

    // Axes
    ctx.strokeStyle = '#6b7280';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top);
    ctx.lineTo(margin.left, height - margin.bottom);
    ctx.lineTo(width - margin.right, height - margin.bottom);
    ctx.stroke();

    // Labels
    ctx.fillStyle = '#9ca3af';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    data.forEach((d, i) => {
      ctx.fillText(d.month, getX(i), height - margin.bottom + 15);
    });
  }, [data]);

  return <canvas ref={canvasRef} width={width} height={height} className="w-full" />;
};

export const ForecastFanChart = ({ delegation, propertyType }) => {
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const chartData = useMemo(() => {
    const months = Array.isArray(forecast?.months) ? forecast.months : [];
    if (months.length > 0) {
      return months.map((month, index) => ({
        month: month.month_label || month.month || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][index] || `M${index + 1}`,
        p10: month.lower ?? month.price_per_m2 ?? 0,
        p25: month.lower ?? month.price_per_m2 ?? 0,
        p50: month.price_per_m2 ?? 0,
        p75: month.upper ?? month.price_per_m2 ?? 0,
        p90: month.upper ?? month.price_per_m2 ?? 0,
      }));
    }

    const bands = forecast?.monthly_prices || forecast?.monthly_price_bands;
    if (!bands || !Array.isArray(bands.p50) || bands.p50.length === 0) {
      return [];
    }

    return bands.p50.map((_, index) => ({
      month: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][index] || `M${index + 1}`,
      p10: bands.p10?.[index] ?? bands.p25?.[index] ?? bands.p50[index] ?? 0,
      p25: bands.p25?.[index] ?? bands.p50[index] ?? 0,
      p50: bands.p50?.[index] ?? 0,
      p75: bands.p75?.[index] ?? bands.p50[index] ?? 0,
      p90: bands.p90?.[index] ?? bands.p75?.[index] ?? bands.p50[index] ?? 0,
    }));
  }, [forecast]);

  const summary = forecast?.summary || {};
  const currentPrice = forecast?.current_price ?? summary.current_price_per_m2 ?? chartData[0]?.p50 ?? 0;
  const forecast6m = forecast?.forecast_6m?.price ?? summary.price_6m ?? chartData[5]?.p50 ?? currentPrice;
  const forecast12m = forecast?.forecast_12m?.price ?? summary.price_12m ?? chartData[11]?.p50 ?? forecast6m;
  const forecast6mChange = forecast?.forecast_6m?.pct_change ?? summary.growth_pct_6m ?? 0;
  const forecast12mChange = forecast?.forecast_12m?.pct_change ?? summary.growth_pct_12m ?? 0;
  const modelBadge = forecast?.model_badge || forecast?.model_version || 'Forecast';
  const confidenceMethod = forecast?.confidence_method || forecast?.uncertainty_method || 'Conformal';
  const calibrationCoverage = forecast?.calibration_coverage_pct ?? forecast?.conformal_calibration?.coverage ?? null;
  const trainedMonths = forecast?.trained_months ?? forecast?.model_registry?.history_months ?? null;
  const lastUpdated = forecast?.last_updated ?? forecast?.model_registry?.trained_at ?? null;
  const mapePct = forecast?.mape_pct ?? forecast?.model_registry?.median_mape ?? null;

  const loadForecast = async () => {
    try {
      setLoading(true);
      const data = await getForecast(delegation, propertyType);
      setForecast(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load forecast'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadForecast();
  }, [delegation, propertyType]);

  if (error) return <ErrorFallback error={error} retry={loadForecast} />;
  if (loading) return <SkeletonLoader variant="chart" />;
  if (!forecast) return null;

  if (chartData.length === 0) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 text-sm text-gray-400">
        No forecast series is available for this selection yet.
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <div className="text-sm text-gray-400">12-Month Price Forecast</div>
          <div className="flex gap-2 mt-2">
            <span className="px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded text-xs">
              🧠 {modelBadge}
            </span>
            <span className="px-2 py-0.5 bg-orange-900/50 text-orange-300 rounded text-xs">
              {confidenceMethod} Conformal
            </span>
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-gray-750 rounded p-3">
          <div className="text-xs text-gray-500">Current Price</div>
          <div className="text-lg font-bold text-white">{Math.round(currentPrice).toLocaleString('fr-TN')} TND</div>
        </div>
        <div className="bg-gray-750 rounded p-3">
          <div className="text-xs text-gray-500">6-Month Forecast</div>
          <div className="text-lg font-bold text-green-400">
            {Math.round(forecast6m).toLocaleString('fr-TN')}
            <span className="text-xs ml-1">{forecast6mChange > 0 ? '+' : ''}{forecast6mChange.toFixed(1)}%</span>
          </div>
        </div>
        <div className="bg-gray-750 rounded p-3">
          <div className="text-xs text-gray-500">12-Month Forecast</div>
          <div className="text-lg font-bold text-green-400">
            {Math.round(forecast12m).toLocaleString('fr-TN')}
            <span className="text-xs ml-1">{forecast12mChange > 0 ? '+' : ''}{forecast12mChange.toFixed(1)}%</span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="mb-4">
        <FanChart data={chartData} />
      </div>

      {/* Calibration */}
      <div className="text-xs text-gray-600 mb-3">
        {calibrationCoverage != null
          ? `Calibration: ${calibrationCoverage}% of historical forecasts contained actual prices`
          : 'Calibration data unavailable for this forecast.'}
      </div>

      {/* Provenance */}
      <ProvenanceBlock
        modelName={modelBadge}
        trainedDate={trainedMonths != null ? `${trainedMonths} months` : 'N/A'}
        dataSnapshot={lastUpdated || 'N/A'}
        method={mapePct != null ? `MAPE: ${Number(mapePct).toFixed(1)}%` : confidenceMethod}
      />
    </div>
  );
};

export default ForecastFanChart;
