import React from 'react';
import { Shield, AlertCircle, Zap, Info } from 'lucide-react';

/**
 * UncertaintyBadge: Displays confidence level and uncertainty method
 * 
 * Props:
 * - confidenceLevel: number (0-1), e.g., 0.90
 * - method: 'conformal_prediction' | 'fixed_mape' | 'native_quantiles'
 * - size: 'sm' | 'md' | 'lg'
 * - showTooltip: boolean
 */
export default function UncertaintyBadge({
  confidenceLevel = 0.90,
  method = 'conformal_prediction',
  size = 'md',
  showTooltip = true,
  className = '',
}) {
  const confidencePercent = Math.round(confidenceLevel * 100);

  const methodInfo = {
    conformal_prediction: {
      label: 'Conformal',
      description: 'Distribution-free empirical coverage guarantee',
      color: 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400',
      icon: Shield,
    },
    fixed_mape: {
      label: 'Fixed MAPE',
      description: 'Based on Mean Absolute Percentage Error',
      color: 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400',
      icon: AlertCircle,
    },
    native_quantiles: {
      label: 'Native Quantiles',
      description: 'Direct quantile regression output',
      color: 'bg-purple-500/20 border-purple-500/50 text-purple-400',
      icon: Zap,
    },
  };

  const info = methodInfo[method] || methodInfo.conformal_prediction;
  const Icon = info.icon;

  const sizeClasses = {
    sm: 'px-3 py-1 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  return (
    <div className={`relative group ${className}`}>
      <div className={`${info.color} border rounded-lg font-semibold flex items-center gap-2 ${sizeClasses[size]}`}>
        <Icon size={size === 'sm' ? 14 : size === 'md' ? 16 : 18} />
        <span>{confidencePercent}% {info.label}</span>
      </div>

      {showTooltip && (
        <div className="absolute left-0 mt-2 w-64 bg-gray-900/95 border border-white/20 rounded-lg p-3 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none group-hover:pointer-events-auto z-10">
          <div className="flex gap-2 mb-2">
            <Info size={16} className="text-blue-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-white text-sm">{info.label} Uncertainty</p>
              <p className="text-gray-300 text-xs mt-1">{info.description}</p>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {method === 'conformal_prediction' && (
              'This interval is calibrated empirically and has a theoretical guarantee to cover the true value at least the stated percentage of the time, regardless of the underlying data distribution.'
            )}
            {method === 'fixed_mape' && (
              'This interval is based on the historical Mean Absolute Percentage Error (MAPE) of the model. It represents a standard margin around the point forecast.'
            )}
            {method === 'native_quantiles' && (
              'This interval is produced directly by the neural network as native quantile predictions, trained via quantile regression.'
            )}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * UncertaintyMetrics: Detailed display of uncertainty metrics
 * 
 * Props:
 * - confidenceLevel: number (0-1)
 * - method: string
 * - mape: number (percentage)
 * - p90Mape: number (percentage)
 * - calibrationSamples: number
 */
export function UncertaintyMetrics({
  confidenceLevel = 0.90,
  method = 'conformal_prediction',
  mape = null,
  p90Mape = null,
  calibrationSamples = null,
}) {
  return (
    <div className="bg-gradient-to-br from-gray-900/50 to-gray-800/30 border border-white/10 rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-lg font-semibold text-white">Uncertainty Metrics</h4>
        <UncertaintyBadge
          confidenceLevel={confidenceLevel}
          method={method}
          size="md"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {mape !== null && (
          <div className="bg-gray-800/50 rounded p-3">
            <p className="text-gray-400 text-xs mb-1">Median MAPE</p>
            <p className="text-white font-bold text-lg">{mape.toFixed(2)}%</p>
          </div>
        )}

        {p90Mape !== null && (
          <div className="bg-gray-800/50 rounded p-3">
            <p className="text-gray-400 text-xs mb-1">P90 MAPE</p>
            <p className="text-white font-bold text-lg">{p90Mape.toFixed(2)}%</p>
          </div>
        )}

        {calibrationSamples !== null && (
          <div className="bg-gray-800/50 rounded p-3">
            <p className="text-gray-400 text-xs mb-1">Calibration Samples</p>
            <p className="text-white font-bold text-lg">{calibrationSamples}</p>
          </div>
        )}

        <div className="bg-gray-800/50 rounded p-3">
          <p className="text-gray-400 text-xs mb-1">Coverage Level</p>
          <p className="text-white font-bold text-lg">{Math.round(confidenceLevel * 100)}%</p>
        </div>
      </div>

      <div className="border-t border-white/10 pt-3 text-xs text-gray-400">
        <p>
          {method === 'conformal_prediction' && (
            'Interval calibrated via empirical quantile method with distribution-free coverage guarantee.'
          )}
          {method === 'fixed_mape' && (
            'Interval based on historical model errors with fixed percentage margin.'
          )}
          {method === 'native_quantiles' && (
            'Interval produced by neural network quantile regression heads.'
          )}
        </p>
      </div>
    </div>
  );
}

/**
 * MethodIndicator: Shows which uncertainty method is being used
 * 
 * Helpful for understanding what type of uncertainty quantification is applied
 */
export function MethodIndicator({ method = 'conformal_prediction', compact = false }) {
  const methodInfo = {
    conformal_prediction: {
      label: 'Conformal Prediction',
      description: 'Distribution-free empirical coverage',
      color: 'emerald',
      icon: '🎯',
    },
    fixed_mape: {
      label: 'Fixed MAPE',
      description: 'Percentage-based error bounds',
      color: 'yellow',
      icon: '⚠️',
    },
    native_quantiles: {
      label: 'Native Quantiles',
      description: 'Neural network output',
      color: 'purple',
      icon: '⚡',
    },
  };

  const info = methodInfo[method] || methodInfo.conformal_prediction;
  const colorMap = {
    emerald: 'bg-emerald-900/30 border-emerald-500/50 text-emerald-400',
    yellow: 'bg-yellow-900/30 border-yellow-500/50 text-yellow-400',
    purple: 'bg-purple-900/30 border-purple-500/50 text-purple-400',
  };

  if (compact) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold border ${colorMap[info.color]}`}>
        <span>{info.icon}</span>
        <span>{info.label}</span>
      </span>
    );
  }

  return (
    <div className={`border rounded-lg p-4 ${colorMap[info.color]}`}>
      <p className="font-semibold text-sm flex items-center gap-2">
        <span>{info.icon}</span>
        {info.label}
      </p>
      <p className="text-xs mt-1 text-gray-300">{info.description}</p>
    </div>
  );
}
