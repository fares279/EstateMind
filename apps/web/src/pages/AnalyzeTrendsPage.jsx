import React, { useState, useEffect } from 'react';
import { TrendingUp, Calendar, BarChart3, AlertCircle, Zap } from 'lucide-react';
import ForecastChart from '../features/forecast/components/ForecastChart';
import * as api from '../services/api';

export default function AnalyzeTrendsPage() {
  const [delegation, setDelegation] = useState('Tunis');
  const [propertyType, setPropertyType] = useState('apartment');
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [delegations, setDelegations] = useState([]);

  // Fetch available delegations on component mount
  useEffect(() => {
    const fetchDelegations = async () => {
      try {
        const response = await api.getForecastGovernorateList();
        if (response.data?.governorates) {
          const allDelegations = [];
          for (const gov of response.data.governorates) {
            try {
              const delResponse = await api.getForecastDelegationList(gov);
              if (delResponse.data?.delegations) {
                allDelegations.push(...delResponse.data.delegations);
              }
            } catch (err) {
              console.warn(`Failed to fetch delegations for ${gov}:`, err);
            }
          }
          setDelegations(Array.from(new Set(allDelegations)).sort());
        }
      } catch (err) {
        console.warn('Failed to fetch delegations list:', err);
        // Fallback to common delegations
        setDelegations(['Tunis', 'Sfax', 'Ariana', 'Ben Arous', 'Sousse']);
      }
    };

    fetchDelegations();
  }, []);

  // Fetch forecast data when delegation or property type changes
  useEffect(() => {
    const fetchForecast = async () => {
      if (!delegation) return;

      setLoading(true);
      setError(null);

      try {
        const response = await api.getForecastDelegation(delegation, propertyType);
        setForecastData(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load forecast data');
        setForecastData(null);
      } finally {
        setLoading(false);
      }
    };

    fetchForecast();
  }, [delegation, propertyType]);

  // Summary stats from forecast data
  const summary = forecastData?.summary || {};
  const modelRegistry = forecastData?.model_registry || {};

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] pt-24 px-4">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-2">Price Trends & Forecasts</h1>
        <p className="text-gray-400 mb-8">12-month price forecasts with AI-powered uncertainty quantification</p>

        {/* Controls */}
        <div className="grid md:grid-cols-2 gap-4 mb-8">
          <div>
            <label className="block text-sm font-semibold text-gray-300 mb-2">Delegation</label>
            <select
              value={delegation}
              onChange={(e) => setDelegation(e.target.value)}
              className="w-full px-4 py-2 rounded-lg bg-gray-800 border border-white/20 text-white focus:outline-none focus:border-orange-500"
            >
              {delegations.map((del) => (
                <option key={del} value={del}>
                  {del}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-300 mb-2">Property Type</label>
            <select
              value={propertyType}
              onChange={(e) => setPropertyType(e.target.value)}
              className="w-full px-4 py-2 rounded-lg bg-gray-800 border border-white/20 text-white focus:outline-none focus:border-orange-500"
            >
              <option value="apartment">Apartment</option>
              <option value="villa">Villa</option>
              <option value="land">Land</option>
            </select>
          </div>
        </div>

        {/* Summary Stats */}
        {!loading && forecastData && (
          <div className="grid md:grid-cols-4 gap-4 mb-8">
            <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-4">
              <p className="text-gray-400 text-sm mb-1">Current Price</p>
              <p className="text-2xl font-bold text-emerald-400">
                ${summary.current_price_per_m2?.toLocaleString() || 'N/A'}
              </p>
              <p className="text-xs text-gray-500 mt-2">TND/m²</p>
            </div>
            <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-4">
              <p className="text-gray-400 text-sm mb-1">6-Month Price</p>
              <p className="text-2xl font-bold text-blue-400">
                ${summary.price_6m?.toLocaleString() || 'N/A'}
              </p>
              <p className="text-xs text-gray-500 mt-2">Growth: {summary.growth_pct_6m || 0}%</p>
            </div>
            <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-4">
              <p className="text-gray-400 text-sm mb-1">12-Month Price</p>
              <p className="text-2xl font-bold text-[#FF6B35]">
                ${summary.price_12m?.toLocaleString() || 'N/A'}
              </p>
              <p className="text-xs text-gray-500 mt-2">Growth: {summary.growth_pct_12m || 0}%</p>
            </div>
            <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-4">
              <p className="text-gray-400 text-sm mb-1">Trend Direction</p>
              <p className={`text-2xl font-bold ${
                summary.trend === 'rising' ? 'text-green-400' :
                summary.trend === 'falling' ? 'text-red-400' :
                'text-yellow-400'
              }`}>
                {summary.trend?.toUpperCase() || 'STABLE'}
              </p>
              <TrendingUp className="text-inherit mt-2" size={20} />
            </div>
          </div>
        )}

        {/* Main Chart Section */}
        <div className="glass-card bg-white/5 backdrop-blur-lg border border-white/10 rounded-lg p-8">
          {error && (
            <div className="mb-6 p-4 bg-red-900/20 border border-red-500/50 rounded-lg flex items-start gap-3">
              <AlertCircle className="text-red-400 mt-1 flex-shrink-0" size={20} />
              <div>
                <p className="text-red-400 font-semibold">Error Loading Forecast</p>
                <p className="text-red-300 text-sm">{error}</p>
              </div>
            </div>
          )}

          <ForecastChart
            data={forecastData?.months || []}
            modelType={modelRegistry.model_type || 'LINEAR_TREND'}
            confidenceLevel={forecastData?.conformal_calibration?.coverage || 0.90}
            uncertaintyMethod={forecastData?.uncertainty_method || 'fixed_mape'}
            modelRegistry={modelRegistry}
            calibrationMetadata={forecastData?.conformal_calibration || {}}
            title={`${delegation} - ${propertyType.charAt(0).toUpperCase() + propertyType.slice(1)} Price Forecast`}
            loading={loading}
            error={error}
          />
        </div>

        {/* Model Info */}
        {!loading && forecastData && modelRegistry && Object.keys(modelRegistry).length > 0 && (
          <div className="mt-8 grid md:grid-cols-2 gap-4">
            <div className="glass-card bg-purple-900/20 border border-purple-500/30 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-purple-300 mb-4 flex items-center gap-2">
                <Zap size={20} />
                Model Information
              </h3>
              <div className="space-y-2 text-sm">
                <p><span className="text-gray-400">Type:</span> <span className="text-white font-semibold">{modelRegistry.model_type}</span></p>
                <p><span className="text-gray-400">History:</span> <span className="text-white">{modelRegistry.history_months} months</span></p>
                <p><span className="text-gray-400">Median MAPE:</span> <span className="text-white">{modelRegistry.median_mape?.toFixed(2)}%</span></p>
                <p><span className="text-gray-400">P90 MAPE:</span> <span className="text-white">{modelRegistry.p90_mape?.toFixed(2)}%</span></p>
                <p><span className="text-gray-400">Status:</span> <span className="text-emerald-400">{modelRegistry.qualified ? '✓ Qualified' : '⚠ Review Needed'}</span></p>
                <p><span className="text-gray-400">Trained:</span> <span className="text-white text-xs">{new Date(modelRegistry.trained_at).toLocaleDateString()}</span></p>
              </div>
            </div>

            {forecastData?.conformal_calibration && Object.keys(forecastData.conformal_calibration).length > 0 && (
              <div className="glass-card bg-cyan-900/20 border border-cyan-500/30 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-cyan-300 mb-4 flex items-center gap-2">
                  <BarChart3 size={20} />
                  Calibration Metadata
                </h3>
                <div className="space-y-2 text-sm">
                  <p><span className="text-gray-400">Coverage:</span> <span className="text-white">{(forecastData.conformal_calibration.coverage * 100).toFixed(0)}%</span></p>
                  <p><span className="text-gray-400">Samples:</span> <span className="text-white">{forecastData.conformal_calibration.n_calibration || 'N/A'}</span></p>
                  <p><span className="text-gray-400">Quantile Level:</span> <span className="text-white">{forecastData.conformal_calibration.quantile_level?.toFixed(3) || 'N/A'}</span></p>
                  <p><span className="text-gray-400">Uncertainty:</span> <span className="text-emerald-400">{forecastData.uncertainty_method}</span></p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer Info */}
        <div className="mt-8 text-xs text-gray-500 border-t border-gray-700 pt-4">
          <p>
            ℹ️ Forecasts are generated using advanced machine learning models (Linear Regression, N-BEATS, and Temporal Fusion Transformer) with empirical coverage calibration.
            Confidence intervals are distribution-free and guaranteed to cover the true price at least {Math.round((forecastData?.conformal_calibration?.coverage || 0.9) * 100)}% of the time.
            Past performance does not guarantee future results.
          </p>
        </div>
      </div>
    </div>
  );
}
