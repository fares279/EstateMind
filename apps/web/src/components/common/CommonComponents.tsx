/**
 * Shared UI components used across all modules
 */

import React from 'react';
import { formatRelativeTime, getConfidenceBgColor } from '../utils/formatting';

/**
 * FreshnessPill: Shows data freshness status with icon and relative time
 * Used everywhere: KPI cards, API responses, data sources
 */
export const FreshnessPill: React.FC<{
  status: 'FRESH' | 'WARN' | 'STALE' | 'CRITICAL';
  timestamp: string | Date;
}> = ({ status, timestamp }) => {
  const config = {
    FRESH: { color: 'text-green-400', icon: '✓', prefix: 'Updated' },
    WARN: { color: 'text-yellow-400', icon: '⚠', prefix: 'Updated' },
    STALE: { color: 'text-orange-400', icon: '⚠', prefix: 'Data from' },
    CRITICAL: { color: 'text-red-400', icon: '✗', prefix: 'Last updated' },
  };

  const c = config[status];
  return (
    <span className={`text-xs ${c.color}`}>
      {c.icon} {c.prefix} {formatRelativeTime(timestamp)}
    </span>
  );
};

/**
 * ConfidenceBadge: Shows confidence level with color coding
 */
export const ConfidenceBadge: React.FC<{
  level: 'HIGH' | 'MEDIUM' | 'LOW';
  score?: number;
}> = ({ level, score }) => {
  const bgColor = {
    HIGH: 'bg-green-900/40 border-green-700/50 text-green-300',
    MEDIUM: 'bg-yellow-900/40 border-yellow-700/50 text-yellow-300',
    LOW: 'bg-red-900/40 border-red-700/50 text-red-300',
  }[level];

  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs 
                      font-medium border ${bgColor}`}>
      {level === 'HIGH' && '✓'}
      {level === 'MEDIUM' && '⚠'}
      {level === 'LOW' && '✗'}
      {' '}
      {level} {score !== undefined && `(${(score * 100).toFixed(0)}%)`}
    </span>
  );
};

/**
 * ConfidenceBand: Shows confidence interval with visual bar
 */
export const ConfidenceBand: React.FC<{
  lower: number;
  upper: number;
  level: number;
  current?: number;
  formatFn: (v: number) => string;
  calibrationStatus?: 'CALIBRATED' | 'PENDING';
}> = ({ lower, upper, level, current, formatFn, calibrationStatus }) => {
  const range = upper - lower;
  const leftPercent = current ? ((current - lower) / range) * 100 : 50;

  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs text-gray-400 mb-1">
        <span>{formatFn(lower)}</span>
        <span className="text-orange-400">{Math.round(level * 100)}% band</span>
        <span>{formatFn(upper)}</span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full relative">
        <div
          className="h-2 bg-orange-500 rounded-full absolute"
          style={{
            left: `${Math.max(0, leftPercent - 5)}%`,
            width: '10%',
          }}
        />
        <div className="h-full w-full bg-gradient-to-r from-orange-500/10 via-orange-500/30 to-orange-500/10 rounded-full" />
      </div>
      {calibrationStatus && (
        <div className="text-xs mt-1">
          {calibrationStatus === 'CALIBRATED' ? (
            <span className="text-green-400">✓ Calibrated confidence interval</span>
          ) : (
            <span className="text-yellow-400">⚠ Calibration pending</span>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * ProvenanceBlock: Shows model metadata (name, training date, data vintage, method)
 */
export const ProvenanceBlock: React.FC<{
  modelName?: string;
  trainedAt?: string;
  dataSnapshot?: string;
  method?: string;
  climateSource?: string;
}> = ({ modelName, trainedAt, dataSnapshot, method, climateSource }) => {
  const items = [
    modelName && `Model: ${modelName}`,
    trainedAt && `Trained: ${trainedAt}`,
    dataSnapshot && `Data: ${dataSnapshot}`,
    method && `Method: ${method}`,
    climateSource && `Climate: ${climateSource}`,
  ].filter(Boolean);

  if (items.length === 0) return null;

  return (
    <div className="text-xs text-gray-600 border-t border-gray-700 pt-2 mt-3 
                    flex flex-wrap gap-3">
      {items.map((item, i) => (
        <span key={i}>{item}</span>
      ))}
    </div>
  );
};

/**
 * TrendBadge: Shows trend direction with color and percentage
 */
export const TrendBadge: React.FC<{
  change: number;
  label?: string;
}> = ({ change, label }) => {
  const color = change > 0 ? 'text-green-400' : change < 0 ? 'text-red-400' : 'text-gray-400';
  const icon = change > 0 ? '↑' : change < 0 ? '↓' : '→';

  return (
    <span className={`text-sm font-medium ${color}`}>
      {icon} {label || ''} {Math.abs(change).toFixed(1)}%
    </span>
  );
};

/**
 * SHAPDriver: Single SHAP feature contribution bar
 */
export const SHAPDriver: React.FC<{
  feature: string;
  value: number;
  direction: 'positive' | 'negative';
  note?: string;
  maxValue?: number;
}> = ({ feature, value, direction, note, maxValue = 2000 }) => {
  const isPositive = direction === 'positive';
  const barColor = isPositive ? 'bg-green-500' : 'bg-red-500';
  const barWidth = Math.min(100, Math.abs(value) / maxValue * 100);

  return (
    <div className="mb-3">
      <div className="flex justify-between items-start mb-1">
        <div>
          <span className="text-white text-sm font-medium">{feature}</span>
          {note && <span className="text-xs text-gray-500 ml-2">({note})</span>}
        </div>
        <span
          className={`text-sm font-medium ${isPositive ? 'text-green-400' : 'text-red-400'}`}
        >
          {isPositive ? '+' : ''}{value.toLocaleString()} TND
        </span>
      </div>
      <div className="h-1.5 bg-gray-700 rounded">
        <div className={`h-1.5 rounded ${barColor}`} style={{ width: `${barWidth}%` }} />
      </div>
    </div>
  );
};

/**
 * SourceCitation: Single source in legal/RAG context
 */
export const SourceCitation: React.FC<{
  lawName: string;
  article: string;
  similarity: number;
  confidenceLabel: 'HIGH' | 'MEDIUM' | 'LOW';
}> = ({ lawName, article, similarity, confidenceLabel }) => {
  const barWidth = Math.round(similarity * 100);
  const barColor =
    similarity >= 0.85 ? 'bg-green-500' : similarity >= 0.65 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="mb-4 p-3 bg-gray-750 rounded-lg">
      <div className="flex justify-between items-start mb-2">
        <div>
          <span className="text-white text-sm font-medium">{lawName}</span>
          <span className="text-gray-400 text-sm ml-2">{article}</span>
        </div>
        <span
          className={`text-xs px-2 py-0.5 rounded font-medium ${getConfidenceBgColor(confidenceLabel)}`}
        >
          {confidenceLabel}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">Similarity: {similarity.toFixed(2)}</span>
        <div className="flex-1 h-1.5 bg-gray-700 rounded">
          <div className={`h-1.5 rounded ${barColor}`} style={{ width: `${barWidth}%` }} />
        </div>
      </div>

      {confidenceLabel === 'MEDIUM' && (
        <div className="text-xs text-yellow-400 mt-1">
          Moderate confidence — consider verifying independently
        </div>
      )}
    </div>
  );
};

/**
 * AnomalyAlert: Warning for anomalous data
 */
export const AnomalyAlert: React.FC<{
  message: string;
  severity?: 'warning' | 'error';
}> = ({ message, severity = 'warning' }) => {
  const bgColor = severity === 'error' ? 'bg-red-900/20 border-red-700/50' : 'bg-yellow-900/20 border-yellow-700/50';
  const textColor = severity === 'error' ? 'text-red-300' : 'text-yellow-300';

  return (
    <div className={`p-3 rounded-lg border ${bgColor} text-sm ${textColor}`}>
      <span>{severity === 'error' ? '✗' : '⚠'}</span>
      {' '}
      {message}
    </div>
  );
};

/**
 * FallbackNotice: Shows when fallback data is being used
 */
export const FallbackNotice: React.FC<{
  reason: string;
}> = ({ reason }) => {
  return (
    <div className="text-xs text-yellow-400 mb-2 flex items-center gap-1">
      <span>⚠</span>
      <span>{reason}</span>
    </div>
  );
};

/**
 * SkeletonLoader: Generic skeleton for loading states
 */
export const SkeletonLoader: React.FC<{
  lines?: number;
  variant?: 'text' | 'card' | 'chart';
}> = ({ lines = 3, variant = 'text' }) => {
  if (variant === 'card') {
    return (
      <div className="bg-gray-800 rounded-xl p-6 animate-pulse">
        <div className="h-4 bg-gray-700 rounded mb-4 w-1/3" />
        <div className="h-8 bg-gray-700 rounded mb-4" />
        <div className="h-2 bg-gray-700 rounded mb-2" />
        <div className="h-2 bg-gray-700 rounded mb-2 w-5/6" />
      </div>
    );
  }

  if (variant === 'chart') {
    return (
      <div className="bg-gray-800 rounded-xl p-6 animate-pulse">
        <div className="flex gap-2 mb-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-6 bg-gray-700 rounded w-20" />
          ))}
        </div>
        <div className="h-64 bg-gray-700 rounded mb-4" />
        <div className="grid grid-cols-3 gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-gray-700 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-2 bg-gray-700 rounded animate-pulse" style={{
          width: `${Math.random() * 40 + 60}%`,
        }} />
      ))}
    </div>
  );
};

/**
 * ErrorBoundary wrapper with fallback UI
 */
export const ErrorFallback: React.FC<{
  error: Error;
  retry: () => void;
}> = ({ error, retry }) => {
  return (
    <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4">
      <div className="text-red-300 text-sm mb-2">
        <span className="font-semibold">Error:</span> {error.message}
      </div>
      <button
        onClick={retry}
        className="text-xs px-3 py-1 bg-red-700 text-white rounded hover:bg-red-600 transition"
      >
        Retry
      </button>
    </div>
  );
};
