import React, { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { MapPin, TrendingUp, ChevronUp, ChevronDown } from 'lucide-react';
import { getInvestorOpportunities } from '../../services/api';

/* ── Design tokens ─────────────────────────────────────────── */
const CARD   = 'rounded-2xl border border-white/10 bg-white/5';
const ORANGE = '#FF6B35';
const SELECT_CLS = 'rounded-xl border border-white/20 bg-[#111827] px-3 py-1.5 text-xs text-white ' +
  'focus:outline-none focus:border-[#FF6B35]/60 focus:ring-1 focus:ring-[#FF6B35]/30 transition-colors';

const PTYPES = [
  { value: 'apartment',  label: 'Apartments'  },
  { value: 'house',      label: 'Houses'       },
  { value: 'commercial', label: 'Commercial'   },
  { value: 'land',       label: 'Land'         },
];

const GRADE_COLOR = { A: '#22c55e', B: '#3b82f6', C: '#f59e0b', D: '#ef4444' };
const GRADE_LABEL = { A: 'Prime',   B: 'Good',    C: 'Fair',    D: 'Caution' };

const POSITION = {
  SEVERELY_UNDERVALUED: { label: 'Strong Value',  color: '#22c55e' },
  UNDERVALUED:          { label: 'Below Market',  color: '#86efac' },
  FAIRLY_PRICED:        { label: 'Fair Price',    color: '#f59e0b' },
  OVERPRICED:           { label: 'Above Market',  color: '#ef4444' },
};

const SIGNAL = {
  BUY_NOW: { label: 'Buy Now', color: '#22c55e' },
  WAIT:    { label: 'Hold',    color: '#f59e0b' },
  HOLD:    { label: 'Hold',    color: '#f59e0b' },
};

/* ── Score pill ────────────────────────────────────────────── */
function ScorePill({ score }) {
  const color = score >= 65 ? '#22c55e' : score >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-xs font-bold w-6 text-right tabular-nums" style={{ color }}>
        {Math.round(score)}
      </span>
    </div>
  );
}

const BarTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#111827] border border-white/10 rounded-xl px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-1">{label}</p>
      <p className="text-white font-semibold">{Math.round(payload[0].value)}/100</p>
    </div>
  );
};

/* ── Sortable column header ────────────────────────────────── */
function Th({ label, col, sort, asc, onSort, align = 'left' }) {
  const active = sort === col;
  return (
    <th
      onClick={col ? () => onSort(col) : undefined}
      className={`px-4 py-3.5 text-[10px] font-semibold uppercase tracking-wider
        text-${align} select-none
        ${col ? 'cursor-pointer hover:text-gray-300' : ''}
        ${active ? 'text-white' : 'text-gray-500'}`}>
      <span className="inline-flex items-center gap-1">
        {label}
        {active && (asc ? <ChevronUp size={10} /> : <ChevronDown size={10} />)}
      </span>
    </th>
  );
}

/* ── Page ──────────────────────────────────────────────────── */
export default function OpportunitiesPage() {
  const [data,    setData]    = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');
  const [ptype,   setPtype]   = useState('apartment');
  const [limit,   setLimit]   = useState(20);
  const [sort,    setSort]    = useState('opportunity_score');
  const [asc,     setAsc]     = useState(false);

  useEffect(() => {
    setLoading(true);
    setError('');
    getInvestorOpportunities({ property_type: ptype, limit })
      .then(r => setData(r.data || []))
      .catch((e) => {
        setData([]);
        setError(e?.response?.data?.error || 'Could not load opportunities right now.');
      })
      .finally(() => setLoading(false));
  }, [ptype, limit]);

  const sorted = [...data].sort((a, b) =>
    asc ? (a[sort] ?? 0) - (b[sort] ?? 0) : (b[sort] ?? 0) - (a[sort] ?? 0)
  );

  const handleSort = (col) => {
    if (sort === col) setAsc(a => !a);
    else { setSort(col); setAsc(false); }
  };

  const top8 = sorted.slice(0, 8).map(d => ({
    name:  d.delegation.length > 12 ? d.delegation.slice(0, 12) + '…' : d.delegation,
    score: Math.round(d.opportunity_score || 0),
  }));

  const bestYield = sorted.length ? Math.max(...sorted.map(d => d.gross_yield_pct || 0)) : 0;
  const buyCount  = sorted.filter(d => d.buy_signal === 'BUY_NOW').length;

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Market Opportunities</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Best locations ranked by investment score
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Type tabs */}
          <div className="flex gap-1 p-1 rounded-xl border border-white/10 bg-white/5">
            {PTYPES.map(t => (
              <button key={t.value} onClick={() => setPtype(t.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                  ${ptype === t.value
                    ? 'bg-[#FF6B35] text-white'
                    : 'text-gray-400 hover:text-white'}`}>
                {t.label}
              </button>
            ))}
          </div>
          <select
            className={SELECT_CLS}
            value={limit} onChange={e => setLimit(parseInt(e.target.value))}>
            <option value={10}>Top 10</option>
            <option value={20}>Top 20</option>
            <option value={50}>Top 50</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin h-7 w-7 rounded-full border-2 border-[#FF6B35] border-t-transparent" />
        </div>
      ) : sorted.length === 0 ? (
        <div className={`${CARD} flex items-center justify-center h-48`}>
          <p className="text-sm text-gray-500">
            {error || 'No data available for this property type'}
          </p>
        </div>
      ) : (
        <>
          {/* ── KPI strip ──────────────────────────────────────── */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            {[
              {
                label: 'Top Location',
                value: sorted[0]?.delegation,
                sub:   sorted[0]?.governorate,
                color: ORANGE,
              },
              {
                label: 'Best Score',
                value: `${Math.round(sorted[0]?.opportunity_score || 0)}/100`,
                sub:   null,
                color: '#22c55e',
              },
              {
                label: 'Best Annual Yield',
                value: `${bestYield.toFixed(1)}%`,
                sub:   null,
                color: ORANGE,
              },
              {
                label: 'Buy Opportunities',
                value: `${buyCount}`,
                sub:   `of ${sorted.length} analysed`,
                color: '#3b82f6',
              },
            ].map(k => (
              <div key={k.label} className={`${CARD} p-5`}>
                <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  {k.label}
                </p>
                <p className="text-xl font-bold leading-tight" style={{ color: k.color }}>{k.value}</p>
                {k.sub && (
                  <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                    {k.label === 'Top Location' && <MapPin size={10} />}
                    {k.sub}
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* ── Top 8 bar chart ────────────────────────────────── */}
          <div className={`${CARD} p-6`}>
            <p className="text-sm font-semibold text-white mb-5">Top Locations by Score</p>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={top8} layout="vertical" barSize={11}
                margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                <XAxis type="number" domain={[0, 100]}
                  tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={88}
                  tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip content={<BarTip />} cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
                <Bar dataKey="score" fill={ORANGE} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* ── Table ──────────────────────────────────────────── */}
          <div className={CARD + ' overflow-hidden'}>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10">
                    <Th label="#"              col={null}                 sort={sort} asc={asc} onSort={handleSort} />
                    <Th label="Location"       col={null}                 sort={sort} asc={asc} onSort={handleSort} />
                    <Th label="Score"          col="opportunity_score"    sort={sort} asc={asc} onSort={handleSort} />
                    <Th label="Rating"         col={null}                 sort={sort} asc={asc} onSort={handleSort} align="center" />
                    <Th label="Signal"         col={null}                 sort={sort} asc={asc} onSort={handleSort} align="center" />
                    <Th label="Annual Yield"   col="gross_yield_pct"      sort={sort} asc={asc} onSort={handleSort} align="right" />
                    <Th label="12m Outlook"    col="forecast_12m_pct"     sort={sort} asc={asc} onSort={handleSort} align="right" />
                    <Th label="Growth/yr"      col="annual_trend_pct"     sort={sort} asc={asc} onSort={handleSort} align="right" />
                    <Th label="Market Position" col={null}                sort={sort} asc={asc} onSort={handleSort} />
                    <Th label="Price / m²"     col="avg_price_pm2"        sort={sort} asc={asc} onSort={handleSort} align="right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {sorted.map((d, i) => {
                    const pos    = POSITION[d.undervaluation] || { label: d.undervaluation || '—', color: '#9ca3af' };
                    const signal = SIGNAL[d.buy_signal]       || { label: d.buy_signal || '—',     color: '#9ca3af' };
                    const gc     = GRADE_COLOR[d.investment_grade];
                    const gl     = GRADE_LABEL[d.investment_grade] || d.investment_grade;
                    const trend  = d.annual_trend_pct || 0;
                    const fcst   = d.forecast_12m_pct || 0;
                    return (
                      <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-4 py-3.5 text-xs text-gray-600 tabular-nums">{i + 1}</td>
                        <td className="px-4 py-3.5">
                          <p className="text-sm font-semibold text-white">{d.delegation}</p>
                          <p className="text-xs text-gray-500">{d.governorate}</p>
                        </td>
                        <td className="px-4 py-3.5">
                          <ScorePill score={d.opportunity_score || 0} />
                        </td>
                        <td className="px-4 py-3.5 text-center">
                          {gc ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-bold"
                              style={{ background: gc + '18', color: gc, border: `1px solid ${gc}25` }}>
                              {gl}
                            </span>
                          ) : <span className="text-xs text-gray-600">—</span>}
                        </td>
                        <td className="px-4 py-3.5 text-center">
                          <span className="text-xs font-semibold" style={{ color: signal.color }}>
                            {signal.label}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-right text-sm font-semibold"
                          style={{ color: ORANGE }}>
                          {(d.gross_yield_pct || 0).toFixed(1)}%
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <span className={`text-xs font-semibold
                            ${fcst >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {fcst >= 0 ? '+' : ''}{fcst.toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <span className={`text-xs font-semibold
                            ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {trend >= 0 ? '+' : ''}{trend.toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="text-xs" style={{ color: pos.color }}>{pos.label}</span>
                        </td>
                        <td className="px-4 py-3.5 text-right text-xs text-gray-300 tabular-nums">
                          {Math.round(d.avg_price_pm2 || 0).toLocaleString()} TND
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
