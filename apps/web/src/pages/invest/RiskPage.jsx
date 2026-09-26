import React, { useState, useEffect } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
} from 'recharts';
import { ShieldCheck, ShieldAlert, ShieldOff, TrendingUp, AlertTriangle, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getInvestorRisk } from '../../services/api';

/* ── Design tokens ─────────────────────────────────────────── */
const CARD   = 'rounded-2xl border border-white/10 bg-white/5';
const ORANGE = '#FF6B35';

const RISK_COLOR  = { Low: '#22c55e', Medium: '#f59e0b', High: '#ef4444', Elevated: '#ef4444' };
const GRADE_COLOR = { A: '#22c55e',   B: '#3b82f6',      C: '#f59e0b',    D: '#ef4444' };
const GRADE_LABEL = { A: 'Prime',     B: 'Good',         C: 'Fair',       D: 'Caution' };
const PIE_COLORS  = [ORANGE, '#3b82f6', '#22c55e', '#a855f7', '#f59e0b', '#06b6d4', '#ec4899'];

/* ── Arc gauge ─────────────────────────────────────────────── */
function RiskGauge({ score }) {
  const color = score < 35 ? '#22c55e' : score < 65 ? '#f59e0b' : '#ef4444';
  const label = score < 35 ? 'Low Risk' : score < 65 ? 'Moderate Risk' : 'Elevated Risk';
  const Icon  = score < 35 ? ShieldCheck : score < 65 ? ShieldAlert : ShieldOff;

  const R   = 52;
  const arc = 2 * Math.PI * R * 0.75;

  return (
    <div className="flex flex-col items-center py-4">
      <div className="relative w-36 h-36">
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-[135deg]">
          <circle cx="60" cy="60" r={R} fill="none"
            stroke="rgba(255,255,255,0.06)" strokeWidth="9"
            strokeDasharray={`${arc} ${2 * Math.PI * R}`} strokeLinecap="round" />
          <circle cx="60" cy="60" r={R} fill="none"
            stroke={color} strokeWidth="9"
            strokeDasharray={`${arc * score / 100} ${2 * Math.PI * R}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.7s ease' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <Icon size={18} style={{ color }} />
          <p className="text-2xl font-bold mt-1" style={{ color }}>{score}</p>
        </div>
      </div>
      <p className="text-[10px] text-gray-500 uppercase tracking-widest mt-1">Risk Score</p>
      <p className="text-sm font-bold mt-1" style={{ color }}>{label}</p>
    </div>
  );
}

/* ── Mini pie ──────────────────────────────────────────────── */
function ExposurePie({ title, data }) {
  return (
    <div className={`${CARD} p-6`}>
      <p className="text-sm font-semibold text-white mb-5">{title}</p>
      {data.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-6">No data</p>
      ) : (
        <div className="flex items-center gap-5">
          <PieChart width={120} height={120}>
            <Pie data={data} dataKey="value" cx={58} cy={58}
              innerRadius={30} outerRadius={54} stroke="none">
              {data.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
            </Pie>
            <Tooltip
              contentStyle={{ background: '#111827', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10 }}
              formatter={v => [`${v}%`]}
            />
          </PieChart>
          <div className="flex-1 space-y-2">
            {data.map((item, i) => (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="flex-shrink-0 h-2 w-2 rounded-full"
                    style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                  <span className="text-xs text-gray-300 truncate capitalize">{item.name}</span>
                </div>
                <span className="text-xs text-gray-400 ml-2 flex-shrink-0">{item.value}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────── */
export default function RiskPage() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate              = useNavigate();

  useEffect(() => {
    getInvestorRisk()
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-72">
      <div className="animate-spin h-7 w-7 rounded-full border-2 border-[#FF6B35] border-t-transparent" />
    </div>
  );

  /* ── Empty state ─────────────────────────────────────────── */
  if (!data || !data.assets?.length) return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Risk Monitor</h1>
        <p className="mt-0.5 text-sm text-gray-500">Portfolio risk and diversification analysis</p>
      </div>
      <div className={`${CARD} flex flex-col items-center justify-center py-20 text-center`}>
        <div className="w-14 h-14 rounded-2xl bg-white/[0.04] flex items-center justify-center mb-5">
          <ShieldAlert size={24} className="text-gray-500" />
        </div>
        <h2 className="text-base font-semibold text-gray-200">No Portfolio to Analyse</h2>
        <p className="text-sm text-gray-500 mt-2 max-w-xs">
          Add properties to your portfolio to see a full risk breakdown
        </p>
        <button onClick={() => navigate('/invest/portfolio')}
          className="mt-6 flex items-center gap-2 px-5 py-2.5 rounded-xl
            bg-[#FF6B35] text-white text-sm font-semibold hover:bg-[#e55a1f]
            transition-colors shadow-lg shadow-[#FF6B35]/20">
          <Plus size={14} /> Go to Portfolio
        </button>
      </div>
    </div>
  );

  const govPie   = Object.entries(data.governorate_exposure   || {}).map(([k, v]) => ({ name: k, value: v }));
  const ptypePie = Object.entries(data.property_type_exposure || {}).map(([k, v]) => ({ name: k, value: v }));

  const avgRisk = data.portfolio_risk_score || 0;
  const hhi     = data.hhi_index            || 0;

  const radarData = [
    { subject: 'Location Mix',  A: Math.min(hhi, 100) },
    { subject: 'Market Risk',   A: avgRisk },
    { subject: 'Asset Mix',     A: ptypePie.length <= 1 ? 70 : ptypePie.length === 2 ? 40 : 18 },
    { subject: 'Liquidity',     A: data.assets.filter(a => a.risk_level === 'High').length / data.assets.length * 100 || 30 },
    { subject: 'Income Risk',   A: data.assets.some(a => (a.yield_pct || 0) < 2) ? 58 : 28 },
    { subject: 'Volatility',    A: Math.min(avgRisk * 0.75 + 12, 100) },
  ];

  const concLevel = data.concentration_risk || 'Low';
  const cc  = RISK_COLOR[concLevel] || '#9ca3af';
  const spreadLabel = hhi < 30 ? 'Well Diversified' : hhi < 60 ? 'Partially Concentrated' : 'Highly Concentrated';
  const spreadColor = hhi < 30 ? '#22c55e' : hhi < 60 ? '#f59e0b' : '#ef4444';

  const tips = concLevel === 'High' ? [
    { icon: AlertTriangle, color: '#ef4444', text: 'Spread investments across 3+ governorates' },
    { icon: AlertTriangle, color: '#ef4444', text: 'Add different property types to reduce sector risk' },
  ] : concLevel === 'Medium' ? [
    { icon: TrendingUp, color: '#f59e0b', text: 'Consider diversifying into another governorate' },
    { icon: TrendingUp, color: '#f59e0b', text: 'A different property type would improve balance' },
  ] : [
    { icon: ShieldCheck, color: '#22c55e', text: 'Portfolio is well-diversified geographically' },
    { icon: ShieldCheck, color: '#22c55e', text: 'Continue monitoring individual asset performance' },
  ];

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold text-white">Risk Monitor</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          {data.assets.length} {data.assets.length === 1 ? 'property' : 'properties'} analysed
        </p>
      </div>

      {/* ── Top row: Gauge + Radar + Concentration ─────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">

        {/* Gauge */}
        <div className={`${CARD} p-6 flex flex-col`}>
          <p className="text-sm font-semibold text-white mb-2">Overall Risk Level</p>
          <div className="flex-1 flex items-center justify-center">
            <RiskGauge score={avgRisk} />
          </div>
          <div className="mt-4 pt-4 border-t border-white/[0.07] grid grid-cols-3 gap-2 text-center">
            {[
              { label: 'Low',      range: '0–34',  color: '#22c55e', active: avgRisk < 35 },
              { label: 'Moderate', range: '35–64', color: '#f59e0b', active: avgRisk >= 35 && avgRisk < 65 },
              { label: 'Elevated', range: '65+',   color: '#ef4444', active: avgRisk >= 65 },
            ].map(t => (
              <div key={t.label}
                className={`rounded-xl px-2 py-2 border transition-all
                  ${t.active ? '' : 'opacity-30'}`}
                style={t.active
                  ? { borderColor: t.color + '50', background: t.color + '10' }
                  : { borderColor: 'rgba(255,255,255,0.05)' }}>
                <p className="text-xs font-bold" style={{ color: t.color }}>{t.label}</p>
                <p className="text-[10px] text-gray-500">{t.range}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Radar */}
        <div className={`${CARD} p-6`}>
          <p className="text-sm font-semibold text-white mb-4">Risk Dimensions</p>
          <ResponsiveContainer width="100%" height={210}>
            <RadarChart data={radarData} margin={{ top: 4, right: 20, bottom: 4, left: 20 }}>
              <PolarGrid stroke="rgba(255,255,255,0.07)" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: '#9ca3af', fontSize: 10 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
              <Radar name="Risk" dataKey="A"
                stroke={ORANGE} fill={ORANGE} fillOpacity={0.18}
                strokeWidth={1.5} dot={{ fill: ORANGE, r: 2 }} />
            </RadarChart>
          </ResponsiveContainer>
          <p className="text-[10px] text-gray-600 text-center">Smaller area = lower risk</p>
        </div>

        {/* Concentration */}
        <div className={`${CARD} p-6`}>
          <p className="text-sm font-semibold text-white mb-5">Portfolio Spread</p>
          <div className="space-y-4">

            <div className="flex items-center justify-between">
              <p className="text-xs text-gray-500">Diversification</p>
              <span className="text-xs font-bold" style={{ color: spreadColor }}>{spreadLabel}</span>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-xs text-gray-500">Concentration Level</p>
                <span className="px-2 py-0.5 rounded-lg text-xs font-bold"
                  style={{ background: cc + '18', color: cc, border: `1px solid ${cc}25` }}>
                  {concLevel}
                </span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
                <div className="h-full rounded-full transition-all"
                  style={{ width: `${Math.min(hhi, 100)}%`,
                    background: hhi < 30 ? '#22c55e' : hhi < 60 ? '#f59e0b' : '#ef4444' }} />
              </div>
            </div>

            <div className="pt-3 border-t border-white/[0.07] space-y-3">
              <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                Recommendations
              </p>
              {tips.map((t, i) => (
                <div key={i} className="flex items-start gap-2">
                  <t.icon size={12} style={{ color: t.color }} className="flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-gray-400">{t.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Exposure pies ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ExposurePie title="Geographic Exposure" data={govPie} />
        <ExposurePie title="Asset Type Exposure" data={ptypePie} />
      </div>

      {/* ── Asset table ─────────────────────────────────────────── */}
      <div className={CARD + ' overflow-hidden'}>
        <div className="px-6 py-4 border-b border-white/10">
          <p className="text-sm font-semibold text-white">Asset Risk Breakdown</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/[0.06]">
                {['Property', 'Rating', 'Risk Level', 'Risk Score', 'Annual Yield', 'Est. Return'].map(h => (
                  <th key={h} className="px-5 py-3.5 text-left text-[10px] font-semibold
                    text-gray-500 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {data.assets.map((a, i) => {
                const gc  = GRADE_COLOR[a.grade]      || '#9ca3af';
                const gl  = GRADE_LABEL[a.grade]      || a.grade;
                const rc  = RISK_COLOR[a.risk_level]  || '#9ca3af';
                const pct = Math.min(a.risk_score || 0, 100);
                return (
                  <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-4 text-sm font-semibold text-white">{a.name}</td>
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-lg
                        text-xs font-bold"
                        style={{ background: gc + '18', color: gc, border: `1px solid ${gc}25` }}>
                        {gl}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-sm font-semibold" style={{ color: rc }}>
                        {a.risk_level}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
                          <div className="h-full rounded-full"
                            style={{ width: `${pct}%`,
                              background: pct < 35 ? '#22c55e' : pct < 65 ? '#f59e0b' : '#ef4444' }} />
                        </div>
                        <span className="text-xs text-gray-400 w-6 tabular-nums">{pct}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-sm font-semibold" style={{ color: ORANGE }}>
                      {a.yield_pct != null ? `${a.yield_pct}%` : '—'}
                    </td>
                    <td className="px-5 py-4 text-sm font-semibold text-blue-400">
                      {a.irr_pct != null ? `${a.irr_pct}%` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
