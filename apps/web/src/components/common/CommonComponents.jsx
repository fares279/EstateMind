/**
 * Shared UI Components - Formatting and Display Utilities
 * Used by all 10 modules for consistent visual presentation
 */

import React from 'react';

/**
 * FreshnessPill - Shows data age with color-coded status
 */
export const FreshnessPill = ({ status = 'FRESH', timestamp }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'FRESH': return 'bg-green-900/50 border border-green-600 text-green-400';
      case 'WARN': return 'bg-yellow-900/50 border border-yellow-600 text-yellow-400';
      case 'STALE': return 'bg-orange-900/50 border border-orange-600 text-orange-400';
      case 'CRITICAL': return 'bg-red-900/50 border border-red-600 text-red-400';
      default: return 'bg-gray-700 border border-gray-600 text-gray-300';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'FRESH': return '✓';
      case 'WARN': return '⚠';
      case 'STALE': return '⚠';
      case 'CRITICAL': return '✗';
      default: return '•';
    }
  };

  const getRelativeTime = () => {
    if (!timestamp) return 'unknown';
    const now = new Date();
    const then = new Date(timestamp);
    const sec = Math.floor((now - then) / 1000);
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    return `${Math.floor(sec / 86400)}d ago`;
  };

  return (
    <div className={`px-2 py-1 rounded text-xs font-medium inline-flex items-center gap-1 ${getStatusColor()}`}>
      <span>{getStatusIcon()}</span>
      <span>{getRelativeTime()}</span>
    </div>
  );
};

/**
 * ConfidenceBadge - Shows confidence level with color
 */
export const ConfidenceBadge = ({ confidence = 'MEDIUM' }) => {
  const getColor = () => {
    switch (confidence) {
      case 'HIGH': return 'bg-green-600 text-white';
      case 'MEDIUM': return 'bg-yellow-600 text-white';
      case 'LOW': return 'bg-red-600 text-white';
      default: return 'bg-gray-600 text-white';
    }
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-semibold ${getColor()}`}>
      {confidence}
    </span>
  );
};

/**
 * ConfidenceBand - Visual confidence interval display
 */
export const ConfidenceBand = ({ lower, upper, current, calibrated = true }) => {
  const total = upper - lower || 1;
  const leftPercent = ((current - lower) / total) * 100;

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <div className="flex-1 relative h-2 bg-gray-700 rounded-full overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-orange-500/20 to-orange-500/40 rounded-full" />
          <div
            className="absolute top-0 h-full w-1 bg-orange-500 rounded-full"
            style={{ left: `${Math.max(0, Math.min(100, leftPercent))}%` }}
          />
        </div>
      </div>
      <div className="text-xs text-gray-400 flex justify-between">
        <span>{lower.toLocaleString()}</span>
        <span className="text-orange-400 font-semibold">{current.toLocaleString()}</span>
        <span>{upper.toLocaleString()}</span>
      </div>
      {calibrated && (
        <div className="text-xs text-green-400">✓ Calibrated</div>
      )}
    </div>
  );
};

/**
 * ProvenanceBlock - Model metadata footer
 */
export const ProvenanceBlock = ({ modelName, trainedDate, dataSnapshot, method }) => (
  <div className="border-t border-gray-700 pt-3 mt-3 text-xs text-gray-500 space-y-0.5">
    <div><span className="text-gray-400">Model:</span> {modelName}</div>
    <div><span className="text-gray-400">Trained:</span> {trainedDate}</div>
    <div><span className="text-gray-400">Data snapshot:</span> {dataSnapshot}</div>
    <div><span className="text-gray-400">Method:</span> {method}</div>
  </div>
);

/**
 * TrendBadge - Directional trend indicator
 */
export const TrendBadge = ({ change, label }) => {
  const isPositive = change > 0;
  const color = isPositive ? 'text-green-400' : change < 0 ? 'text-red-400' : 'text-gray-400';
  const icon = isPositive ? '↑' : change < 0 ? '↓' : '→';

  return (
    <span className={`${color} font-semibold`}>
      {icon} {Math.abs(change).toFixed(1)}% {label}
    </span>
  );
};

/**
 * SHAPDriver - Single feature contribution display
 */
export const SHAPDriver = ({ name, impact, direction, unit = '' }) => {
  const isPositive = direction === 'positive';
  const barPercent = Math.abs(impact) / 100 * 100;
  const color = isPositive ? 'bg-green-600' : 'bg-red-600';

  return (
    <div className="mb-2">
      <div className="flex justify-between items-center text-sm mb-1">
        <span className="text-gray-300">{name}</span>
        <span className={isPositive ? 'text-green-400' : 'text-red-400'}>
          {isPositive ? '+' : ''}
          {impact.toFixed(1)} {unit}
        </span>
      </div>
      <div className="h-1.5 bg-gray-700 rounded overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(barPercent, 100)}%` }} />
      </div>
    </div>
  );
};

/**
 * SourceCitation - Single source with similarity score
 */
export const SourceCitation = ({ source, similarity, confidence }) => {
  const barWidth = similarity * 100;

  return (
    <div className="mb-2 p-2 bg-gray-750 rounded border border-gray-700">
      <div className="flex justify-between items-start mb-1">
        <div className="text-sm text-gray-300">{source}</div>
        <ConfidenceBadge confidence={confidence} />
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1 bg-gray-700 rounded overflow-hidden">
          <div className="h-full bg-orange-500" style={{ width: `${barWidth}%` }} />
        </div>
        <span className="text-xs text-gray-500">{similarity.toFixed(2)}</span>
      </div>
    </div>
  );
};

/**
 * AnomalyAlert - Warning for anomalous data
 */
export const AnomalyAlert = ({ message, severity = 'warning' }) => {
  const bgColor = severity === 'error' ? 'bg-red-900/30 border-red-700' : 'bg-yellow-900/30 border-yellow-700';
  const textColor = severity === 'error' ? 'text-red-300' : 'text-yellow-300';

  return (
    <div className={`${bgColor} border ${textColor} rounded p-3 text-sm mb-3`}>
      {severity === 'error' ? '✗' : '⚠'} {message}
    </div>
  );
};

/**
 * FallbackNotice - Alert when fallback data is used
 */
export const FallbackNotice = ({ reason }) => (
  <div className="bg-blue-900/30 border border-blue-700/50 rounded p-2 mb-2 text-xs text-blue-300">
    ⚠ Fallback data: {reason}
  </div>
);

/**
 * SkeletonLoader - Generic loading placeholder
 */
export const SkeletonLoader = ({ variant = 'card', lines = 3 }) => {
  if (variant === 'text') {
    return (
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="h-4 bg-gray-700 rounded animate-pulse" />
        ))}
      </div>
    );
  }
  if (variant === 'chart') {
    return (
      <div className="space-y-3">
        <div className="h-64 bg-gray-700 rounded animate-pulse" />
        <div className="flex gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex-1 h-12 bg-gray-700 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="bg-gray-750 rounded p-4 space-y-3">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-4 bg-gray-700 rounded animate-pulse" />
      ))}
      <div className="h-32 bg-gray-700 rounded animate-pulse" />
    </div>
  );
};

/**
 * ErrorFallback - Error state with retry button
 */
export const ErrorFallback = ({ error, retry }) => (
  <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-6 text-center">
    <div className="text-red-400 font-semibold mb-2">✗ Error</div>
    <div className="text-red-300 text-sm mb-4">{error?.message || 'Something went wrong'}</div>
    {retry && (
      <button
        onClick={retry}
        className="px-4 py-2 bg-red-700 hover:bg-red-600 text-white rounded transition font-semibold"
      >
        Retry
      </button>
    )}
  </div>
);
