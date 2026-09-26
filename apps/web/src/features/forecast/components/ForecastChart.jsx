import React, { useMemo } from 'react';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { TrendingUp, AlertCircle, Shield, Zap } from 'lucide-react';

/**
 * ForecastChart: Multi-layer quantile fan chart for price forecasts
 * 
 * Features:
 * - Displays nested quantile bands (0.1, 0.3, 0.5, 0.7, 0.9)
 * - Color-coded uncertainty levels (darker=more confident)
 * - Model type badge (LINEAR_TREND, NBEATS, TFT)
 * - Confidence level indicator
 * - Custom tooltip with detailed quantile information
 */
export default function ForecastChart({
  data = [],
  modelType = 'LINEAR_TREND',
  confidenceLevel = 0.90,
  uncertaintyMethod = 'conformal_prediction',
  modelRegistry = {},
  calibrationMetadata = {},
  title = 'Price Forecast',
  loading = false,
  error = null,
}) {
  // Quantile color scheme: darker alpha = more extreme quantiles, lighter = near median
  const QUANTILE_COLORS = {
    q0_1: { color: '#8B5CF6', opacity: 0.15, label: '10th' },  // violet-600, very dark
    q0_3: { color: '#06B6D4', opacity: 0.25, label: '30th' },  // cyan-500, dark
    q0_5: { color: '#10B981', opacity: 0.35, label: 'Median' }, // emerald-500, medium (but this is the line, not area)
    q0_7: { color: '#06B6D4', opacity: 0.25, label: '70th' },  // cyan-500, dark
    q0_9: { color: '#8B5CF6', opacity: 0.15, label: '90th' },  // violet-600, very dark
  };

  // Model type badge configuration
  const MODEL_BADGES = {
    LINEAR_TREND: { color: 'bg-blue-500/20', textColor: 'text-blue-400', label: 'Linear Trend', icon: '📊' },
    NBEATS: { color: 'bg-purple-500/20', textColor: 'text-purple-400', label: 'N-BEATS (Neural)', icon: '🧠' },
    TFT: { color: 'bg-orange-500/20', textColor: 'text-orange-400', label: 'TFT (Transformer)', icon: '⚡' },
  };

  const modelBadge = MODEL_BADGES[modelType] || MODEL_BADGES.LINEAR_TREND;

  // Transform forecast data to chart format
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    return data.map((month) => ({
      month: month.month_label || month.month,
      horizon: month.horizon,
      price: month.price_per_m2,
      q0_1: month.quantiles?.q0_1,
      q0_3: month.quantiles?.q0_3,
      q0_5: month.quantiles?.q0_5,
      q0_7: month.quantiles?.q0_7,
      q0_9: month.quantiles?.q0_9,
      lower: month.lower, // fallback if quantiles not available
      upper: month.upper, // fallback if quantiles not available
    }));
  }, [data]);

  // Check if we have quantile data or fallback to simple bounds
  const hasQuantiles = chartData.length > 0 && chartData[0].q0_1 !== undefined;

  // Custom tooltip showing detailed information
  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || payload.length === 0) return null;

    const data = payload[0].payload;

    return (
      <div className="bg-gray-900/95 border border-white/20 rounded p-3 shadow-lg">
        <p className="text-white font-semibold text-sm mb-2">{data.month}</p>
        <p className="text-emerald-400 font-bold">${data.price?.toFixed(2)}</p>

        {hasQuantiles ? (
          <>
            <p className="text-xs text-gray-400 mt-2">Quantile Range:</p>
            <p className="text-xs text-blue-400">Q10: ${data.q0_1?.toFixed(2)}</p>
            <p className="text-xs text-cyan-400">Q30: ${data.q0_3?.toFixed(2)}</p>
            <p className="text-xs text-purple-400">Q70: ${data.q0_7?.toFixed(2)}</p>
            <p className="text-xs text-violet-400">Q90: ${data.q0_9?.toFixed(2)}</p>
          </>
        ) : (
          <>
            <p className="text-xs text-gray-400 mt-2">Confidence Interval:</p>
            <p className="text-xs text-blue-400">Lower: ${data.lower?.toFixed(2)}</p>
            <p className="text-xs text-blue-400">Upper: ${data.upper?.toFixed(2)}</p>
          </>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="w-full h-96 flex items-center justify-center bg-gray-900/50 rounded-lg">
        <div className="text-center">
          <div className="animate-spin mb-4">
            <Zap className="mx-auto text-orange-500" size={32} />
          </div>
          <p className="text-gray-400">Loading forecast data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-96 flex items-center justify-center bg-red-900/20 border border-red-500/50 rounded-lg">
        <div className="text-center">
          <AlertCircle className="mx-auto mb-4 text-red-400" size={32} />
          <p className="text-red-400 font-semibold">Error Loading Forecast</p>
          <p className="text-gray-400 text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="w-full h-96 flex items-center justify-center bg-gray-900/50 rounded-lg">
        <div className="text-center">
          <TrendingUp className="mx-auto mb-4 text-gray-600" size={32} />
          <p className="text-gray-400">No forecast data available</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6">
      {/* Header with Title and Model Badge */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-white">{title}</h3>
          <p className="text-sm text-gray-400 mt-1">
            12-month price forecast with uncertainty bands
          </p>
        </div>
        <div className={`${modelBadge.color} ${modelBadge.textColor} px-4 py-2 rounded-lg border border-white/10 text-sm font-semibold flex items-center gap-2`}>
          <span>{modelBadge.icon}</span>
          <span>{modelBadge.label}</span>
        </div>
      </div>

      {/* Main Chart */}
      <div className="bg-gray-900/50 border border-white/10 rounded-lg p-6">
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart
            data={chartData}
            margin={{ top: 20, right: 30, left: 0, bottom: 60 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              dataKey="month"
              stroke="#666"
              angle={-45}
              textAnchor="end"
              height={100}
              tick={{ fontSize: 12 }}
            />
            <YAxis
              stroke="#666"
              tick={{ fontSize: 12 }}
              label={{ value: 'Price (TND/m²)', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip content={<CustomTooltip />} />

            {/* Quantile Bands - Nested Areas for Fan Effect */}
            {hasQuantiles ? (
              <>
                {/* Outermost band: Q0.1 to Q0.9 */}
                <Area
                  type="monotone"
                  dataKey="q0_9"
                  fill={QUANTILE_COLORS.q0_9.color}
                  stroke="none"
                  fillOpacity={QUANTILE_COLORS.q0_9.opacity}
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="q0_1"
                  fill="transparent"
                  stroke="none"
                  isAnimationActive={false}
                />

                {/* Middle band: Q0.3 to Q0.7 */}
                <Area
                  type="monotone"
                  dataKey="q0_7"
                  fill={QUANTILE_COLORS.q0_7.color}
                  stroke="none"
                  fillOpacity={QUANTILE_COLORS.q0_7.opacity}
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="q0_3"
                  fill="transparent"
                  stroke="none"
                  isAnimationActive={false}
                />

                {/* Median Line */}
                <Line
                  type="monotone"
                  dataKey="q0_5"
                  stroke={QUANTILE_COLORS.q0_5.color}
                  strokeWidth={3}
                  dot={false}
                  name="Median"
                  isAnimationActive={false}
                />
              </>
            ) : (
              <>
                {/* Fallback: Simple confidence interval bands */}
                <Area
                  type="monotone"
                  dataKey="upper"
                  fill="#8B5CF6"
                  stroke="none"
                  fillOpacity={0.2}
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="lower"
                  fill="transparent"
                  stroke="none"
                  isAnimationActive={false}
                />

                {/* Point Forecast Line */}
                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="#10B981"
                  strokeWidth={3}
                  dot={false}
                  name="Forecast"
                  isAnimationActive={false}
                />
              </>
            )}

            <Legend
              verticalAlign="top"
              height={36}
              wrapperStyle={{ paddingBottom: '20px' }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Metadata Cards */}
      <div className="grid md:grid-cols-3 gap-4">
        {/* Confidence Level Card */}
        <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Shield className="text-blue-400 mt-1" size={20} />
            <div>
              <p className="text-gray-400 text-sm">Confidence Level</p>
              <p className="text-white font-bold text-lg">
                {Math.round(confidenceLevel * 100)}%
              </p>
              <p className="text-blue-400 text-xs mt-1">
                {uncertaintyMethod === 'conformal_prediction'
                  ? 'Distribution-free guarantee'
                  : 'Fixed MAPE bands'}
              </p>
            </div>
          </div>
        </div>

        {/* Model Performance Card */}
        {modelRegistry && Object.keys(modelRegistry).length > 0 && (
          <div className="bg-purple-900/20 border border-purple-500/30 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <TrendingUp className="text-purple-400 mt-1" size={20} />
              <div>
                <p className="text-gray-400 text-sm">Median MAPE</p>
                <p className="text-white font-bold text-lg">
                  {(modelRegistry.median_mape || 0).toFixed(2)}%
                </p>
                <p className="text-purple-400 text-xs mt-1">
                  {modelRegistry.qualified ? '✓ Qualified' : '⚠ Requires Review'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Calibration Info Card */}
        {calibrationMetadata && Object.keys(calibrationMetadata).length > 0 && (
          <div className="bg-emerald-900/20 border border-emerald-500/30 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Zap className="text-emerald-400 mt-1" size={20} />
              <div>
                <p className="text-gray-400 text-sm">Calibration</p>
                <p className="text-white font-bold text-lg">
                  n={calibrationMetadata.n_calibration || 'N/A'}
                </p>
                <p className="text-emerald-400 text-xs mt-1">
                  {calibrationMetadata.quantile_level
                    ? `Q=${calibrationMetadata.quantile_level.toFixed(3)}`
                    : 'Coverage tuned'}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quantile Legend (if using quantiles) */}
      {hasQuantiles && (
        <div className="bg-gray-900/30 border border-white/10 rounded-lg p-4">
          <p className="text-gray-300 text-sm font-semibold mb-3">Uncertainty Bands</p>
          <div className="grid md:grid-cols-5 gap-3 text-xs">
            <div className="flex items-center gap-2">
              <div
                className="w-4 h-4 rounded"
                style={{
                  backgroundColor: QUANTILE_COLORS.q0_1.color,
                  opacity: QUANTILE_COLORS.q0_1.opacity,
                }}
              />
              <span className="text-gray-400">10th-90th percentile (outer band)</span>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="w-4 h-4 rounded"
                style={{
                  backgroundColor: QUANTILE_COLORS.q0_3.color,
                  opacity: QUANTILE_COLORS.q0_3.opacity,
                }}
              />
              <span className="text-gray-400">30th-70th percentile</span>
            </div>
            <div className="col-span-3 text-gray-500">
              Darker shading indicates more extreme outcomes. The median line (green) represents the most likely scenario.
            </div>
          </div>
        </div>
      )}

      {/* Footer Note */}
      <div className="text-xs text-gray-500 border-t border-gray-700 pt-4">
        <p>
          ℹ️ Forecasts are statistical estimates based on historical price data and trained model parameters.
          Actual prices may vary. {uncertaintyMethod === 'conformal_prediction' && 'Intervals are calibrated for 90% empirical coverage.'}
        </p>
      </div>
    </div>
  );
}
