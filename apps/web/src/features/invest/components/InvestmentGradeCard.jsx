/**
 * Investment Intelligence
 * InvestmentGradeCard - Property investment grade with SHAP drivers
 * PortfolioRiskPanel - Portfolio metrics and risk alerts
 */

import React, { useEffect, useState } from 'react';
import { getInvestmentGrade, getPortfolioRisk } from '../../../services/api-modules';
import { SHAPDriver, AnomalyAlert, SkeletonLoader, ErrorFallback } from '../../../components/common/CommonComponents';

export const InvestmentGradeCard = ({ grade }) => {
  const { grade: gradeLabel, score, location, yield_gross, yield_net, irr, irr_ci, recommendation, confidence, drivers } = grade;

  const gradeBg =
    gradeLabel === 'A' || gradeLabel === 'A+'
      ? 'bg-green-600'
      : gradeLabel.startsWith('B')
        ? 'bg-blue-600'
        : gradeLabel.startsWith('C')
          ? 'bg-yellow-600'
          : 'bg-red-600';

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="text-sm text-gray-400">{location}</div>
          <div className="text-lg font-semibold text-white">Investment Grade</div>
        </div>
        <div className={`text-3xl font-bold px-3 py-1 rounded text-white ${gradeBg}`}>{gradeLabel}</div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4 text-center">
        <div className="bg-gray-750 rounded p-2">
          <div className="text-xs text-gray-500">Gross Yield</div>
          <div className="text-white font-semibold">{(yield_gross * 100).toFixed(2)}%</div>
        </div>
        <div className="bg-gray-750 rounded p-2">
          <div className="text-xs text-gray-500">Net Yield</div>
          <div className="text-white font-semibold">{(yield_net * 100).toFixed(2)}%</div>
        </div>
        <div className="bg-gray-750 rounded p-2">
          <div className="text-xs text-gray-500">IRR 12M</div>
          <div className="text-green-400 font-semibold">{(irr * 100).toFixed(2)}%</div>
          <div className="text-xs text-gray-500">
            [{(irr_ci[0] * 100).toFixed(1)}%, {(irr_ci[1] * 100).toFixed(1)}%]
          </div>
        </div>
      </div>

      <div className="mb-3 p-2 bg-blue-900/30 border border-blue-700/50 rounded text-sm text-blue-300">
        <span className="font-medium">Recommendation:</span> {recommendation} ({Math.round(confidence * 100)}% confidence)
      </div>

      <div className="text-xs text-gray-500 mb-2">Score Drivers:</div>
      {drivers.slice(0, 3).map((driver, i) => (
        <SHAPDriver
          key={i}
          name={driver.name}
          impact={driver.impact}
          direction={driver.direction}
        />
      ))}
    </div>
  );
};

export const PortfolioRiskPanel = ({ portfolioId }) => {
  const [risk, setRisk] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadPortfolioRisk = async () => {
    try {
      setLoading(true);
      const data = await getPortfolioRisk(portfolioId);
      setRisk(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load portfolio risk'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPortfolioRisk();
  }, [portfolioId]);

  if (error) return <ErrorFallback error={error} retry={loadPortfolioRisk} />;
  if (loading) return <SkeletonLoader variant="card" />;
  if (!risk) return null;

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 space-y-4">
      <div className="text-lg font-semibold text-white mb-4">Portfolio Risk Assessment</div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-750 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Annual Volatility</div>
          <div className="text-2xl font-bold text-white">{(risk.volatility * 100).toFixed(2)}%</div>
        </div>
        <div className="bg-gray-750 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Diversification Ratio</div>
          <div className="text-2xl font-bold text-white">{risk.diversification_ratio.toFixed(2)}</div>
          <div className="text-xs text-gray-600">
            {risk.diversification_ratio > 1.5 ? 'Good' : risk.diversification_ratio > 1 ? 'Fair' : 'Poor'}
          </div>
        </div>
      </div>

      {risk.concentration_alert && <AnomalyAlert message={risk.concentration_alert} severity="warning" />}
      {risk.correlation_alert && <AnomalyAlert message={risk.correlation_alert} severity="warning" />}

      <div className="text-xs text-gray-600 border-t border-gray-700 pt-3">
        Correlation quality: <span className="font-semibold">{risk.correlation_quality}</span>
      </div>

      <div className="grid grid-cols-2 gap-4 border-t border-gray-700 pt-4">
        <div>
          <div className="text-xs text-gray-500 mb-1">Blended Yield</div>
          <div className="text-xl font-bold text-white">{(risk.blended_yield * 100).toFixed(2)}%</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 mb-1">Blended IRR 12M</div>
          <div className="text-xl font-bold text-green-400">{(risk.irr * 100).toFixed(2)}%</div>
          <div className="text-xs text-gray-600">
            [{(risk.irr_ci[0] * 100).toFixed(1)}%, {(risk.irr_ci[1] * 100).toFixed(1)}%]
          </div>
        </div>
      </div>
    </div>
  );
};

export default InvestmentGradeCard;
