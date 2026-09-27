/**
 * Multi-Agent Market Simulator
 * ScenarioBuilder - Input interface for simulation parameters
 * SimulationResultPanel - Ensemble results with quantile bands
 */

import React, { useEffect, useRef, useState } from 'react';
import { validateScenario, runSimulation } from '../../../services/api-modules';
import { AnomalyAlert, SkeletonLoader, ErrorFallback } from '../../../components/common/CommonComponents';

export const ScenarioBuilder = ({ onRunSimulation }) => {
  const [scenario, setScenario] = useState({
    interest_rate_shock: 0,
    construction_supply_shock: 0,
    foreign_investment_increase: 0,
    price_growth_target: 0,
  });

  const [validation, setValidation] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const handleValidate = async () => {
    try {
      const result = await validateScenario(scenario);
      setValidation(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Validation failed'));
    }
  };

  const handleRun = async () => {
    if (!validation?.is_valid) {
      handleValidate();
      return;
    }

    try {
      setRunning(true);
      setError(null);
      const result = await runSimulation(scenario);
      onRunSimulation(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Simulation failed'));
    } finally {
      setRunning(false);
    }
  };

  const handleReset = () => {
    setScenario({
      interest_rate_shock: 0,
      construction_supply_shock: 0,
      foreign_investment_increase: 0,
      price_growth_target: 0,
    });
    setValidation(null);
  };

  const RANGES = {
    interest_rate_shock: { min: -5, max: 5, step: 0.5 },
    construction_supply_shock: { min: -40, max: 40, step: 5 },
    foreign_investment_increase: { min: 0, max: 50, step: 5 },
    price_growth_target: { min: -30, max: 30, step: 1 },
  };

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
      <div className="text-lg font-semibold text-white mb-4">Scenario Configuration</div>

      {error && <AnomalyAlert message={error.message} severity="error" />}

      <div className="space-y-6 mb-6">
        {Object.entries(RANGES).map(([key, { min, max, step }]) => (
          <div key={key}>
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm text-gray-300 capitalize">{key.replace(/_/g, ' ')}</label>
              <span className="text-white font-semibold">{scenario[key]}{key === 'interest_rate_shock' ? '%' : ''}</span>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 w-6 text-right">{min}</span>
              <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={scenario[key]}
                onChange={(e) =>
                  setScenario({
                    ...scenario,
                    [key]: parseFloat(e.target.value),
                  })
                }
                className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
              />
              <span className="text-xs text-gray-500 w-6 text-left">{max}</span>
            </div>

            {validation && (
              <div className="mt-1 text-xs">
                {validation.is_valid ? (
                  <span className="text-green-400">✓ Within feasible range</span>
                ) : (
                  <span className="text-orange-400">⚠ Check range</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {validation && (
        <div className="mb-6 p-3 bg-blue-900/20 border border-blue-700/50 rounded-lg">
          <div className="text-sm text-blue-300 mb-1">
            <span className="font-medium">Feasibility: {validation.feasibility_label}</span> ({(validation.feasibility_score * 100).toFixed(0)}/100)
          </div>
          {validation.warnings.length > 0 && (
            <div className="text-xs text-yellow-300">
              {validation.warnings.map((w, i) => (
                <div key={i}>⚠ {w}</div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleValidate}
          disabled={running}
          className="flex-1 px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 disabled:opacity-50 transition"
        >
          Validate
        </button>
        <button
          onClick={handleRun}
          disabled={running || !validation?.can_proceed}
          className="flex-1 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50 transition font-semibold"
        >
          {running ? 'Running...' : '▶ Run Simulation'}
        </button>
        <button
          onClick={handleReset}
          disabled={running}
          className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:text-white disabled:opacity-50 transition"
        >
          Reset
        </button>
      </div>
    </div>
  );
};

const SimulationFanChart = ({ data }) => {
  const canvasRef = useRef(null);
  const width = 600;
  const height = 300;
  const margin = { top: 20, right: 20, bottom: 30, left: 60 };

  useEffect(() => {
    if (!canvasRef.current) return;

    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) return;

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

export const SimulationResultPanel = ({ result, scenarioName = 'Scenario Analysis' }) => {
  const { ensemble_size, monthly_price_bands, growth_rate_12m, probability_price_decline, probability_growth_above_5pct, probability_growth_above_10pct } = result;

  const chartData = monthly_price_bands.p50.map((_, i) => ({
    month: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][i],
    p10: monthly_price_bands.p10[i],
    p25: monthly_price_bands.p25[i],
    p50: monthly_price_bands.p50[i],
    p75: monthly_price_bands.p75[i],
    p90: monthly_price_bands.p90[i],
  }));

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700">
      <div className="p-5 border-b border-gray-700 flex justify-between">
        <div>
          <div className="text-white font-semibold">{scenarioName}</div>
          <div className="text-xs text-gray-500 mt-0.5">{ensemble_size} Monte Carlo runs · 12 months</div>
        </div>
        <div className="text-right">
          <div className="text-orange-400 font-bold text-lg">{growth_rate_12m.median_label}</div>
          <div className="text-xs text-gray-500">median growth</div>
        </div>
      </div>

      <div className="p-5">
        <SimulationFanChart data={chartData} />
      </div>

      <div className="grid grid-cols-3 gap-3 p-5 border-t border-gray-700">
        {[
          { label: 'Pessimistic', value: growth_rate_12m.pessimistic_label, color: 'text-red-400' },
          { label: 'Median', value: growth_rate_12m.median_label, color: 'text-white' },
          { label: 'Optimistic', value: growth_rate_12m.optimistic_label, color: 'text-green-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-gray-750 rounded-lg p-3 text-center">
            <div className="text-xs text-gray-500 mb-1">{label}</div>
            <div className={`font-bold ${color}`}>{value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-3 p-5 text-center border-t border-gray-700">
        <div>
          <div className="text-xs text-gray-500 mb-1">P(decline)</div>
          <div className={`font-bold ${probability_price_decline > 0.2 ? 'text-red-400' : 'text-gray-300'}`}>
            {Math.round(probability_price_decline * 100)}%
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 mb-1">P(growth&gt;5%)</div>
          <div className="text-green-400 font-bold">{Math.round(probability_growth_above_5pct * 100)}%</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 mb-1">P(growth&gt;10%)</div>
          <div className="text-green-400 font-bold">{Math.round(probability_growth_above_10pct * 100)}%</div>
        </div>
      </div>
    </div>
  );
};

export default ScenarioBuilder;
