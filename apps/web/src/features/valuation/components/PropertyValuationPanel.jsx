/**
 * Valuation with SHAP Drivers
 * Shows estimated price with confidence bands and explainability
 */

import React, { useState, useEffect } from 'react';
import { ConfidenceBand, ProvenanceBlock, SHAPDriver, SkeletonLoader } from '../../../components/common/CommonComponents';

export const ValuationResultPanel = ({ result }) => {
  const [activeTab, setActiveTab] = useState('drivers');

  // Handle both old and new API response formats
  const estimated_price = result?.estimated_price;
  const lower_bound = result?.lower_bound || result?.confidence_band?.lower;
  const upper_bound = result?.upper_bound || result?.confidence_band?.upper;
  const confidence = result?.confidence ?? result?.confidence_score;
  const confidence_level = result?.confidence_level;
  const model_name = result?.model_name;
  const training_date = result?.model_version || result?.trained_date;
  
  // SHAP drivers - comprehensive fallback chain to find driver data from API response
  // Backend returns: features_impact (primary), top_drivers (summary), or shap.contributions (fallback)
  const drivers = result?.shap_drivers                    // Normalized field from ValuatePage
                  || result?.features_impact             // Direct API response
                  || result?.top_drivers                 // Alternative from backend
                  || result?.shap?.contributions         // SHAP object structure
                  || [];

  // Debug logging
  useEffect(() => {
    console.log('PropertyValuationPanel result:', result);
    console.log('Drivers array:', drivers);
    console.log('Result keys:', result ? Object.keys(result) : 'no result');
  }, [result, drivers]);

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <div className="text-sm text-gray-400">Estimated Price</div>
          <div className="text-4xl font-bold text-white">
            {estimated_price ? Math.round(estimated_price).toLocaleString('en-US') : 'N/A'} <span className="text-lg text-gray-500">TND</span>
          </div>
        </div>
      </div>

      {/* Confidence and Metadata */}
      {confidence && (
        <div className="mb-4 p-3 bg-gray-700/50 rounded-lg">
          <div className="text-sm text-gray-400 mb-2">Confidence: {confidence}% ({confidence_level})</div>
          {model_name && <div className="text-xs text-gray-500">Model: {model_name}</div>}
          {training_date && <div className="text-xs text-gray-500">Version: {training_date}</div>}
        </div>
      )}

      {/* Confidence Band */}
      {lower_bound && upper_bound && (
        <div className="mb-4">
          <div className="text-sm text-gray-400 mb-2">Price Range</div>
          <div className="flex gap-4">
            <div className="flex-1 bg-green-900/30 rounded p-3">
              <div className="text-xs text-gray-400">Lower</div>
              <div className="text-lg font-bold text-green-400">{Math.round(lower_bound).toLocaleString('en-US')} TND</div>
            </div>
            <div className="flex-1 bg-red-900/30 rounded p-3">
              <div className="text-xs text-gray-400">Upper</div>
              <div className="text-lg font-bold text-red-400">{Math.round(upper_bound).toLocaleString('en-US')} TND</div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 mb-4 border-b border-gray-700">
        {['drivers', 'scenarios', 'comparables'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-2 px-2 font-semibold text-sm transition ${
              activeTab === tab ? 'border-b-2 border-orange-500 text-orange-400' : 'text-gray-400'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'drivers' && (
        <div className="space-y-4">
          <div>
            <div className="text-sm text-gray-400 mb-3">Price Drivers:</div>
            {drivers && drivers.length > 0 ? (
              drivers.slice(0, 7).map((driver, i) => (
                <div key={i} className="flex items-center justify-between p-2 bg-gray-700/30 rounded mb-2">
                  <div>
                    <div className="text-sm font-medium text-white">{driver.feature || driver.name}</div>
                    <div className="text-xs text-gray-400">
                      {driver.raw_feature && `(${driver.raw_feature})`}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-green-400">
                      {(driver.impact || driver.delta || 0).toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-400">{driver.percent ? `${driver.percent}%` : ''}</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-gray-500">No driver data available</div>
            )}
          </div>

          {/* Climate Impact if available */}
          {result?.climate_risk_category && (
            <div className="p-3 bg-blue-900/30 border border-blue-700/50 rounded">
              <div className="text-sm text-blue-300 font-medium mb-1">Climate Risk</div>
              <div className="text-blue-300">{result.climate_risk_category}</div>
              {result.climate_adjustment_pct && (
                <div className="text-xs text-blue-300 mt-1">
                  Adjustment: {result.climate_adjustment_pct}%
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'scenarios' && (
        <div className="space-y-2">
          <div className="text-sm text-gray-400 mb-3">Counterfactuals:</div>
          {result?.counterfactuals &&
            result.counterfactuals.map((cf, i) => (
              <div key={i} className="p-2 bg-gray-750 rounded flex justify-between">
                <span className="text-gray-300">{cf.scenario}</span>
                <span className="text-green-400">
                  +{(cf.price_change_pct * 100).toFixed(1)}% (+{cf.price_change_tnd.toLocaleString()} TND)
                </span>
              </div>
            ))}
        </div>
      )}

      {activeTab === 'comparables' && (
        <div className="text-sm text-gray-400 italic">Comparable properties analysis...</div>
      )}

      {/* Provenance */}
      <ProvenanceBlock
        modelName={model_name || 'XGBoost'}
        trainedDate={result?.trained_date || result?.model_version || 'Latest'}
        dataSnapshot={result?.data_snapshot_date || new Date().toLocaleDateString()}
        method={result?.climate_source || 'delegation_composite_score'}
      />
    </div>
  );
};

export default ValuationResultPanel;
