/**
 * Formatting utilities for dates, prices, and other common formats
 */

export const formatPrice = (price, decimals = 0) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'TND',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(price);
};

export const formatPriceCompact = (price) => {
  if (price >= 1000000) {
    return `${(price / 1000000).toFixed(1)}M TND`;
  }
  if (price >= 1000) {
    return `${(price / 1000).toFixed(0)}K TND`;
  }
  return `${price} TND`;
};

export const formatRelativeTime = (timestamp) => {
  const now = new Date();
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
};

export const formatDate = (date) => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

export const formatDateTime = (date) => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const formatPercentage = (value, decimals = 1) => {
  return `${(value * 100).toFixed(decimals)}%`;
};

export const formatMonthLabel = (index) => {
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  return months[index % 12];
};

export const getFreshnessStatus = (
  timestamp,
  staleDays = 7,
  warnHours = 24
) => {
  const now = new Date();
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
  const diffHours = (now.getTime() - date.getTime()) / 3600000;
  const diffDays = diffHours / 24;

  if (diffDays > staleDays) return 'CRITICAL';
  if (diffDays > staleDays / 2) return 'STALE';
  if (diffHours > warnHours) return 'WARN';
  return 'FRESH';
};

export const getConfidenceColor = (confidence) => {
  if (confidence >= 0.75) return 'text-green-400';
  if (confidence >= 0.55) return 'text-yellow-400';
  return 'text-red-400';
};

export const getConfidenceLabel = (confidence) => {
  if (confidence >= 0.75) return 'HIGH';
  if (confidence >= 0.55) return 'MEDIUM';
  return 'LOW';
};

export const getConfidenceBgColor = (label) => {
  const colors = {
    HIGH: 'bg-green-500',
    MEDIUM: 'bg-yellow-500',
    LOW: 'bg-red-500',
  };
  return colors[label];
};

export const getGradeLabel = (score) => {
  if (score >= 85) return 'A+';
  if (score >= 80) return 'A';
  if (score >= 75) return 'A-';
  if (score >= 70) return 'B+';
  if (score >= 65) return 'B';
  if (score >= 60) return 'B-';
  if (score >= 55) return 'C+';
  if (score >= 50) return 'C';
  if (score >= 45) return 'C-';
  return 'D';
};

export const getTrendIcon = (change) => {
  if (change > 0) return '↑';
  if (change < 0) return '↓';
  return '→';
};

export const getTrendColor = (change) => {
  if (change > 0) return 'text-green-400';
  if (change < 0) return 'text-red-400';
  return 'text-gray-400';
};

export const climbingBars = (value, max = 10) => {
  const bars = Math.min(Math.max(Math.round((value / max) * 10), 0), 10);
  const filled = '█'.repeat(bars);
  const empty = '░'.repeat(10 - bars);
  return `${filled}${empty}`;
};
