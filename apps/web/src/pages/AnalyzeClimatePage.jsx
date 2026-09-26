import React, { useEffect, useState, useCallback } from 'react';
import {
  AlertTriangle, Cloud, Droplets, Flame, Leaf, Loader2,
  RefreshCw, Search, Thermometer, TrendingDown, TrendingUp,
  Wind, Zap,
} from 'lucide-react';
import {
  getClimateDashboard,
  getClimateWeather,
  getClimateScenarios,
  getClimateCompare,
} from '../services/api';

/* ─── helpers ─────────────────────────────────────────────── */
const RISK_COLOR = {
  Low:       { bg: 'bg-green-500/20',  text: 'text-green-400',  border: 'border-green-500/30'  },
  Moderate:  { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  High:      { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/30' },
  'Very High':{ bg: 'bg-red-500/20',   text: 'text-red-400',    border: 'border-red-500/30'    },
};

const riskStyle = (cat) => RISK_COLOR[cat] || RISK_COLOR['Moderate'];

const gradeColor = (g) =>
  ({ A: 'text-green-400', B: 'text-lime-400', C: 'text-yellow-400', D: 'text-orange-400', F: 'text-red-400' }[g] || 'text-gray-400');

const adjColor = (pct) =>
  pct > 0 ? 'text-green-400' : pct < 0 ? 'text-red-400' : 'text-gray-400';

const adjSign = (pct) => (pct > 0 ? `+${pct.toFixed(1)}%` : `${pct.toFixed(1)}%`);

function ScoreBar({ value, max = 100, color = 'bg-[#FF6B35]' }) {
  const pct = Math.min(100, Math.max(0, ((value || 0) / max) * 100));
  return (
    <div className="w-full bg-white/10 rounded-full h-2 mt-1">
      <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ─── sub-components ──────────────────────────────────────── */
function SummaryCards({ data }) {
  const highRisk  = data.filter((r) => ['High', 'Very High'].includes(r.risk_category)).length;
  const avgSustain = data.length
    ? (data.reduce((s, r) => s + (r.sustainability_score || 0), 0) / data.length).toFixed(1)
    : '—';
  const avgAdj = data.length
    ? (data.reduce((s, r) => s + (r.price_adjustment_pct || 0), 0) / data.length).toFixed(1)
    : '—';

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      {[
        { label: 'Governorates', value: data.length, icon: <Leaf size={22} className="text-[#FF6B35]" /> },
        { label: 'High / Very High Risk', value: highRisk, icon: <AlertTriangle size={22} className="text-red-400" /> },
        { label: 'Avg Sustainability', value: avgSustain, icon: <Leaf size={22} className="text-green-400" /> },
        { label: 'Avg Price Adjustment', value: `${avgAdj > 0 ? '+' : ''}${avgAdj}%`, icon: <TrendingDown size={22} className="text-yellow-400" /> },
      ].map(({ label, value, icon }) => (
        <div key={label} className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">{icon}<span className="text-gray-400 text-sm">{label}</span></div>
          <p className="text-2xl font-bold text-white">{value}</p>
        </div>
      ))}
    </div>
  );
}

function GovernorateTable({ data, onSelect, selected }) {
  const [query, setQuery] = useState('');
  const filtered = data.filter((r) =>
    r.governorate.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-xl p-6 mb-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-white">All Governorates</h2>
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter…"
            className="bg-white/10 border border-white/20 rounded-lg pl-9 pr-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#FF6B35]"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-left border-b border-white/10">
              {['Governorate', 'Risk Category', 'Risk Score', 'Sustainability', 'Grade', 'Price Adj.'].map((h) => (
                <th key={h} className="pb-2 pr-4 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const rs = riskStyle(row.risk_category);
              const isSelected = selected === row.governorate;
              return (
                <tr
                  key={row.governorate}
                  onClick={() => onSelect(isSelected ? null : row.governorate)}
                  className={`border-b border-white/5 cursor-pointer transition-colors hover:bg-white/5 ${isSelected ? 'bg-white/10' : ''}`}
                >
                  <td className="py-2.5 pr-4 text-white font-medium">{row.governorate}</td>
                  <td className="pr-4">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${rs.bg} ${rs.text}`}>
                      {row.risk_category || '—'}
                    </span>
                  </td>
                  <td className="pr-4">
                    <div className="flex items-center gap-2">
                      <span className="text-white w-8">{(row.combined_risk_score || 0).toFixed(1)}</span>
                      <ScoreBar value={row.combined_risk_score} max={10} />
                    </div>
                  </td>
                  <td className="pr-4">
                    <div className="flex items-center gap-2">
                      <span className="text-white w-8">{(row.sustainability_score || 0).toFixed(0)}</span>
                      <ScoreBar value={row.sustainability_score} color="bg-green-500" />
                    </div>
                  </td>
                  <td className={`pr-4 font-bold ${gradeColor(row.sustainability_grade)}`}>
                    {row.sustainability_grade || '—'}
                  </td>
                  <td className={`font-semibold ${adjColor(row.price_adjustment_pct)}`}>
                    {row.price_adjustment_pct != null ? adjSign(row.price_adjustment_pct) : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function WeatherPanel({ governorate }) {
  const [weather, setWeather]   = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);

  useEffect(() => {
    if (!governorate) return;
    setLoading(true);
    setError(null);
    getClimateWeather(governorate)
      .then((r) => setWeather(r.data))
      .catch(() => setError('Weather data unavailable'))
      .finally(() => setLoading(false));
  }, [governorate]);

  if (!governorate) return null;

  return (
    <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-xl p-6 mb-8">
      <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <Thermometer size={20} className="text-[#FF6B35]" />
        Live Weather — {governorate}
      </h2>

      {loading && <p className="text-gray-400 flex items-center gap-2"><Loader2 size={16} className="animate-spin" /> Fetching…</p>}
      {error   && <p className="text-red-400 text-sm">{error}</p>}
      {weather && !loading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Temperature', value: `${weather.temperature_2m?.toFixed(1) ?? '—'} °C`, icon: <Thermometer size={18} className="text-orange-400" /> },
            { label: 'Humidity',    value: `${weather.relative_humidity_2m ?? '—'} %`,        icon: <Droplets size={18} className="text-blue-400" /> },
            { label: 'Wind',        value: `${weather.wind_speed_10m?.toFixed(1) ?? '—'} km/h`, icon: <Wind size={18} className="text-cyan-400" /> },
            { label: 'Precip.',     value: `${weather.precipitation ?? '—'} mm`,               icon: <Cloud size={18} className="text-gray-300" /> },
          ].map(({ label, value, icon }) => (
            <div key={label} className="bg-white/5 rounded-lg p-4 flex items-center gap-3">
              {icon}
              <div>
                <p className="text-gray-400 text-xs">{label}</p>
                <p className="text-white font-semibold">{value}</p>
              </div>
            </div>
          ))}

          {weather.heat_index_level && (
            <div className="col-span-2 bg-orange-500/10 border border-orange-500/20 rounded-lg p-4">
              <p className="text-gray-400 text-xs mb-1">Heat Index Level</p>
              <p className={`font-bold ${weather.heat_index_level === 'Danger' ? 'text-red-400' : weather.heat_index_level === 'Extreme Caution' ? 'text-orange-400' : 'text-yellow-400'}`}>
                {weather.heat_index_level}
              </p>
            </div>
          )}
          {weather.flood_index?.level && (
            <div className="col-span-2 bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
              <p className="text-gray-400 text-xs mb-1">Flood Index</p>
              <p className="text-blue-300 font-bold">{weather.flood_index.level}</p>
              {weather.flood_index.note && <p className="text-gray-400 text-xs mt-1">{weather.flood_index.note}</p>}
            </div>
          )}
          {weather.drought_spi?.label && (
            <div className="col-span-2 md:col-span-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4">
              <p className="text-gray-400 text-xs mb-1">Drought (SPI)</p>
              <p className="text-yellow-300 font-bold">{weather.drought_spi.label} — SPI {weather.drought_spi.spi?.toFixed(2)}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ScenariosPanel({ data }) {
  if (!data.length) return null;
  const top = [...data].sort((a, b) => (a.delta_4c || 0) - (b.delta_4c || 0)).slice(0, 8);

  return (
    <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-xl p-6 mb-8">
      <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <Zap size={20} className="text-yellow-400" />
        Climate Scenario Projections
        <span className="text-gray-400 text-sm font-normal ml-2">(worst-affected first)</span>
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-left border-b border-white/10">
              {['Governorate', 'Risk Category', 'Baseline', '+2°C', '+4°C', 'Δ2°C', 'Δ4°C'].map((h) => (
                <th key={h} className="pb-2 pr-4 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {top.map((row) => {
              const rs = riskStyle(row.risk_category);
              return (
                <tr key={row.governorate} className="border-b border-white/5">
                  <td className="py-2.5 pr-4 text-white font-medium">{row.governorate}</td>
                  <td className="pr-4">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${rs.bg} ${rs.text}`}>{row.risk_category || '—'}</span>
                  </td>
                  <td className="pr-4 text-gray-300">{(row.baseline || 0).toFixed(1)}</td>
                  <td className="pr-4 text-gray-300">{(row.plus_2c || 0).toFixed(1)}</td>
                  <td className="pr-4 text-gray-300">{(row.plus_4c || 0).toFixed(1)}</td>
                  <td className={`pr-4 font-semibold ${(row.delta_2c || 0) < 0 ? 'text-red-400' : 'text-green-400'}`}>
                    {(row.delta_2c || 0) > 0 ? '+' : ''}{(row.delta_2c || 0).toFixed(2)}
                  </td>
                  <td className={`font-semibold ${(row.delta_4c || 0) < 0 ? 'text-red-400' : 'text-green-400'}`}>
                    {(row.delta_4c || 0) > 0 ? '+' : ''}{(row.delta_4c || 0).toFixed(2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RiskAxisCards({ data }) {
  if (!data.length) return null;

  const highFlood    = data.filter((r) => ['high','very_high'].includes((r.flood_risk||'').toLowerCase())).length;
  const highHeat     = data.filter((r) => ['high','very_high'].includes((r.heat_stress_risk||'').toLowerCase())).length;
  const highDrought  = data.filter((r) => ['high','very_high'].includes((r.drought_risk||'').toLowerCase())).length;
  const highEarthq   = data.filter((r) => ['high','very_high'].includes((r.earthquake_risk||'').toLowerCase())).length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      {[
        { label: 'Flood Risk (High+)',      count: highFlood,   icon: <Droplets size={24} className="text-blue-400" />,   color: 'border-blue-500/30'   },
        { label: 'Heat Stress (High+)',     count: highHeat,    icon: <Flame size={24} className="text-orange-400" />,    color: 'border-orange-500/30' },
        { label: 'Drought Risk (High+)',    count: highDrought, icon: <Cloud size={24} className="text-yellow-400" />,    color: 'border-yellow-500/30' },
        { label: 'Earthquake Risk (High+)', count: highEarthq,  icon: <AlertTriangle size={24} className="text-red-400" />, color: 'border-red-500/30'  },
      ].map(({ label, count, icon, color }) => (
        <div key={label} className={`glass-card bg-white/10 backdrop-blur-lg border ${color} rounded-xl p-5`}>
          <div className="mb-3">{icon}</div>
          <p className="text-3xl font-bold text-white mb-1">{count}</p>
          <p className="text-gray-400 text-xs">{label}</p>
          <p className="text-gray-500 text-xs">of {data.length} governorates</p>
        </div>
      ))}
    </div>
  );
}

function PriceImpactPanel({ data }) {
  if (!data.length) return null;
  const sorted = [...data].sort((a, b) => (a.price_adjustment_pct || 0) - (b.price_adjustment_pct || 0));

  return (
    <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-xl p-6 mb-8">
      <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <TrendingDown size={20} className="text-[#FF6B35]" />
        Climate Price Impact by Governorate
      </h2>
      <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
        {sorted.map((r) => {
          const pct = r.price_adjustment_pct || 0;
          const barW = Math.min(100, Math.abs(pct) * 4);
          const barColor = pct >= 0 ? 'bg-green-500' : 'bg-red-500';
          return (
            <div key={r.governorate} className="flex items-center gap-3">
              <span className="text-gray-300 text-sm w-28 flex-shrink-0">{r.governorate}</span>
              <div className="flex-1 bg-white/10 rounded-full h-2">
                <div className={`${barColor} h-2 rounded-full transition-all`} style={{ width: `${barW}%` }} />
              </div>
              <span className={`text-sm font-semibold w-14 text-right ${adjColor(pct)}`}>{adjSign(pct)}</span>
              <span className="text-gray-500 text-xs w-20 flex-shrink-0">{r.price_adjustment_label || ''}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── main page ───────────────────────────────────────────── */
export default function AnalyzeClimatePage() {
  const [dashboard, setDashboard]   = useState([]);
  const [scenarios, setScenarios]   = useState([]);
  const [selected, setSelected]     = useState(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([getClimateDashboard(), getClimateScenarios()])
      .then(([dashRes, scenRes]) => {
        setDashboard(dashRes.data.results || []);
        setScenarios(scenRes.data.results || []);
      })
      .catch((err) => {
        console.error('Climate load error:', err);
        setError('Failed to load climate data. Please try again.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] pt-24 px-4 pb-16">
      <div className="max-w-6xl mx-auto">

        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">Climate Risk Intelligence</h1>
            <p className="text-gray-400">Real-time environmental hazard scores, scenario projections, and property price impact for all 24 Tunisian governorates.</p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white border border-white/20 rounded-lg px-3 py-2 transition-colors"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-500/20 border border-red-500/30 rounded-xl p-4 mb-8 text-red-300 flex items-center gap-2">
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="flex items-center justify-center h-64 text-gray-400 gap-3">
            <Loader2 size={28} className="animate-spin text-[#FF6B35]" />
            <span>Loading climate intelligence…</span>
          </div>
        )}

        {!loading && !error && (
          <>
            <SummaryCards data={dashboard} />
            <RiskAxisCards data={dashboard} />
            <PriceImpactPanel data={dashboard} />

            <GovernorateTable
              data={dashboard}
              selected={selected}
              onSelect={setSelected}
            />

            {selected && (
              <WeatherPanel governorate={selected} />
            )}

            <ScenariosPanel data={scenarios} />

            {/* Tip */}
            <p className="text-center text-gray-500 text-sm mt-4">
              Click a governorate row to load live weather data for that region.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
