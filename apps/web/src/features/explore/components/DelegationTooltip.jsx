/**
 * Delegation Tooltip
 * Shows delegation opportunity scores with SHAP drivers
 */

import React from 'react';
import { ConfidenceBadge, SHAPDriver } from '../../../components/common/CommonComponents';

export const DelegationTooltip = ({ delegation }) => {
  const {
    delegation_name,
    opportunity_score,
    confidence_level,
    score_range,
    score_drivers,
    calibration_date,
    directional_accuracy_pct,
  } = delegation;

  // Grade mapping
  const getGrade = (score) => {
    if (score >= 80) return 'A';
    if (score >= 65) return 'B';
    if (score >= 50) return 'C';
    return 'D';
  };

  const gradeBg = {
    A: 'bg-green-600',
    B: 'bg-blue-600',
    C: 'bg-yellow-600',
    D: 'bg-red-600',
  }[getGrade(opportunity_score)];

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 w-80">
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="text-sm text-gray-400">{delegation_name}</div>
          <div className="text-white font-semibold">Opportunity Score</div>
        </div>
        <div className={`text-2xl font-bold px-3 py-1 rounded text-white ${gradeBg}`}>
          {getGrade(opportunity_score)}
        </div>
      </div>

      {/* Score and confidence */}
      <div className="mb-3 p-2 bg-gray-750 rounded">
        <div className="text-2xl font-bold text-white mb-1">{opportunity_score.toFixed(0)}</div>
        <div className="flex items-center justify-between text-xs">
          <ConfidenceBadge confidence={confidence_level} />
          <span className="text-gray-500">
            [{score_range[0].toFixed(0)}, {score_range[1].toFixed(0)}]
          </span>
        </div>
      </div>

      {/* Drivers */}
      <div className="mb-3">
        <div className="text-xs text-gray-500 mb-2 font-semibold">Top Drivers:</div>
        {score_drivers.slice(0, 3).map((driver, i) => (
          <SHAPDriver
            key={i}
            name={driver.name}
            impact={driver.impact}
            direction={driver.direction}
          />
        ))}
      </div>

      {/* Calibration */}
      <div className="border-t border-gray-700 pt-2 text-xs text-gray-600">
        <div>Calibration: {calibration_date}</div>
        <div>Accuracy: {directional_accuracy_pct}%</div>
      </div>
    </div>
  );
};

export default DelegationTooltip;
