/**
 * AnalyzePage — Market Intelligence Hub
 * Tab 1: Market Dashboard — all 278 delegations, real prices from CSV
 * Tab 2: Price Outlook — 12 months per delegation: national growth of the INS price index plus the local benchmark deviation
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  AreaChart, Area, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, Legend,
  PieChart, Pie, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Treemap, RadialBarChart, RadialBar, ComposedChart, ReferenceLine,
} from 'recharts';
import {
  AlertTriangle, BarChart3, LayoutDashboard, Building2, Loader2,
  TrendingUp, TrendingDown, Minus, MapPin, Globe, ChevronRight,
  ChevronUp, ChevronDown, Info, Search, ArrowUpDown, Home, Store, Trees, Filter, X, Star, Zap,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { KPIGrid } from '../features/dashboard/components/MarketKPIGrid';
import {
  getForecastGovernorateList,
  getForecastDelegationList,
  getForecastDelegation,
  getForecastNational,
  getForecastMarket,
  getKpiFreshness,
  getMarketDashboard,
} from '../services/api';

// ── Constants ─────────────────────────────────────────────────────────────────
const ORANGE = '#FF6B35';
const CARD   = 'rounded-2xl border border-white/10 bg-white/5 p-6';

const CHART_COLORS = [
  '#FF6B35','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7',
  '#DDA0DD','#85C1E9','#F0B27A','#82E0AA','#AED6F1',
  '#F1948A','#A9CCE3','#C39BD3','#F9E79F','#A3E4D7',
  '#F5CBA7','#AED6F1','#D2B4DE','#ABEBC6','#FAD7A0',
];

const PROP_TYPES = [
  { id: 'apartment', label: 'Apartment', icon: Building2 },
  { id: 'house',     label: 'House',     icon: Home      },
  { id: 'commercial',label: 'Commercial',icon: Store     },
  { id: 'land',      label: 'Land',      icon: Trees     },
];

const SEL_CLS =
  'w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2.5 text-sm text-white ' +
  'focus:border-[#FF6B35]/60 focus:outline-none focus:ring-1 focus:ring-[#FF6B35]/30 ' +
  'transition-colors cursor-pointer';

const fmt = (n) => (n ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 });
const fmtP = (n) => `${n > 0 ? '+' : ''}${(n ?? 0).toFixed(1)}%`;
// Axis ticks in thousands without duplicates: 0, 500, 1k, 1.5k, 2k… (whole thousands
// used to repeat labels: '2k' for both 1,500 and 2,000)
const fmtK = (v) => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(v % 1000 === 0 ? 0 : 1)}k` : `${v}`);
// One definition of growing / stable / declining for the whole page (it used 0%, 2% and a
// third rule in different places, so the counts disagreed)
const TREND_BAND = 2;
const trendClass = (t) => ((t ?? 0) >= TREND_BAND ? 'growing' : (t ?? 0) <= -TREND_BAND ? 'declining' : 'stable');

// Why a request failed, in words: the server's own message, or that it was unreachable.
function loadErrorReason(err) {
  if (!err?.response) return 'The server could not be reached. Check your connection.';
  return err.response.data?.error || `The server returned an error (${err.response.status}).`;
}

function LoadError({ message, onRetry }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
      <AlertTriangle size={15} className="flex-shrink-0" />
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="rounded-lg border border-red-400/40 px-3 py-1 text-xs font-semibold hover:bg-red-500/10">
          Try again
        </button>
      )}
    </div>
  );
}

function FreshnessPill({ freshness }) {
  if (!freshness) return null;
  const status = freshness.status;
  if (status === 'fresh') {
    return <span className="text-[10px] font-semibold text-green-400">Updated {freshness.age_human}</span>;
  }
  if (status === 'warn') {
    return <span className="text-[10px] font-semibold text-amber-400">Warning: {freshness.age_human}</span>;
  }
  if (status === 'stale') {
    return <span className="text-[10px] font-semibold text-red-400">Stale: {freshness.age_human}</span>;
  }
  return <span className="text-[10px] font-semibold text-gray-500">Freshness unknown</span>;
}

// ── Shared atoms ──────────────────────────────────────────────────────────────
function TrendBadge({ growth }) {
  if (growth >= 2)
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-green-500/30 bg-green-500/15 px-2.5 py-1 text-xs font-semibold text-green-400">
        <TrendingUp size={11} /> {fmtP(growth)}
      </span>
    );
  if (growth <= -2)
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/15 px-2.5 py-1 text-xs font-semibold text-red-400">
        <TrendingDown size={11} /> {fmtP(growth)}
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-gray-500/30 bg-gray-500/15 px-2.5 py-1 text-xs font-semibold text-gray-400">
      <Minus size={11} /> {fmtP(growth)}
    </span>
  );
}

function MetricCard({ label, value, sub, highlight }) {
  return (
    <div className={`rounded-xl border p-4 text-center ${
      highlight ? 'border-[#FF6B35]/30 bg-[#FF6B35]/5' : 'border-white/10 bg-white/5'
    }`}>
      <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-black ${highlight ? 'text-[#FF6B35]' : 'text-white'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}

function PropTypePills({ value, onChange }) {
  return (
    <div className="flex flex-wrap gap-2">
      {PROP_TYPES.map(({ id, label, icon: Icon }) => (
        <button key={id} onClick={() => onChange(id)}
          className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-all ${
            value === id
              ? 'border-[#FF6B35] bg-[#FF6B35]/15 text-[#FF6B35]'
              : 'border-white/15 bg-white/5 text-gray-400 hover:border-white/30 hover:text-white'
          }`}>
          <Icon size={11} /> {label}
        </button>
      ))}
    </div>
  );
}

function SortTh({ label, col, active, dir, onClick }) {
  return (
    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 cursor-pointer select-none hover:text-white transition-colors"
      onClick={onClick}>
      <span className="flex items-center gap-1">
        {label}
        {active
          ? (dir === 'asc' ? <ChevronUp size={12} className="text-[#FF6B35]" /> : <ChevronDown size={12} className="text-[#FF6B35]" />)
          : <ArrowUpDown size={12} className="text-gray-600" />}
      </span>
    </th>
  );
}

function ForecastTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="rounded-xl border border-white/20 bg-[#111827] px-4 py-3 shadow-2xl text-xs">
      <p className="font-bold text-white mb-1.5">{label}</p>
      <p className="text-[#FF6B35]">Forecast: <strong>{fmt(d?.price_per_m2)} TND/m²</strong></p>
      <p className="text-gray-500 mt-0.5">Confidence band: {fmt(d?.lower)} – {fmt(d?.upper)} TND/m²</p>
    </div>
  );
}

// ── Price Forecast Tab ─────────────────────────────────────────────────────────
function PriceForecastSection() {
  const [propType,     setPropType]     = useState('apartment');
  const [governorates, setGovernorates] = useState([]);
  const [delegations,  setDelegations]  = useState([]);
  const [selGov,       setSelGov]       = useState('');
  const [selDel,       setSelDel]       = useState('');

  const [nationalData, setNationalData] = useState(null);
  const [forecastData, setForecastData] = useState(null);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState('');

  // Load governorate list once
  useEffect(() => {
    getForecastGovernorateList()
      .then(r => setGovernorates([...new Set(r.data.governorates || [])]))
      .catch(() => {});
  }, []);

  // Load national top-movers when propType changes or no delegation selected
  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    if (selDel) return;
    setLoading(true);
    setError('');
    getForecastNational(propType)
      .then(r => setNationalData(r.data))
      .catch((err) => setError(`National forecast data could not be loaded. ${loadErrorReason(err)}`))
      .finally(() => setLoading(false));
  }, [propType, selDel, reloadKey]);

  const handlePropTypeChange = useCallback((pt) => {
    setPropType(pt);
    setForecastData(null);
    setError('');
    if (selDel) {
      setLoading(true);
      getForecastDelegation(selDel, pt)
        .then(r => setForecastData(r.data))
        .catch(() => setError(`No ${pt} forecast for ${selDel}.`))
        .finally(() => setLoading(false));
    }
  }, [selDel]);

  const handleGovChange = useCallback(async (gov) => {
    setSelGov(gov);
    setSelDel('');
    setDelegations([]);
    setForecastData(null);
    setError('');
    if (!gov) return;
    try {
      const res = await getForecastDelegationList(gov);
      setDelegations([...new Set(res.data.delegations || [])]);
    } catch { /* silently */ }
  }, []);

  const handleDelChange = useCallback(async (del) => {
    setSelDel(del);
    setForecastData(null);
    setError('');
    if (!del) return;
    setLoading(true);
    try {
      const res = await getForecastDelegation(del, propType);
      setForecastData(res.data);
    } catch {
      setError(`No forecast data available for ${del} (${propType}).`);
    } finally {
      setLoading(false);
    }
  }, [propType]);

  const chartData = useMemo(() =>
    (forecastData?.months || []).map(m => ({
      month_label:  m.month_label,
      price_per_m2: m.price_per_m2,
      lower:        m.lower,
      upper:        m.upper,
    })), [forecastData]);

  const summary = forecastData?.summary;
  const priceRange = forecastData?.price_range;

  return (
    <section className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-[#FF6B35]/30 bg-[#FF6B35]/10 px-3 py-1.5 text-xs font-semibold text-[#FFB38F] mb-3">
          <BarChart3 size={13} /> Price Outlook · {nationalData?.total_delegations ?? 278} Delegations
          {nationalData?.horizon ? ` · ${nationalData.horizon.start} – ${nationalData.horizon.end}` : ''}
        </div>
        <h2 className="text-3xl font-black text-white">12-Month Price Outlook</h2>
        <p className="mt-1.5 text-gray-400 max-w-2xl">
          Each delegation's reference price per m², grown over the next 12 months at the national rate of the
          official INS property price index{nationalData?.outlook_basis ? ` (${fmtP(nationalData.outlook_basis.national_growth_pct)} a year, data to ${nationalData.outlook_basis.last_quarter})` : ''},
          adjusted by the delegation's own benchmark trend. On the national index since 2005, this method missed
          12-month growth by {nationalData?.outlook_basis ? `${nationalData.outlook_basis.backtest_mae_12m_pp} points` : 'about 4–6 points'} on average;
          local accuracy is not measured, as no delegation price history exists.
        </p>
      </div>

      {/* Controls */}
      <div className={CARD}>
        <p className="text-xs uppercase tracking-widest text-gray-500 mb-3">Property Type</p>
        <PropTypePills value={propType} onChange={handlePropTypeChange} />

        <div className="mt-5 pt-5 border-t border-white/8">
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-3">Location</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-gray-400 block mb-1.5">
                Governorate
              </label>
              <select className={SEL_CLS} value={selGov}
                onChange={e => handleGovChange(e.target.value)}>
                <option value="">— All governorates —</option>
                {governorates.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-gray-400 block mb-1.5">
                Delegation
              </label>
              <select className={SEL_CLS} value={selDel}
                onChange={e => handleDelChange(e.target.value)}
                disabled={!selGov || delegations.length === 0}>
                <option value="">— Select delegation —</option>
                {delegations.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          </div>

          {selGov && (
            <p className="mt-3 text-xs text-gray-500 flex items-center gap-1">
              <Globe size={11} />
              <span className="text-white font-medium ml-1">{selGov}</span>
              {selDel && (
                <><ChevronRight size={11} />
                  <span className="text-[#FF6B35] font-medium">{selDel}</span>
                </>
              )}
              {!selDel && (
                <span className="ml-1 text-gray-600">· {delegations.length} delegations — select one for its forecast</span>
              )}
            </p>
          )}
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-10 gap-3 text-gray-400">
          <Loader2 size={20} className="animate-spin" />
          <span className="text-sm">Loading forecast…</span>
        </div>
      )}
      {!loading && error && (
        <LoadError message={error} onRetry={selDel ? null : () => setReloadKey(k => k + 1)} />
      )}

      {/* Delegation forecast view */}
      {!loading && !error && forecastData && chartData.length > 0 && (
        <div className="space-y-5">
          {/* Metric strip */}
          <div className="grid grid-cols-3 gap-4">
            <MetricCard
              label={chartData[0]?.month_label}
              value={`${fmt(summary?.current_price_per_m2)} TND/m²`}
              sub="Starting point"
            />
            <MetricCard
              label={chartData[Math.min(5, chartData.length - 1)]?.month_label}
              value={`${fmt(summary?.price_6m)} TND/m²`}
              sub={summary?.growth_pct_6m != null ? `${fmtP(summary.growth_pct_6m)} vs ${chartData[0]?.month_label}` : ''}
            />
            <MetricCard
              label={chartData[chartData.length - 1]?.month_label}
              value={`${fmt(summary?.price_12m)} TND/m²`}
              sub={summary?.growth_pct_12m != null ? `${fmtP(summary.growth_pct_12m)} vs ${chartData[0]?.month_label}` : ''}
              highlight
            />
          </div>

          {/* Trend + band note */}
          <div className="flex items-center gap-3 flex-wrap">
            <TrendBadge growth={summary?.growth_pct_12m ?? 0} />
            <span className="text-xs text-gray-500">Shaded area: 90% range, from this method's errors on the national INS price index (2005–2025)</span>
          </div>

          {/* 12-month chart */}
          <div className={CARD}>
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">
              {selDel} — {PROP_TYPES.find(p => p.id === propType)?.label} · Price per m²
            </p>
            <p className="text-xs text-gray-600 mb-5">{chartData[0]?.month_label} → {chartData[chartData.length - 1]?.month_label}</p>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={chartData} margin={{ left: 10, right: 10, top: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={ORANGE} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={ORANGE} stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={ORANGE} stopOpacity={0.1} />
                    <stop offset="95%" stopColor={ORANGE} stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="month_label" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false}
                  tickFormatter={fmtK} />
                <Tooltip content={<ForecastTooltip />} />
                <Area type="monotone" dataKey="upper" stroke="none" fill="url(#bandGrad)" fillOpacity={1} />
                <Area type="monotone" dataKey="lower" stroke="none" fill="white"           fillOpacity={0} />
                <Area type="monotone" dataKey="price_per_m2"
                  stroke={ORANGE} strokeWidth={2.5} fill="url(#priceGrad)" fillOpacity={1}
                  dot={false} activeDot={{ r: 5, fill: ORANGE }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Current market context */}
          {priceRange && (
            <div className={CARD}>
              <p className="text-xs uppercase tracking-widest text-gray-500 mb-4">
                Reference Benchmark · {selDel} ({forecastData.governorate})
              </p>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center">
                  <p className="text-xs text-gray-500 mb-1">Benchmark Min</p>
                  <p className="text-base font-bold text-white">{fmt(priceRange.min)} TND/m²</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-gray-500 mb-1">Benchmark Average</p>
                  <p className="text-base font-bold text-[#FF6B35]">{fmt(priceRange.avg)} TND/m²</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-gray-500 mb-1">Benchmark Max</p>
                  <p className="text-base font-bold text-white">{fmt(priceRange.max)} TND/m²</p>
                </div>
              </div>
              {/* Price bar */}
              {priceRange.min != null && priceRange.max != null && priceRange.avg != null && (
                <div className="relative h-2 bg-white/10 rounded-full overflow-hidden">
                  <div className="absolute inset-0 rounded-full"
                    style={{ background: 'linear-gradient(90deg, #4ECDC4, #FF6B35)' }} />
                  <div className="absolute h-full w-1 bg-white rounded-full -translate-x-1/2"
                    style={{ left: `${((priceRange.avg - priceRange.min) / (priceRange.max - priceRange.min || 1)) * 100}%` }} />
                </div>
              )}
              <div className="flex items-center gap-2 mt-3">
                <TrendBadge growth={priceRange.annual_trend_pct ?? 0} />
                <span className="text-xs text-gray-500">annual benchmark trend</span>
              </div>
              {priceRange.notes && (
                <p className="text-xs text-gray-500 mt-2 flex items-start gap-1.5">
                  <Info size={11} className="mt-0.5 flex-shrink-0" /> {priceRange.notes}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* National view — no delegation selected */}
      {!loading && !error && !selDel && nationalData && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <MetricCard label="Delegations" value={nationalData.total_delegations} sub="One outlook each" />
            <MetricCard label="Horizon"     value="12 months"
              sub={nationalData.horizon ? `${nationalData.horizon.start} – ${nationalData.horizon.end}` : 'From this month'} />
            {/* this card used to say "Accuracy ~97.5%, MAPE 2.5%": a constant, never measured */}
            <MetricCard label="Method" value="INS national trend"
              sub={nationalData.outlook_basis ? `Backtest error ±${nationalData.outlook_basis.backtest_mae_12m_pp} pts / year (national)` : 'Backtested on the INS index'} highlight />
          </div>

          <div className={CARD}>
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">
              Top 10 Delegations — Highest Projected Growth (12 months)
            </p>
            <p className="text-xs text-gray-600 mb-4">
              Select a governorate above, then a delegation, to view its full 12-month price chart.
            </p>
            <div className="space-y-2">
              {(nationalData.top_delegations || []).map((d, i) => (
                <div key={d.delegation}
                  className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/3 px-4 py-2.5">
                  <span className="text-xs text-gray-600 w-5 text-right">#{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white truncate">{d.delegation}</p>
                    <p className="text-xs text-gray-500">{d.governorate}</p>
                  </div>
                  <span className="text-xs text-gray-400 hidden sm:block">
                    {fmt(d.price_jan_tnd)} TND/m² now
                  </span>
                  <TrendBadge growth={d.growth_pct_12m} />
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-gray-600 flex items-center gap-1">
              <Info size={11} /> Select a governorate → delegation above to drill into any of these areas.
            </p>
          </div>
        </div>
      )}

      {!loading && !selDel && !nationalData && !error && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <BarChart3 size={52} className="text-gray-700 mb-4" />
          <p className="text-white font-semibold text-lg">No forecast data available</p>
          <p className="text-sm text-gray-500 mt-2">
            Run <code className="text-[#FFB38F]">python manage.py generate_forecasts</code> to seed the database.
          </p>
        </div>
      )}
    </section>
  );
}

// ── Tunisia SVG Paths ─────────────────────────────────────────────────────────
const TUN_PATHS = [
  { id:'Bizerte',     name:'Bizerte',     lx:68, ly:30,
    d:'M60,8 L110,8 L118,18 L105,32 L88,38 L72,34 L55,24 Z' },
  { id:'Ariana',     name:'Ariana',      lx:128,ly:46,
    d:'M118,38 L138,36 L144,46 L138,56 L122,56 L112,48 Z' },
  { id:'Tunis',      name:'Tunis',       lx:136,ly:62,
    d:'M122,56 L138,56 L148,64 L142,72 L126,70 L118,62 Z' },
  { id:'La Manouba', name:'La Manouba',  lx:108,ly:56,
    d:'M105,44 L118,38 L112,48 L122,56 L118,62 L102,58 L96,50 Z' },
  { id:'Ben Arous',  name:'Ben Arous',   lx:140,ly:80,
    d:'M126,70 L142,72 L148,82 L138,88 L122,82 L118,74 Z' },
  { id:'Nabeul',     name:'Nabeul',      lx:165,ly:72,
    d:'M148,54 L172,54 L178,66 L175,82 L162,92 L148,86 L148,64 Z' },
  { id:'Zaghouan',   name:'Zaghouan',    lx:128,ly:94,
    d:'M118,74 L138,88 L148,86 L145,102 L128,108 L112,100 L108,86 Z' },
  { id:'Béja',       name:'Béja',        lx:70, ly:62,
    d:'M40,44 L82,42 L96,50 L102,58 L88,72 L70,78 L44,68 L36,56 Z' },
  { id:'Jendouba',   name:'Jendouba',    lx:38, ly:80,
    d:'M18,60 L56,56 L70,78 L60,96 L38,100 L16,90 Z' },
  { id:'Kef',        name:'Le Kef',      lx:58, ly:108,
    d:'M38,100 L60,96 L70,78 L88,72 L92,92 L80,118 L52,120 L34,112 Z' },
  { id:'Siliana',    name:'Siliana',     lx:98, ly:106,
    d:'M88,72 L108,86 L112,100 L104,118 L80,118 L92,92 Z' },
  { id:'Kairouan',   name:'Kairouan',    lx:118,ly:136,
    d:'M104,118 L128,108 L145,102 L150,128 L140,150 L118,154 L100,142 Z' },
  { id:'Kasserine',  name:'Kasserine',   lx:72, ly:148,
    d:'M52,120 L80,118 L104,118 L100,142 L88,160 L64,162 L44,148 L46,130 Z' },
  { id:'Sidi Bouzid',name:'Sidi Bouzid', lx:104,ly:170,
    d:'M100,142 L118,154 L122,174 L110,190 L86,190 L76,174 L88,160 Z' },
  { id:'Sousse',     name:'Sousse',      lx:155,ly:128,
    d:'M145,102 L162,92 L175,104 L170,128 L158,140 L150,128 Z' },
  { id:'Monastir',   name:'Monastir',    lx:163,ly:148,
    d:'M158,140 L175,134 L178,150 L166,158 L152,152 Z' },
  { id:'Mahdia',     name:'Mahdia',      lx:163,ly:172,
    d:'M152,152 L166,158 L170,172 L160,184 L148,176 L142,162 Z' },
  { id:'Sfax',       name:'Sfax',        lx:150,ly:200,
    d:'M140,150 L150,128 L170,172 L172,200 L158,216 L138,210 L128,192 Z' },
  { id:'Gafsa',      name:'Gafsa',       lx:84, ly:204,
    d:'M64,162 L88,160 L86,190 L100,210 L90,228 L62,226 L46,208 L50,186 Z' },
  { id:'Tozeur',     name:'Tozeur',      lx:52, ly:252,
    d:'M32,224 L62,226 L70,248 L56,268 L30,262 L24,244 Z' },
  { id:'Kébili',     name:'Kébili',      lx:100,ly:256,
    d:'M62,226 L90,228 L110,240 L108,268 L82,278 L62,262 L70,248 Z' },
  { id:'Gabès',      name:'Gabès',       lx:148,ly:222,
    d:'M128,192 L138,210 L158,216 L164,234 L150,248 L130,242 L118,224 L110,204 Z' },
  { id:'Médenine',   name:'Médenine',    lx:162,ly:268,
    d:'M150,248 L164,234 L180,246 L186,270 L172,290 L150,286 L136,270 Z' },
  { id:'Tataouine',  name:'Tataouine',   lx:140,ly:326,
    d:'M108,268 L136,270 L150,286 L154,320 L140,356 L116,360 L100,330 L96,298 Z' },
];

function dashPriceColor(p) {
  if (!p) return '#1f2937';
  if (p >= 3500) return '#dc2626';
  if (p >= 2800) return '#ea580c';
  if (p >= 2000) return '#d97706';
  if (p >= 1400) return '#16a34a';
  if (p >= 900)  return '#0284c7';
  return '#4338ca';
}

function TunisChoropleth({ delegations, hoveredGov, onHover }) {
  // Aggregate avg price by governorate
  const govMap = useMemo(() => {
    const m = {};
    delegations.forEach(d => {
      if (!m[d.governorate]) m[d.governorate] = { prices:[], trend:0, count:0 };
      m[d.governorate].prices.push(d.price_avg || 0);
      m[d.governorate].trend += (d.annual_trend_pct || 0);
      m[d.governorate].count++;
    });
    const out = {};
    Object.entries(m).forEach(([g, v]) => {
      out[g] = { avg: v.prices.reduce((a,b)=>a+b,0)/v.prices.length, trend: v.trend/v.count, count: v.count };
    });
    return out;
  }, [delegations]);

  return (
    <div className="relative w-full">
      <svg viewBox="0 0 270 408" className="w-full" style={{maxHeight:'460px'}}>
        <rect x="0" y="0" width="270" height="408" fill="transparent"/>
        {TUN_PATHS.map(gov => {
          const info = govMap[gov.id] || govMap[gov.name];
          const fill = dashPriceColor(info?.avg);
          const isHov = hoveredGov === gov.id;
          return (
            <g key={gov.id}
              onMouseEnter={() => onHover(gov.id)}
              onMouseLeave={() => onHover(null)}
              style={{ cursor: 'pointer' }}>
              <path d={gov.d} fill={fill} fillOpacity={isHov ? 1 : 0.72}
                stroke={isHov ? '#fff' : 'rgba(0,0,0,0.5)'} strokeWidth={isHov ? 1.5 : 0.6}
                style={{ transition: 'fill-opacity .15s' }}/>
              <text x={gov.lx} y={gov.ly} fontSize={isHov ? '7.5' : '6'}
                fill={isHov ? '#fff' : 'rgba(255,255,255,0.7)'}
                textAnchor="middle" dominantBaseline="middle"
                style={{ pointerEvents: 'none', fontWeight: isHov ? 700 : 400 }}>
                {gov.name}
              </text>
              {info && isHov && (
                <text x={gov.lx} y={gov.ly + 10} fontSize="5.5" fill="#FFB38F"
                  textAnchor="middle" style={{ pointerEvents: 'none' }}>
                  {Math.round(info.avg).toLocaleString()} TND/m²
                </text>
              )}
            </g>
          );
        })}
        {/* Legend */}
        {[['<900','#4338ca',8],['900-1.4K','#0284c7',50],['1.4-2K','#16a34a',100],['2-2.8K','#d97706',154],['2.8-3.5K','#ea580c',200],['3.5K+','#dc2626',242]].map(([lbl,c,x])=>(
          <g key={lbl} transform={`translate(${x},400)`}>
            <rect x="0" y="-5" width="8" height="8" rx="1.5" fill={c} fillOpacity={0.85}/>
            <text x="10" y="0" fontSize="6" fill="#6b7280">{lbl}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

// ── Market Dashboard Tab ───────────────────────────────────────────────────────
function DashboardSection() {
  const [propType,     setPropType]     = useState('apartment');
  const [marketData,   setMarketData]   = useState(null);
  const [materialized, setMaterialized] = useState(null);
  const [freshness,    setFreshness]    = useState({});
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState('');
  // Filters
  const [filterGov,    setFilterGov]    = useState('');
  const [filterTrend,  setFilterTrend]  = useState('all');
  const [filterCoastal,setFilterCoastal]= useState(false);
  const [priceMin,     setPriceMin]     = useState('');
  const [priceMax,     setPriceMax]     = useState('');
  const [search,       setSearch]       = useState('');
  const [sortKey,      setSortKey]      = useState('price_avg');
  const [sortDir,      setSortDir]      = useState('desc');
  const [hoveredGov,   setHoveredGov]   = useState(null);

  const loadMarket = useCallback((pt) => {
    setLoading(true); setError('');
    getForecastMarket(pt)
      .then(r => setMarketData(r.data))
      .catch((err) => setError(`Market data could not be loaded. ${loadErrorReason(err)}`))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadMarket(propType); }, [propType, loadMarket]);

  // public market-wide figures (these calls used to need a login)
  useEffect(() => {
    getKpiFreshness().then((r) => setFreshness(r.data || {})).catch(() => setFreshness({}));
    getMarketDashboard().then((r) => setMaterialized(r.data || null)).catch(() => setMaterialized(null));
  }, []);

  const allDelegations = marketData?.delegations || [];

  // Unique governorates for filter
  const govOptions = useMemo(() =>
    [...new Set(allDelegations.map(d => d.governorate).filter(Boolean))].sort(),
    [allDelegations]);

  // Apply filters
  const filtered = useMemo(() => {
    return allDelegations.filter(d => {
      if (filterGov && d.governorate !== filterGov) return false;
      if (filterTrend !== 'all' && trendClass(d.annual_trend_pct) !== filterTrend) return false;
      if (filterCoastal && !d.is_coastal) return false;
      if (priceMin && (d.price_avg || 0) < parseFloat(priceMin)) return false;
      if (priceMax && (d.price_avg || 0) > parseFloat(priceMax)) return false;
      if (search && !d.delegation?.toLowerCase().includes(search.toLowerCase()) &&
          !d.governorate?.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [allDelegations, filterGov, filterTrend, filterCoastal, priceMin, priceMax, search]);

  const activeFilters = [filterGov, filterTrend !== 'all' && filterTrend, priceMin && `≥${priceMin}`, priceMax && `≤${priceMax}`].filter(Boolean);

  // ── Derived datasets ───────────────────────────────────────────────────────
  const sorted = useMemo(() => [...filtered].sort((a,b) => {
    const av = a[sortKey] ?? (sortDir==='asc' ? Infinity : -Infinity);
    const bv = b[sortKey] ?? (sortDir==='asc' ? Infinity : -Infinity);
    return sortDir === 'asc' ? av - bv : bv - av;
  }), [filtered, sortKey, sortDir]);

  const top20Price = useMemo(() =>
    [...filtered].sort((a,b) => (b.price_avg||0)-(a.price_avg||0)).slice(0,20), [filtered]);

  const top10Growing = useMemo(() =>
    [...filtered].filter(d=>trendClass(d.annual_trend_pct)==='growing')
      .sort((a,b)=>(b.annual_trend_pct||0)-(a.annual_trend_pct||0)).slice(0,10), [filtered]);

  const top10Declining = useMemo(() =>
    [...filtered].filter(d=>trendClass(d.annual_trend_pct)==='declining')
      .sort((a,b)=>(a.annual_trend_pct||0)-(b.annual_trend_pct||0)).slice(0,10), [filtered]);

  const scatterData = useMemo(() =>
    filtered.filter(d => d.price_avg && d.annual_trend_pct != null), [filtered]);

  // Price bracket distribution (pie)
  const priceBrackets = useMemo(() => {
    const brackets = [
      { name:'<1,000', range:[0,1000], color:'#4338ca' },
      { name:'1,000–1,500', range:[1000,1500], color:'#0284c7' },
      { name:'1,500–2,000', range:[1500,2000], color:'#16a34a' },
      { name:'2,000–2,500', range:[2000,2500], color:'#d97706' },
      { name:'2,500–3,000', range:[2500,3000], color:'#ea580c' },
      { name:'3,000+', range:[3000,Infinity], color:'#dc2626' },
    ];
    return brackets.map(b => ({
      ...b,
      value: filtered.filter(d => (d.price_avg||0) >= b.range[0] && (d.price_avg||0) < b.range[1]).length,
    })).filter(b => b.value > 0);
  }, [filtered]);

  // Governorate-level aggregation for radar
  const govAgg = useMemo(() => {
    const m = {};
    filtered.forEach(d => {
      if (!m[d.governorate]) m[d.governorate] = { prices:[], trends:[], count:0, coastal: false };
      // a governorate counts as coastal if any of its delegations is
      m[d.governorate].coastal = m[d.governorate].coastal || Boolean(d.is_coastal);
      m[d.governorate].prices.push(d.price_avg||0);
      m[d.governorate].trends.push(d.annual_trend_pct||0);
      m[d.governorate].count++;
    });
    return Object.entries(m).map(([gov,v]) => ({
      governorate: gov,
      avg_price: Math.round(v.prices.reduce((a,b)=>a+b,0)/v.prices.length),
      avg_trend: parseFloat((v.trends.reduce((a,b)=>a+b,0)/v.trends.length).toFixed(2)),
      delegation_count: v.count,
      coastal: v.coastal,
    })).sort((a,b) => b.avg_price - a.avg_price);
  }, [filtered]);

  // Treemap data
  const treemapData = useMemo(() => ({
    name: 'Tunisia',
    children: govAgg.slice(0,20)
      .filter(g => g.governorate && g.governorate !== 'null' && !isNaN(g.avg_price) && g.avg_price > 0)  // Filter out NaN & null governorates
      .map(g => ({
        name: g.governorate,
        size: g.avg_price,
        trend: isNaN(g.avg_trend) ? 0 : g.avg_trend,  // Replace NaN trends with 0
        count: g.delegation_count,
      })),
  }), [govAgg]);

  // Histogram bins
  const histogram = useMemo(() => {
    const bins = 12;
    const prices = filtered.map(d => d.price_avg||0).filter(p=>p>0);
    if (!prices.length) return [];
    const mn = Math.min(...prices), mx = Math.max(...prices);
    const step = (mx-mn)/bins || 100;
    return Array.from({length:bins}, (_,i) => {
      const lo = mn + i*step, hi = lo+step;
      return { range:`${Math.round(lo/100)*100}`, count: prices.filter(p=>p>=lo&&p<hi).length };
    });
  }, [filtered]);

  // Radar: top 8 govs by 5 metrics
  const radarGovs = govAgg.slice(0,8);

  // KPIs
  const kpis = useMemo(() => {
    if (!filtered.length) return {};
    const prices = filtered.map(d=>d.price_avg||0).filter(p=>p>0);
    const coastal = filtered.filter(d=>d.is_coastal);
    const inland  = filtered.filter(d=>!d.is_coastal);
    const coastalAvg = coastal.length ? coastal.reduce((s,d)=>s+(d.price_avg||0),0)/coastal.length : 0;
    const inlandAvg  = inland.length  ? inland.reduce((s,d) =>s+(d.price_avg||0),0)/inland.length  : 0;
    const natAvg = prices.reduce((a,b)=>a+b,0)/(prices.length||1);
    const growing = filtered.filter(d=>trendClass(d.annual_trend_pct)==='growing').length;
    const declining = filtered.filter(d=>trendClass(d.annual_trend_pct)==='declining').length;
    const topP = [...filtered].sort((a,b)=>(b.price_avg||0)-(a.price_avg||0))[0];
    const topG = [...filtered].filter(d=>trendClass(d.annual_trend_pct)==='growing').sort((a,b)=>(b.annual_trend_pct||0)-(a.annual_trend_pct||0))[0];
    const cheapest = [...filtered].sort((a,b)=>(a.price_avg||Infinity)-(b.price_avg||Infinity))[0];
    return { natAvg, growing, declining, topP, topG, cheapest,
      // needs both groups: it read -100% when no delegation was marked coastal
      coastalPremium: coastal.length && inland.length && inlandAvg ? (coastalAvg/inlandAvg-1)*100 : null,
      total: filtered.length };
  }, [filtered]);

  const nationalFreshness = freshness?.national_median_price;
  const growthFreshness = freshness?.top_growing_delegations;
  const listingFreshness = freshness?.national_listing_volume;
  const isNationalStale = nationalFreshness?.status === 'stale';

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d==='asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const resetFilters = () => { setFilterGov(''); setFilterTrend('all'); setFilterCoastal(false); setPriceMin(''); setPriceMax(''); setSearch(''); };

  if (loading) return (
    <div className="flex items-center justify-center py-24 gap-3 text-gray-400">
      <Loader2 size={24} className="animate-spin" /><span className="text-sm">Loading market data…</span>
    </div>
  );
  if (error) return <LoadError message={error} onRetry={() => loadMarket(propType)} />;

  return (
    <section className="space-y-8">

      {/* ── Header ── */}
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-[#FF6B35]/30 bg-[#FF6B35]/10 px-3 py-1.5 text-xs font-semibold text-[#FFB38F] mb-3">
          <LayoutDashboard size={13} /> Reference Price Benchmarks · {marketData?.total_delegations} Delegations
        </div>
        <h2 className="text-3xl font-black text-white">Market Intelligence Dashboard</h2>
        <p className="mt-1.5 text-gray-400 max-w-2xl">
          Asking-price benchmarks per m² (minimum, average, maximum) and annual trends for every Tunisian
          delegation. The cards directly below come from real listings instead, so their figures differ.
        </p>
        {materialized?.freshness && (
          <p className="mt-2 text-xs text-gray-500">
            Listing figures updated {materialized.freshness.age_human} · {fmt(materialized.national_listing_count)} listings
          </p>
        )}
      </div>

      {/* ── KPI Grid Module ── */}
      <KPIGrid />

      {/* ── Filters ── */}
      <div className={CARD + ' space-y-4'}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-[#FF6B35]" />
            <span className="text-sm font-semibold text-white">Filters</span>
            {activeFilters.length > 0 && (
              <span className="text-xs bg-[#FF6B35]/20 text-[#FF6B35] rounded-full px-2 py-0.5">{activeFilters.length} active</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500">{filtered.length} of {allDelegations.length} delegations</span>
            {activeFilters.length > 0 && (
              <button onClick={resetFilters} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors">
                <X size={11} /> Reset
              </button>
            )}
          </div>
        </div>

        {/* Property type */}
        <div>
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-2">Property Type</p>
          <PropTypePills value={propType} onChange={(pt) => { setPropType(pt); setMarketData(null); }} />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2 border-t border-white/8">
          {/* Governorate */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-widest text-gray-500 block mb-1.5">Governorate</label>
            <select className={SEL_CLS} value={filterGov} onChange={e => setFilterGov(e.target.value)}>
              <option value="">All governorates</option>
              {govOptions.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          {/* Trend */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-widest text-gray-500 block mb-1.5">Market Trend</label>
            <select className={SEL_CLS} value={filterTrend} onChange={e => setFilterTrend(e.target.value)}>
              <option value="all">All trends</option>
              <option value="growing">Growing ▲</option>
              <option value="declining">Declining ▼</option>
              <option value="stable">Stable →</option>
            </select>
          </div>
          {/* Price range */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-widest text-gray-500 block mb-1.5">Price Range (TND/m²)</label>
            <div className="flex gap-2">
              <input type="number" placeholder="Min" value={priceMin} onChange={e=>setPriceMin(e.target.value)}
                className={SEL_CLS + ' text-xs'} />
              <input type="number" placeholder="Max" value={priceMax} onChange={e=>setPriceMax(e.target.value)}
                className={SEL_CLS + ' text-xs'} />
            </div>
          </div>
          {/* Search + coastal */}
          <div>
            <label className="text-xs font-semibold uppercase tracking-widest text-gray-500 block mb-1.5">Search</label>
            <div className="relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
              <input type="text" placeholder="Delegation or governorate…" value={search} onChange={e=>setSearch(e.target.value)}
                className={SEL_CLS + ' pl-8 text-xs'} />
            </div>
          </div>
        </div>
      </div>

      {/* ── KPI Strip ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-[#FF6B35]/25 bg-[#FF6B35]/8 p-5 flex flex-col gap-1">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-1" style={{background:'#FF6B3520',border:'1px solid #FF6B3530'}}>
            <Building2 size={14} className="text-[#FF6B35]" />
          </div>
          <p className="text-xs uppercase tracking-widest text-gray-500">Benchmark Average</p>
          <p className={`text-2xl font-black ${isNationalStale ? 'text-gray-500' : 'text-white'}`}>
            {isNationalStale
              ? <span className="text-base">Data out of date</span>
              : <>{Math.round(kpis.natAvg||0).toLocaleString()} <span className="text-sm font-normal text-gray-500">TND/m²</span></>}
          </p>
          <p className="text-xs text-gray-500">{kpis.total} delegations shown</p>
          <FreshnessPill freshness={nationalFreshness} />
        </div>
        <div className="rounded-2xl border border-green-500/20 bg-green-500/8 p-5 flex flex-col gap-1">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-1" style={{background:'#16a34a20',border:'1px solid #16a34a30'}}>
            <TrendingUp size={14} className="text-green-400" />
          </div>
          <p className="text-xs uppercase tracking-widest text-gray-500">Growing Markets</p>
          <p className={`text-2xl font-black ${growthFreshness?.status === 'stale' ? 'text-gray-500' : 'text-green-400'}`}>
            {growthFreshness?.status === 'stale' ? <span className="text-base">Data out of date</span> : kpis.growing}
          </p>
          <p className="text-xs text-gray-500">{kpis.declining} declining · {(kpis.total||0)-(kpis.growing||0)-(kpis.declining||0)} stable (±{TREND_BAND}%)</p>
          <FreshnessPill freshness={growthFreshness} />
        </div>
        <div className="rounded-2xl border border-yellow-500/20 bg-yellow-500/8 p-5 flex flex-col gap-1">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-1" style={{background:'#d9770620',border:'1px solid #d9770630'}}>
            <Star size={14} className="text-yellow-400" />
          </div>
          <p className="text-xs uppercase tracking-widest text-gray-500">Highest Priced</p>
          <p className={`text-base font-black leading-tight truncate ${nationalFreshness?.status === 'stale' ? 'text-gray-500' : 'text-white'}`}>{nationalFreshness?.status === 'stale' ? 'Data out of date' : (kpis.topP?.delegation || 'No price data')}</p>
          <p className="text-xs text-gray-500">{nationalFreshness?.status === 'stale' ? 'Waiting for a data refresh' : (kpis.topP ? `${Math.round(kpis.topP.price_avg).toLocaleString()} TND/m² · ${kpis.topP.governorate}` : 'No delegation has a price yet')}</p>
          <FreshnessPill freshness={nationalFreshness} />
        </div>
        <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/8 p-5 flex flex-col gap-1">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-1" style={{background:'#0284c720',border:'1px solid #0284c730'}}>
            <Zap size={14} className="text-cyan-400" />
          </div>
          <p className="text-xs uppercase tracking-widest text-gray-500">Fastest Growing</p>
          <p className={`text-base font-black leading-tight truncate ${growthFreshness?.status === 'stale' ? 'text-gray-500' : 'text-white'}`}>{growthFreshness?.status === 'stale' ? 'Data out of date' : (kpis.topG?.delegation || 'No growth data')}</p>
          <p className="text-xs text-gray-500">{growthFreshness?.status === 'stale' ? 'Waiting for a data refresh' : (kpis.topG ? `${fmtP(kpis.topG.annual_trend_pct)} a year · ${kpis.topG.governorate}` : 'No growing delegation')}</p>
          <FreshnessPill freshness={growthFreshness} />
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col gap-1">
          <p className="text-xs uppercase tracking-widest text-gray-500">Most Affordable</p>
          <p className="text-base font-black text-white leading-tight truncate">{kpis.cheapest?.delegation || 'No price data'}</p>
          <p className="text-xs text-gray-500">{kpis.cheapest ? `${Math.round(kpis.cheapest.price_avg).toLocaleString()} TND/m²` : 'No delegation has a price yet'}</p>
          <FreshnessPill freshness={nationalFreshness} />
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col gap-1">
          <p className="text-xs uppercase tracking-widest text-gray-500">Coastal Premium</p>
          <p className="text-2xl font-black text-[#4ECDC4]">{kpis.coastalPremium != null ? fmtP(kpis.coastalPremium) : <span className="text-base">Not enough data</span>}</p>
          <p className="text-xs text-gray-500">coastal vs inland benchmark average</p>
          <FreshnessPill freshness={nationalFreshness} />
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col gap-1">
          <p className="text-xs uppercase tracking-widest text-gray-500">Governorates</p>
          <p className="text-2xl font-black text-white">{govAgg.length}</p>
          <p className="text-xs text-gray-500">in filtered view</p>
          <FreshnessPill freshness={listingFreshness} />
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col gap-1">
          <p className="text-xs uppercase tracking-widest text-gray-500">Price Spread</p>
          <p className="text-sm font-black text-white leading-tight">
            {filtered.length ? <>
              {Math.round(Math.min(...filtered.map(d=>d.price_avg||0).filter(p=>p>0))).toLocaleString()}
              <span className="text-gray-500 font-normal"> – </span>
              {Math.round(Math.max(...filtered.map(d=>d.price_avg||0))).toLocaleString()}
            </> : 'No delegations in view'}
          </p>
          <p className="text-xs text-gray-500">TND/m² range</p>
          <FreshnessPill freshness={nationalFreshness} />
        </div>
      </div>

      {/* ── Map + Pie/Donut Row ── */}
      <div className="grid lg:grid-cols-2 gap-6">

        {/* Choropleth map */}
        <div className={CARD}>
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Price Heatmap · Tunisia</p>
          <p className="text-xs text-gray-600 mb-4">Avg price per m² by governorate · hover for details</p>
          {hoveredGov && (() => {
            const info = govAgg.find(g => g.governorate === hoveredGov);
            return info ? (
              <div className="mb-3 flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5">
                <MapPin size={13} className="text-[#FF6B35] flex-shrink-0" />
                <div>
                  <p className="text-sm font-bold text-white">{info.governorate}</p>
                  <p className="text-xs text-gray-400">Avg: {Math.round(info.avg_price).toLocaleString()} TND/m² · {info.delegation_count} delegations · trend: {info.avg_trend > 0 ? '+' : ''}{info.avg_trend}%</p>
                </div>
              </div>
            ) : null;
          })()}
          <TunisChoropleth delegations={filtered} hoveredGov={hoveredGov} onHover={setHoveredGov} />
        </div>

        {/* Pie + donut column */}
        <div className="flex flex-col gap-6">
          {/* Price bracket donut */}
          <div className={CARD + ' flex-1'}>
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Price Distribution</p>
            <p className="text-xs text-gray-600 mb-4">Delegations by price bracket (TND/m²)</p>
            {priceBrackets.length > 0 ? (
              <div className="flex items-center gap-4">
                <ResponsiveContainer width="50%" height={200}>
                  <PieChart>
                    <Pie data={priceBrackets} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                      dataKey="value" paddingAngle={2}>
                      {priceBrackets.map((b,i) => <Cell key={b.name} fill={b.color} fillOpacity={0.85}/>)}
                    </Pie>
                    <Tooltip content={({active,payload}) => {
                      if (!active||!payload?.length) return null;
                      const d=payload[0];
                      return (
                        <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2 text-xs">
                          <p className="font-bold text-white">{d.name}</p>
                          <p style={{color:d.payload.color}}>{d.value} delegations ({((d.value/filtered.length)*100).toFixed(1)}%)</p>
                        </div>
                      );
                    }}/>
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex-1 space-y-2">
                  {priceBrackets.map(b => (
                    <div key={b.name} className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{background:b.color}}/>
                        <span className="text-xs text-gray-400">{b.name}</span>
                      </div>
                      <span className="text-xs font-semibold text-white">{b.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : <div className="h-32 flex items-center justify-center text-gray-600 text-sm">No data</div>}
          </div>

          {/* Growing vs Declining donut */}
          <div className={CARD + ' flex-1'}>
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Market Health</p>
            <p className="text-xs text-gray-600 mb-4">Annual benchmark trend: growing ≥ +{TREND_BAND}%, declining ≤ −{TREND_BAND}%</p>
            {(() => {
              const grow = filtered.filter(d=>trendClass(d.annual_trend_pct)==='growing').length;
              const decl = filtered.filter(d=>trendClass(d.annual_trend_pct)==='declining').length;
              const stbl = filtered.length - grow - decl;
              const healthData = [
                {name:'Growing',value:grow,color:'#16a34a'},
                {name:'Stable', value:stbl,color:'#6b7280'},
                {name:'Declining',value:decl,color:'#ef4444'},
              ].filter(d=>d.value>0);
              return healthData.length > 0 ? (
                <div className="flex items-center gap-4">
                  <ResponsiveContainer width="50%" height={160}>
                    <PieChart>
                      <Pie data={healthData} cx="50%" cy="50%" innerRadius={40} outerRadius={68}
                        dataKey="value" paddingAngle={3}>
                        {healthData.map(d => <Cell key={d.name} fill={d.color} fillOpacity={0.85}/>)}
                      </Pie>
                      <Tooltip content={({active,payload}) => {
                        if (!active||!payload?.length) return null;
                        const d=payload[0];
                        return (
                          <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2 text-xs">
                            <p style={{color:d.payload.color}} className="font-bold">{d.name}: {d.value}</p>
                          </div>
                        );
                      }}/>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex-1 space-y-3">
                    {healthData.map(d => (
                      <div key={d.name} className="flex items-center justify-between">
                        <span className="flex items-center gap-2 text-xs text-gray-400">
                          <span className="w-2.5 h-2.5 rounded-full" style={{background:d.color}}/>
                          {d.name}
                        </span>
                        <span className="text-xs font-bold text-white">{d.value} <span className="text-gray-600 font-normal">({((d.value/filtered.length)*100).toFixed(0)}%)</span></span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : <div className="h-32 flex items-center justify-center text-gray-600 text-sm">No data</div>;
            })()}
          </div>
        </div>
      </div>

      {/* ── Top 20 by Price (horizontal bar) ── */}
      <div className={CARD}>
        <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Price Ranking — Top 20 Delegations</p>
        <p className="text-xs text-gray-600 mb-5">Benchmark average price per m² (TND) · filtered view</p>
        {top20Price.length > 0 ? (
          <ResponsiveContainer width="100%" height={520}>
            <BarChart data={top20Price} layout="vertical" margin={{left:0,right:70,top:0,bottom:0}}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false}/>
              <XAxis type="number" tick={{fill:'#6b7280',fontSize:10}} axisLine={false} tickLine={false}
                tickFormatter={fmtK}/>
              <YAxis type="category" dataKey="delegation" tick={{fill:'#9ca3af',fontSize:10}}
                axisLine={false} tickLine={false} width={110}/>
              <Tooltip content={({active,payload,label}) => {
                if (!active||!payload?.length) return null;
                const d=payload[0]?.payload;
                return (
                  <div className="rounded-xl border border-white/20 bg-[#111827] px-4 py-3 text-xs space-y-1">
                    <p className="font-bold text-white">{label}</p>
                    <p className="text-gray-400">{d?.governorate}</p>
                    <p className="text-[#FF6B35]">Avg: <strong>{fmt(d?.price_avg)} TND/m²</strong></p>
                    <p className="text-gray-400">Range: {fmt(d?.price_min)} – {fmt(d?.price_max)}</p>
                    <TrendBadge growth={d?.annual_trend_pct??0}/>
                  </div>
                );
              }}/>
              <Bar dataKey="price_avg" name="Avg Price/m²" radius={[0,6,6,0]} maxBarSize={20}>
                {top20Price.map((e,i) => <Cell key={e.delegation} fill={CHART_COLORS[i%CHART_COLORS.length]} fillOpacity={0.85}/>)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No data</div>}
      </div>

      {/* ── Growing vs Declining ── */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className={CARD}>
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-1"><span className="text-green-400">▲</span> Fastest Growing</p>
          <p className="text-xs text-gray-600 mb-4">Top 10 by annual trend %</p>
          {top10Growing.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={top10Growing} layout="vertical" margin={{left:0,right:55,top:0,bottom:0}}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false}/>
                <XAxis type="number" tick={{fill:'#6b7280',fontSize:10}} axisLine={false} tickLine={false} tickFormatter={v=>`+${v}%`}/>
                <YAxis type="category" dataKey="delegation" tick={{fill:'#9ca3af',fontSize:10}} axisLine={false} tickLine={false} width={95}/>
                <Tooltip content={({active,payload,label}) => {
                  if (!active||!payload?.length) return null;
                  const d=payload[0]?.payload;
                  return (
                    <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2.5 text-xs space-y-1">
                      <p className="font-bold text-white">{label} <span className="text-gray-400 font-normal">· {d?.governorate}</span></p>
                      <p className="text-green-400">+{d?.annual_trend_pct}% growth</p>
                      <p className="text-[#FF6B35]">{fmt(d?.price_avg)} TND/m²</p>
                    </div>
                  );
                }}/>
                <Bar dataKey="annual_trend_pct" name="Growth %" radius={[0,6,6,0]} maxBarSize={20}>
                  {top10Growing.map((_,i) => <Cell key={i} fill={CHART_COLORS[i%CHART_COLORS.length]} fillOpacity={0.9}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No growing markets</div>}
        </div>
        <div className={CARD}>
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-1"><span className="text-red-400">▼</span> Declining Markets</p>
          <p className="text-xs text-gray-600 mb-4">Top 10 by annual decline</p>
          {top10Declining.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={top10Declining} layout="vertical" margin={{left:0,right:55,top:0,bottom:0}}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false}/>
                <XAxis type="number" tick={{fill:'#6b7280',fontSize:10}} axisLine={false} tickLine={false} tickFormatter={v=>`${v}%`}/>
                <YAxis type="category" dataKey="delegation" tick={{fill:'#9ca3af',fontSize:10}} axisLine={false} tickLine={false} width={95}/>
                <Tooltip content={({active,payload,label}) => {
                  if (!active||!payload?.length) return null;
                  const d=payload[0]?.payload;
                  return (
                    <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2.5 text-xs space-y-1">
                      <p className="font-bold text-white">{label} <span className="text-gray-400 font-normal">· {d?.governorate}</span></p>
                      <p className="text-red-400">{d?.annual_trend_pct}% decline</p>
                      <p className="text-[#FF6B35]">{fmt(d?.price_avg)} TND/m²</p>
                    </div>
                  );
                }}/>
                <Bar dataKey="annual_trend_pct" name="Trend %" radius={[0,6,6,0]} maxBarSize={20}>
                  {top10Declining.map((_,i) => <Cell key={i} fill="#EF4444" fillOpacity={0.45+0.06*i}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No declining data</div>}
        </div>
      </div>

      {/* ── Price Histogram + Scatter ── */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Histogram */}
        <div className={CARD}>
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Price Frequency Histogram</p>
          <p className="text-xs text-gray-600 mb-4">Distribution of avg price/m² across delegations</p>
          {histogram.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={histogram} margin={{left:0,right:10,top:0,bottom:20}}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false}/>
                <XAxis dataKey="range" tick={{fill:'#6b7280',fontSize:9}} axisLine={false} tickLine={false}
                  angle={-35} textAnchor="end" interval={0}/>
                <YAxis tick={{fill:'#6b7280',fontSize:10}} axisLine={false} tickLine={false}/>
                <Tooltip content={({active,payload,label}) => {
                  if (!active||!payload?.length) return null;
                  return (
                    <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2 text-xs">
                      <p className="text-white font-bold">~{label} TND/m²</p>
                      <p className="text-[#FF6B35]">{payload[0].value} delegations</p>
                    </div>
                  );
                }}/>
                <Bar dataKey="count" name="Count" radius={[4,4,0,0]} maxBarSize={32}>
                  {histogram.map((_,i) => <Cell key={i} fill={CHART_COLORS[i%CHART_COLORS.length]} fillOpacity={0.8}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No data</div>}
        </div>

        {/* Scatter: price vs growth */}
        <div className={CARD}>
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Price vs Growth Positioning</p>
          <p className="text-xs text-gray-600 mb-4">Each dot = one delegation · top-right = premium high-growth</p>
          {scatterData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <ScatterChart margin={{left:10,right:10,top:10,bottom:30}}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                <XAxis type="number" dataKey="price_avg" name="Price/m²"
                  tick={{fill:'#6b7280',fontSize:10}} axisLine={false} tickLine={false}
                  tickFormatter={fmtK}
                  label={{value:'Price/m² (TND)',position:'insideBottom',offset:-18,fill:'#6b7280',fontSize:10}}/>
                <YAxis type="number" dataKey="annual_trend_pct" name="Trend %"
                  tick={{fill:'#6b7280',fontSize:10}} axisLine={false} tickLine={false}
                  tickFormatter={v=>`${v}%`}/>
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" strokeDasharray="4 4"/>
                <Tooltip content={({active,payload}) => {
                  if (!active||!payload?.length) return null;
                  const d=payload[0]?.payload;
                  return (
                    <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2 text-xs space-y-0.5">
                      <p className="font-bold text-white">{d?.delegation}</p>
                      <p className="text-gray-400">{d?.governorate}</p>
                      <p className="text-[#FF6B35]">{fmt(d?.price_avg)} TND/m²</p>
                      <p className={(d?.annual_trend_pct||0)>=0?'text-green-400':'text-red-400'}>{fmtP(d?.annual_trend_pct)}</p>
                    </div>
                  );
                }}/>
                <Scatter data={scatterData} fill={ORANGE}>
                  {scatterData.map((e,i) => (
                    <Cell key={`${e.delegation}-${i}`}
                      fill={{growing:'#4ECDC4',declining:'#EF4444',stable:'#9ca3af'}[trendClass(e.annual_trend_pct)]} fillOpacity={0.72}/>
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          ) : <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No scatter data</div>}
          <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#4ECDC4] inline-block"/> Growing</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-gray-400 inline-block"/> Stable</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500 inline-block"/> Declining</span>
          </div>
        </div>
      </div>

      {/* ── Treemap + Radar ── */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Treemap */}
        <div className={CARD}>
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Governorate Treemap</p>
          <p className="text-xs text-gray-600 mb-4">Area = avg price/m² by governorate</p>
          {govAgg.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <Treemap data={treemapData.children} dataKey="size" aspectRatio={4/3}
                content={({ x, y, width, height, name, size, depth }) => {
                  // the root node has no name or size (it printed 'NaN')
                  if (!name || depth === 0 || !Number.isFinite(size)) return null;
                  if (!width || !height || width < 20 || height < 14) return null;
                  const fill = dashPriceColor(size);
                  return (
                    <g>
                      <rect x={x+1} y={y+1} width={width-2} height={height-2} rx={4}
                        fill={fill} fillOpacity={0.82} stroke="rgba(0,0,0,0.3)" strokeWidth={0.5}/>
                      {width > 45 && height > 22 && (
                        <text x={x+width/2} y={y+height/2-5} textAnchor="middle" fill="#fff"
                          fontSize={Math.min(11,width/8)} style={{pointerEvents:'none',fontWeight:600}}>
                          {name}
                        </text>
                      )}
                      {width > 45 && height > 34 && (
                        <text x={x+width/2} y={y+height/2+8} textAnchor="middle" fill="rgba(255,255,255,0.7)"
                          fontSize={Math.min(9,width/10)} style={{pointerEvents:'none'}}>
                          {Math.round(size).toLocaleString()}
                        </text>
                      )}
                    </g>
                  );
                }}>
                <Tooltip content={({active,payload}) => {
                  if (!active||!payload?.length) return null;
                  const d=payload[0]?.payload;
                  return (
                    <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2 text-xs space-y-0.5">
                      <p className="font-bold text-white">{d?.name}</p>
                      <p className="text-[#FF6B35]">{Math.round(d?.size||0).toLocaleString()} TND/m²</p>
                      <p className="text-gray-400">{d?.count} delegations</p>
                      <p className={(d?.trend||0)>=0?'text-green-400':'text-red-400'}>{(d?.trend||0)>=0?'+':''}{(d?.trend||0).toFixed(1)}% trend</p>
                    </div>
                  );
                }}/>
              </Treemap>
            </ResponsiveContainer>
          ) : <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No data</div>}
        </div>

        {/* Radar chart */}
        <div className={CARD}>
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Governorate Radar Comparison</p>
          <p className="text-xs text-gray-600 mb-4">Top 8 governorates · benchmark average price per m²</p>
          {radarGovs.length >= 3 ? (
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={radarGovs}>
                <PolarGrid stroke="rgba(255,255,255,0.06)"/>
                <PolarAngleAxis dataKey="governorate" tick={{fill:'#9ca3af',fontSize:10}}/>
                <PolarRadiusAxis tick={{fill:'#6b7280',fontSize:8}} axisLine={false} tickFormatter={fmtK}/>
                <Radar name="Average price (TND/m²)" dataKey="avg_price" stroke="#FF6B35" fill="#FF6B35" fillOpacity={0.22} strokeWidth={2}/>
                <Tooltip content={({active,payload}) => {
                  if (!active||!payload?.length) return null;
                  const d=payload[0]?.payload;
                  return (
                    <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2 text-xs space-y-0.5">
                      <p className="font-bold text-white">{d?.governorate}</p>
                      <p className="text-[#FF6B35]">{Math.round(d?.avg_price).toLocaleString()} TND/m²</p>
                      <p className={(d?.avg_trend||0)>=0?'text-green-400':'text-red-400'}>{(d?.avg_trend||0)>=0?'+':''}{d?.avg_trend}% trend</p>
                    </div>
                  );
                }}/>
                <Legend wrapperStyle={{fontSize:'10px',color:'#6b7280'}}/>
              </RadarChart>
            </ResponsiveContainer>
          ) : <div className="h-48 flex items-center justify-center text-gray-600 text-sm">Need ≥3 governorates</div>}
        </div>
      </div>

      {/* ── Governorate bar overview ── */}
      <div className={CARD}>
        <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Governorate Price Overview</p>
        <p className="text-xs text-gray-600 mb-5">Avg price per m² aggregated by governorate · all visible delegations</p>
        {govAgg.length > 0 ? (
          <ResponsiveContainer width="100%" height={Math.max(280,govAgg.length*26)}>
            <ComposedChart data={govAgg} layout="vertical" margin={{left:0,right:70,top:0,bottom:0}}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false}/>
              <XAxis type="number" tick={{fill:'#6b7280',fontSize:10}} axisLine={false} tickLine={false}
                tickFormatter={fmtK}/>
              <YAxis type="category" dataKey="governorate" tick={{fill:'#9ca3af',fontSize:10}}
                axisLine={false} tickLine={false} width={90}/>
              <Tooltip content={({active,payload,label}) => {
                if (!active||!payload?.length) return null;
                const d=payload[0]?.payload;
                return (
                  <div className="rounded-xl border border-white/20 bg-[#111827] px-4 py-3 text-xs space-y-1">
                    <p className="font-bold text-white">{label}</p>
                    <p className="text-[#FF6B35]">{Math.round(d?.avg_price||0).toLocaleString()} TND/m²</p>
                    <p className="text-gray-400">{d?.delegation_count} delegations</p>
                    <TrendBadge growth={d?.avg_trend??0}/>
                  </div>
                );
              }}/>
              <Bar dataKey="avg_price" name="Avg Price/m²" radius={[0,6,6,0]} maxBarSize={20}>
                {govAgg.map((_,i) => <Cell key={i} fill={CHART_COLORS[i%CHART_COLORS.length]} fillOpacity={0.8}/>)}
              </Bar>
            </ComposedChart>
          </ResponsiveContainer>
        ) : <div className="h-40 flex items-center justify-center text-gray-600 text-sm">No data</div>}
      </div>

      {/* ── Coastal vs Inland area comparison ── */}
      {(() => {
        const coastalAvgs = govAgg.filter(g=>g.coastal).map(g=>({name:g.governorate,coastal:g.avg_price}));
        const inlandAvgs  = govAgg.filter(g=>!g.coastal).map(g=>({name:g.governorate,inland:g.avg_price}));
        if (!coastalAvgs.length && !inlandAvgs.length) return null;
        const combined = [
          ...coastalAvgs.map(c=>({...c,type:'Coastal',value:c.coastal})),
          ...inlandAvgs.map(c=>({...c,type:'Inland',value:c.inland})),
        ].sort((a,b)=>b.value-a.value).slice(0,16);
        return (
          <div className={CARD}>
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Coastal vs Inland Premium</p>
            <p className="text-xs text-gray-600 mb-5">Top governorates coloured by zone type</p>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={combined} margin={{left:0,right:60,top:0,bottom:20}}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false}/>
                <XAxis dataKey="name" tick={{fill:'#9ca3af',fontSize:9}} axisLine={false} tickLine={false}
                  angle={-30} textAnchor="end" interval={0}/>
                <YAxis tick={{fill:'#6b7280',fontSize:10}} axisLine={false} tickLine={false}
                  tickFormatter={fmtK}/>
                <Tooltip content={({active,payload,label}) => {
                  if (!active||!payload?.length) return null;
                  const d=payload[0]?.payload;
                  return (
                    <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2 text-xs space-y-0.5">
                      <p className="font-bold text-white">{label}</p>
                      <p className="text-gray-400">{d?.type}</p>
                      <p className="text-[#FF6B35]">{Math.round(d?.value||0).toLocaleString()} TND/m²</p>
                    </div>
                  );
                }}/>
                <Bar dataKey="value" name="Avg Price" radius={[4,4,0,0]} maxBarSize={30}>
                  {combined.map((e,i) => <Cell key={i} fill={e.type==='Coastal'?'#4ECDC4':'#F0B27A'} fillOpacity={0.85}/>)}
                </Bar>
                <Legend content={() => (
                  <div className="flex items-center gap-4 justify-center pt-2 text-xs text-gray-500">
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-[#4ECDC4] inline-block"/>Coastal</span>
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-[#F0B27A] inline-block"/>Inland</span>
                  </div>
                )}/>
              </BarChart>
            </ResponsiveContainer>
          </div>
        );
      })()}

      {/* ── Radial gauge: top 10 by price ── */}
      <div className={CARD}>
        <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Price Gauge — Top 10</p>
        <p className="text-xs text-gray-600 mb-5">Price per m² of each delegation as % of the highest-priced one</p>
        {(() => {
          const top10 = [...filtered].sort((a,b)=>(b.price_avg||0)-(a.price_avg||0)).slice(0,10);
          const maxP = top10[0]?.price_avg || 1;
          const gaugeData = top10.map((d,i)=>({ name:d.delegation, value: Math.round((d.price_avg/maxP)*100), price:d.price_avg, fill:CHART_COLORS[i] }));
          return gaugeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={340}>
              <RadialBarChart cx="50%" cy="50%" innerRadius="15%" outerRadius="90%"
                data={gaugeData} startAngle={180} endAngle={-180}>
                <RadialBar minAngle={5} background={{ fill:'rgba(255,255,255,0.03)' }}
                  dataKey="value" label={{ position:'insideStart', fill:'#9ca3af', fontSize:9 }}>
                  {gaugeData.map((e,i) => <Cell key={i} fill={e.fill} fillOpacity={0.85}/>)}
                </RadialBar>
                <Tooltip content={({active,payload}) => {
                  if (!active||!payload?.length) return null;
                  const d=payload[0]?.payload;
                  return (
                    <div className="rounded-xl border border-white/20 bg-[#111827] px-3 py-2 text-xs">
                      <p className="font-bold text-white">{d?.name}</p>
                      <p className="text-[#FF6B35]">{Math.round(d?.price||0).toLocaleString()} TND/m²</p>
                    </div>
                  );
                }}/>
                <Legend iconSize={8} wrapperStyle={{fontSize:'10px',color:'#6b7280'}}/>
              </RadialBarChart>
            </ResponsiveContainer>
          ) : null;
        })()}
      </div>

      {/* ── Filtered summary table ── */}
      <div className={CARD}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
          <div>
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-0.5">Filtered Delegation Table</p>
            <p className="text-xs text-gray-600">{sorted.length} of {allDelegations.length} — click headers to sort</p>
          </div>
          <div className="relative max-w-xs w-full">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"/>
            <input type="text" placeholder="Search…" value={search} onChange={e=>setSearch(e.target.value)}
              className="w-full rounded-xl border border-white/15 bg-black/30 pl-8 pr-3 py-2 text-sm text-white placeholder-gray-600 focus:border-[#FF6B35]/60 focus:outline-none focus:ring-1 focus:ring-[#FF6B35]/30 transition-colors"/>
          </div>
        </div>
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 bg-white/5">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 w-8">#</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Delegation</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Governorate</th>
                <SortTh label="Avg Price"    col="price_avg"        active={sortKey==='price_avg'}        dir={sortDir} onClick={()=>handleSort('price_avg')}/>
                <SortTh label="Min"          col="price_min"        active={sortKey==='price_min'}        dir={sortDir} onClick={()=>handleSort('price_min')}/>
                <SortTh label="Max"          col="price_max"        active={sortKey==='price_max'}        dir={sortDir} onClick={()=>handleSort('price_max')}/>
                <SortTh label="12M Outlook" col="price_12m"        active={sortKey==='price_12m'}        dir={sortDir} onClick={()=>handleSort('price_12m')}/>
                <SortTh label="Trend"        col="annual_trend_pct" active={sortKey==='annual_trend_pct'} dir={sortDir} onClick={()=>handleSort('annual_trend_pct')}/>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {sorted.slice(0,50).map((d,i) => (
                <tr key={`${d.delegation}-${d.governorate}`} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-2.5 text-xs text-gray-600">{i+1}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <MapPin size={11} className="text-gray-600 flex-shrink-0"/>
                      <span className="text-sm font-semibold text-white">{d.delegation}</span>
                      {d.is_coastal && <span className="text-[10px] text-cyan-400 flex-shrink-0">🌊</span>}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-400">{d.governorate}</td>
                  <td className="px-4 py-2.5 text-sm font-semibold text-[#FF6B35]">{fmt(d.price_avg)} <span className="text-xs font-normal text-gray-500">TND/m²</span></td>
                  <td className="px-4 py-2.5 text-sm text-gray-300">{fmt(d.price_min)}</td>
                  <td className="px-4 py-2.5 text-sm text-gray-300">{fmt(d.price_max)}</td>
                  <td className="px-4 py-2.5 text-sm text-[#4ECDC4]">{fmt(d.price_12m)}</td>
                  <td className="px-4 py-2.5"><TrendBadge growth={d.annual_trend_pct??0}/></td>
                </tr>
              ))}
              {sorted.length === 0 && (
                <tr><td colSpan={8} className="text-center text-gray-500 text-sm py-10">No delegations match filters</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {sorted.length > 50 && (
          <p className="text-xs text-gray-600 mt-3">Showing first 50 of {sorted.length} results — use filters to narrow down.</p>
        )}
        <p className="text-xs text-gray-600 mt-2 flex items-center gap-1.5">
          <Info size={11}/>Reference benchmark prices, TND/m². 12M = outlook for {marketData?.horizon?.end || 'twelve months from now'} (INS national growth plus the local benchmark deviation). Trend = the benchmark's own stated annual trend.
        </p>
      </div>

    </section>
  );
}

// ── Page root ──────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'dashboard', label: 'Market Dashboard', icon: LayoutDashboard },
  { id: 'forecast',  label: 'Price Outlook',    icon: BarChart3       },
];

export default function AnalyzePage() {
  const { user, trackActivity } = useAuth();
  const [activeTab, setActiveTab] = useState('dashboard');

  useEffect(() => {
    trackActivity?.('analysis', 'analyze_page_view', { plan: user?.plan || 'free' });
  }, [trackActivity, user?.plan]);

  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] pt-24 px-4 pb-16 text-white">
      <div className="max-w-6xl mx-auto space-y-8">

        <section>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-2">Analyze</h1>
          <p className="text-gray-400 text-lg max-w-2xl">
            Market intelligence for every delegation in Tunisia: reference prices, real listing figures and 12-month outlooks.
          </p>
        </section>

        <div className="flex gap-1 rounded-2xl border border-white/10 bg-white/5 p-1.5">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setActiveTab(id)}
              className={`flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-all
                ${activeTab === id
                  ? 'bg-[#FF6B35] text-white shadow-lg shadow-[#FF6B35]/20'
                  : 'text-gray-400 hover:text-gray-200'}`}>
              <Icon size={15} />{label}
            </button>
          ))}
        </div>

        {activeTab === 'dashboard' && <DashboardSection />}
        {activeTab === 'forecast'  && <PriceForecastSection />}

      </div>
    </main>
  );
}
