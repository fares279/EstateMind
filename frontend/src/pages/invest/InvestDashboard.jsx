import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import {
  DollarSign, TrendingUp, TrendingDown, ShieldCheck,
  ScanSearch, Plus, ChevronRight, MapPin, ArrowUpRight, Building2,
} from 'lucide-react';
import { getInvestorDashboard } from '../../services/api';

const CARD   = 'rounded-2xl border border-white/10 bg-white/5 p-6';
const ORANGE = '#FF6B35';

const GRADE_COLOR = { A: '#22c55e', B: '#3b82f6', C: '#f59e0b', D: '#ef4444' };
const GRADE_LABEL = { A: 'Prime',   B: 'Good',    C: 'Fair',    D: 'Caution' };
const PIE_COLORS  = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444'];

/* ── KPI card ──────────────────────────────────────────────── */
function KpiCard({ label, value, sub, color = ORANGE, icon: Icon, delta }) {
  return (
    <div className={CARD}>
      <div className="flex items-start justify-between mb-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-500">{label}</p>
        {Icon && (
          <div className="w-8 h-8 rounded-xl bg-white/5 flex items-center justify-center">
            <Icon size={14} className="text-gray-500" />
          </div>
        )}
      </div>
      <p className="text-2xl font-black leading-none" style={{ color }}>{value}</p>
      {sub && <p className="mt-2 text-xs text-gray-500">{sub}</p>}
      {delta != null && (
        <div className={`mt-3 flex items-center gap-1 text-xs font-medium
          ${delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {delta >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
          {delta >= 0 ? '+' : ''}{delta}% since acquisition
        </div>
      )}
    </div>
  );
}

/* ── Chart tooltip ─────────────────────────────────────────── */
const BarTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-[#111827] px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-1">{label}</p>
      <p className="text-white font-semibold">{Math.round(payload[0].value).toLocaleString()} TND</p>
    </div>
  );
};

/* ── Page ──────────────────────────────────────────────────── */
export default function InvestDashboard() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate              = useNavigate();

  useEffect(() => {
    getInvestorDashboard()
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin h-8 w-8 rounded-full border-2 border-[#FF6B35] border-t-transparent" />
    </div>
  );

  const p       = data?.portfolio      || {};
  const assets  = data?.assets         || [];
  const signals = data?.market_signals || [];
  const hasAssets = assets.length > 0;

  const gradeData = Object.entries(p.grade_distribution || {})
    .filter(([, n]) => n > 0)
    .map(([g, n]) => ({ name: GRADE_LABEL[g] || g, grade: g, value: n }));

  const barData = assets.slice(0, 6).map(e => ({
    name:  (e.asset?.property_name || '').slice(0, 13),
    value: Math.round(e.asset?.current_value_tnd || e.asset?.acquisition_price_tnd || 0),
  }));

  const riskLabel = p.avg_risk_score == null ? '—'
    : p.avg_risk_score < 35 ? 'Low' : p.avg_risk_score < 65 ? 'Moderate' : 'Elevated';
  const riskColor = p.avg_risk_score == null ? ORANGE
    : p.avg_risk_score < 35 ? '#22c55e' : p.avg_risk_score < 65 ? '#f59e0b' : '#ef4444';

  return (
    <div className="space-y-6">

      {/* ── Action bar ─────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Portfolio Overview</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            {hasAssets
              ? `${p.total_assets} ${p.total_assets === 1 ? 'property' : 'properties'} tracked`
              : 'Start by adding your first property'}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => navigate('/invest/scanner')}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-white/15
              text-sm text-gray-300 hover:bg-white/5 transition-colors">
            <ScanSearch size={14} /> Scan a Deal
          </button>
          <button onClick={() => navigate('/invest/portfolio')}
            className="flex items-center gap-2 px-4 py-2 rounded-xl
              bg-[#FF6B35] text-white text-sm font-semibold
              hover:bg-[#e55a1f] transition-colors shadow-lg shadow-[#FF6B35]/20">
            <Plus size={14} /> Add Property
          </button>
        </div>
      </div>

      {/* ── KPI strip ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard
          label="Portfolio Value"
          value={p.total_value_tnd ? `${(p.total_value_tnd / 1000).toFixed(0)}k TND` : '—'}
          sub={hasAssets ? `Cost ${Math.round((p.total_cost_tnd || 0) / 1000)}k TND` : 'No assets yet'}
          icon={DollarSign}
        />
        <KpiCard
          label="Total Return"
          value={p.total_return_pct != null
            ? `${p.total_return_pct > 0 ? '+' : ''}${p.total_return_pct}%` : '—'}
          sub={p.total_gain_tnd
            ? `${Math.round(p.total_gain_tnd) >= 0 ? '+' : ''}${Math.round(p.total_gain_tnd).toLocaleString()} TND unrealised`
            : 'No return data yet'}
          color={p.total_return_pct == null ? ORANGE
            : p.total_return_pct >= 0 ? '#22c55e' : '#ef4444'}
          icon={TrendingUp}
          delta={p.total_return_pct}
        />
        <KpiCard
          label="Avg Annual Yield"
          value={p.avg_gross_yield_pct != null ? `${p.avg_gross_yield_pct}%` : '—'}
          sub={p.avg_irr_pct != null ? `${p.avg_irr_pct}% estimated IRR` : 'Add assets to calculate'}
          icon={ArrowUpRight}
        />
        <KpiCard
          label="Portfolio Risk"
          value={riskLabel}
          sub={p.avg_risk_score != null ? `Score ${p.avg_risk_score}/100` : 'No assets yet'}
          color={riskColor}
          icon={ShieldCheck}
        />
      </div>

      {/* ── Charts ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">

        {/* Asset values bar */}
        <div className={`xl:col-span-2 ${CARD}`}>
          <p className="text-sm font-semibold text-white mb-6">Asset Values</p>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={barData} barSize={20}
                margin={{ top: 0, right: 4, bottom: 0, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 11 }}
                  axisLine={false} tickLine={false} />
                <YAxis tickFormatter={v => `${(v / 1000).toFixed(0)}k`}
                  tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<BarTip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                <Bar dataKey="value" fill={ORANGE} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex flex-col items-center justify-center h-44 text-center">
              <Building2 size={28} className="text-gray-700 mb-3" />
              <p className="text-sm text-gray-500">Add properties to see value breakdown</p>
              <button onClick={() => navigate('/invest/portfolio')}
                className="mt-3 text-xs text-[#FF6B35] hover:underline">
                Add your first property →
              </button>
            </div>
          )}
        </div>

        {/* Ratings donut */}
        <div className={CARD}>
          <p className="text-sm font-semibold text-white mb-6">Investment Ratings</p>
          {gradeData.length > 0 ? (
            <>
              <div className="flex justify-center">
                <PieChart width={148} height={148}>
                  <Pie data={gradeData} dataKey="value"
                    innerRadius={42} outerRadius={64} paddingAngle={3} stroke="none">
                    {gradeData.map((e, i) => (
                      <Cell key={e.grade} fill={GRADE_COLOR[e.grade] || PIE_COLORS[i % 4]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10 }}
                    itemStyle={{ color: '#e5e7eb', fontSize: 12 }}
                  />
                </PieChart>
              </div>
              <div className="mt-3 space-y-2">
                {gradeData.map(item => (
                  <div key={item.grade} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full"
                        style={{ background: GRADE_COLOR[item.grade] }} />
                      <span className="text-xs text-gray-400">{item.name}</span>
                    </div>
                    <span className="text-xs font-semibold text-white">{item.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-44 text-center">
              <p className="text-sm text-gray-500">No rated assets yet</p>
              <button onClick={() => navigate('/invest/portfolio')}
                className="mt-3 text-xs text-[#FF6B35] hover:underline">
                Add property →
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Bottom: Markets + Portfolio ───────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

        {/* Top markets */}
        <div className={CARD}>
          <div className="flex items-center justify-between mb-5">
            <p className="text-sm font-semibold text-white">Top Markets Right Now</p>
            <button onClick={() => navigate('/invest/opportunities')}
              className="flex items-center gap-1 text-xs font-medium text-[#FF6B35] hover:underline">
              View all <ChevronRight size={12} />
            </button>
          </div>
          {signals.length > 0 ? (
            <div className="space-y-2">
              {signals.slice(0, 5).map((s, i) => (
                <button key={i} onClick={() => navigate('/invest/opportunities')}
                  className="w-full flex items-center justify-between px-4 py-3 rounded-xl
                    bg-white/3 border border-white/8 hover:border-white/15
                    hover:bg-white/5 transition-all text-left">
                  <div className="flex items-center gap-3">
                    <div className="w-7 h-7 rounded-lg bg-[#FF6B35]/10
                      flex items-center justify-center flex-shrink-0">
                      <MapPin size={12} className="text-[#FF6B35]" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{s.delegation_name}</p>
                      <p className="text-xs text-gray-500">{s.governorate}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-green-400">
                      +{(s.annual_trend_pct || 0).toFixed(1)}%/yr
                    </p>
                    <p className="text-xs text-gray-500">
                      {Math.round(s.price_avg || 0).toLocaleString()} TND/m²
                    </p>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500 text-center py-10">Loading market data…</p>
          )}
        </div>

        {/* Portfolio snapshot */}
        <div className={CARD}>
          <div className="flex items-center justify-between mb-5">
            <p className="text-sm font-semibold text-white">My Properties</p>
            <button onClick={() => navigate('/invest/portfolio')}
              className="flex items-center gap-1 text-xs font-medium text-[#FF6B35] hover:underline">
              Manage <ChevronRight size={12} />
            </button>
          </div>
          {assets.length > 0 ? (
            <div className="space-y-2">
              {assets.slice(0, 5).map((entry, i) => {
                const a  = entry.asset || {};
                const s  = entry.score || {};
                const gc = GRADE_COLOR[s.grade];
                const gain = a.unrealized_gain_pct ?? 0;
                return (
                  <div key={i}
                    className="flex items-center justify-between px-4 py-3 rounded-xl
                      bg-white/3 border border-white/8">
                    <div className="flex items-center gap-3 min-w-0">
                      {s.grade ? (
                        <span className="flex-shrink-0 text-[10px] font-black w-5 h-5
                          rounded-md flex items-center justify-center"
                          style={{ background: gc + '22', color: gc, border: `1px solid ${gc}35` }}>
                          {s.grade}
                        </span>
                      ) : <span className="flex-shrink-0 w-5 h-5 rounded-md bg-white/5" />}
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-white truncate">{a.property_name}</p>
                        <p className="text-xs text-gray-500 truncate">
                          {[a.delegation, a.governorate].filter(Boolean).join(', ')}
                        </p>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0 ml-4">
                      <p className="text-sm font-semibold" style={{ color: ORANGE }}>
                        {s.yield?.gross_yield_pct != null ? `${s.yield.gross_yield_pct}%` : '—'}
                      </p>
                      <p className={`text-xs ${gain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {gain > 0 ? '+' : ''}{gain}%
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Building2 size={28} className="text-gray-700 mb-3" />
              <p className="text-sm text-gray-500 mb-4">No properties added yet</p>
              <button onClick={() => navigate('/invest/portfolio')}
                className="px-4 py-2 rounded-xl bg-[#FF6B35] text-white text-xs
                  font-semibold hover:bg-[#e55a1f] transition-colors">
                Add First Property
              </button>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
