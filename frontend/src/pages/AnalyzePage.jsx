/**
 * AnalyzePage — Market Intelligence Hub
 * Tab 1: Market Dashboard — all 278 delegations, real prices from CSV
 * Tab 2: Price Forecast — 12-month forecasts per delegation (Jan–Dec 2026)
 * Tab 3: Climate Risk Intelligence — full Tunisia climate risk analysis
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  AreaChart, Area, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, Legend,
  PieChart, Pie, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Treemap, RadialBarChart, RadialBar, ComposedChart, Line, ReferenceLine,
} from 'recharts';
import {
  AlertTriangle, BarChart3, LayoutDashboard, Building2, Loader2,
  TrendingUp, TrendingDown, Minus, MapPin, Globe, ChevronRight,
  ChevronUp, ChevronDown, Info, Search, ArrowUpDown, Home, Store, Trees,
  Waves, DollarSign, Activity, Filter, X, RefreshCw, Star, Zap,
  Thermometer, Droplets, Wind, Shield, CloudRain, Sun, FlameKindling,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getForecastGovernorateList,
  getForecastDelegationList,
  getForecastDelegation,
  getForecastNational,
  getForecastMarket,
  getClimateDashboard,
  getClimateScenarios,
  getClimateRegionalHeatmap,
  getClimateWeather,
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

const fmt = (n) => (n ?? 0).toLocaleString('fr-TN', { maximumFractionDigits: 0 });
const fmtP = (n) => `${n > 0 ? '+' : ''}${(n ?? 0).toFixed(2)}%`;

// ── Shared atoms ──────────────────────────────────────────────────────────────
function TrendBadge({ growth }) {
  if (growth >= 2)
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-green-500/30 bg-green-500/15 px-2.5 py-1 text-xs font-semibold text-green-400">
        <TrendingUp size={11} /> +{growth}%
      </span>
    );
  if (growth <= -2)
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/15 px-2.5 py-1 text-xs font-semibold text-red-400">
        <TrendingDown size={11} /> {growth}%
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-gray-500/30 bg-gray-500/15 px-2.5 py-1 text-xs font-semibold text-gray-400">
      <Minus size={11} /> {growth > 0 ? '+' : ''}{growth}%
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

function KpiCard({ label, value, sub, color = ORANGE, icon: Icon }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col gap-2">
      {Icon && (
        <div className="w-9 h-9 rounded-xl flex items-center justify-center mb-1"
          style={{ background: `${color}20`, border: `1px solid ${color}30` }}>
          <Icon size={16} style={{ color }} />
        </div>
      )}
      <p className="text-xs uppercase tracking-widest text-gray-500">{label}</p>
      <p className="text-xl font-black text-white leading-tight">{value}</p>
      {sub && <p className="text-xs text-gray-500">{sub}</p>}
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

function DashTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/20 bg-[#111827] px-4 py-3 shadow-2xl text-xs space-y-1">
      <p className="font-bold text-white mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || p.fill }}>
          {p.name}: <strong>{typeof p.value === 'number'
            ? p.value.toLocaleString('fr-TN', { maximumFractionDigits: 2 })
            : p.value}</strong>
        </p>
      ))}
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
  useEffect(() => {
    if (selDel) return;
    setLoading(true);
    getForecastNational(propType)
      .then(r => setNationalData(r.data))
      .catch(() => setError('Could not load national forecast data.'))
      .finally(() => setLoading(false));
  }, [propType, selDel]);

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
          <BarChart3 size={13} /> AI Price Forecast · 278 Delegations · Jan–Dec 2026
        </div>
        <h2 className="text-3xl font-black text-white">12-Month Price Forecast</h2>
        <p className="mt-1.5 text-gray-400 max-w-2xl">
          Select a property type and delegation to see its individual 12-month price trajectory,
          based on current market data and annual growth trends.
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
        <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          <AlertTriangle size={15} className="flex-shrink-0" />{error}
        </div>
      )}

      {/* Delegation forecast view */}
      {!loading && !error && forecastData && chartData.length > 0 && (
        <div className="space-y-5">
          {/* Metric strip */}
          <div className="grid grid-cols-3 gap-4">
            <MetricCard
              label="Jan 2026"
              value={`${fmt(summary?.current_price_per_m2)} TND/m²`}
              sub="Forecast start"
            />
            <MetricCard
              label="Jun 2026"
              value={`${fmt(summary?.price_6m)} TND/m²`}
              sub={summary?.growth_pct_6m != null ? `${fmtP(summary.growth_pct_6m)} vs Jan` : ''}
            />
            <MetricCard
              label="Dec 2026"
              value={`${fmt(summary?.price_12m)} TND/m²`}
              sub={summary?.growth_pct_12m != null ? `${fmtP(summary.growth_pct_12m)} vs Jan` : ''}
              highlight
            />
          </div>

          {/* Trend + band note */}
          <div className="flex items-center gap-3 flex-wrap">
            <TrendBadge growth={summary?.growth_pct_12m ?? 0} />
            <span className="text-xs text-gray-500">Shaded area = ±2.5% confidence band</span>
          </div>

          {/* 12-month chart */}
          <div className={CARD}>
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">
              {selDel} — {PROP_TYPES.find(p => p.id === propType)?.label} · Price per m²
            </p>
            <p className="text-xs text-gray-600 mb-5">Jan 2026 → Dec 2026</p>
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
                  tickFormatter={v => `${(v / 1000).toFixed(1)}k`} />
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
                Current Market Data · {selDel} ({forecastData.governorate})
              </p>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center">
                  <p className="text-xs text-gray-500 mb-1">Asking Min</p>
                  <p className="text-base font-bold text-white">{fmt(priceRange.min)} TND/m²</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-gray-500 mb-1">Market Avg</p>
                  <p className="text-base font-bold text-[#FF6B35]">{fmt(priceRange.avg)} TND/m²</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-gray-500 mb-1">Asking Max</p>
                  <p className="text-base font-bold text-white">{fmt(priceRange.max)} TND/m²</p>
                </div>
              </div>
              {/* Price bar */}
              {priceRange.min != null && priceRange.max != null && priceRange.avg != null && (
                <div className="relative h-2 bg-white/10 rounded-full overflow-hidden">
                  <div className="absolute h-full rounded-full"
                    style={{
                      left:  `${Math.max(0, ((priceRange.min - priceRange.min) / (priceRange.max - priceRange.min || 1)) * 100)}%`,
                      width: `100%`,
                      background: 'linear-gradient(90deg, #4ECDC4, #FF6B35)',
                    }} />
                  <div className="absolute h-full w-1 bg-white rounded-full -translate-x-1/2"
                    style={{ left: `${((priceRange.avg - priceRange.min) / (priceRange.max - priceRange.min || 1)) * 100}%` }} />
                </div>
              )}
              <div className="flex items-center gap-2 mt-3">
                <TrendBadge growth={priceRange.annual_trend_pct ?? 0} />
                <span className="text-xs text-gray-500">annual market trend</span>
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
            <MetricCard label="Delegations" value={nationalData.total_delegations} sub="Individual forecasts" />
            <MetricCard label="Horizon"     value="12 months" sub="Jan–Dec 2026" />
            <MetricCard label="Accuracy"    value="~97.5%" sub="Model MAPE 2.5%" highlight />
          </div>

          <div className={CARD}>
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">
              Top 10 Delegations — Highest Projected Growth
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
                    {fmt(d.price_jan_tnd)} TND/m²
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
      .catch(() => setError('Unable to load market data.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadMarket(propType); }, [propType, loadMarket]);

  const allDelegations = marketData?.delegations || [];

  // Unique governorates for filter
  const govOptions = useMemo(() =>
    [...new Set(allDelegations.map(d => d.governorate).filter(Boolean))].sort(),
    [allDelegations]);

  // Apply filters
  const filtered = useMemo(() => {
    return allDelegations.filter(d => {
      if (filterGov && d.governorate !== filterGov) return false;
      if (filterTrend === 'growing'  && (d.annual_trend_pct || 0) <= 0) return false;
      if (filterTrend === 'declining'&& (d.annual_trend_pct || 0) >= 0) return false;
      if (filterTrend === 'stable'   && Math.abs(d.annual_trend_pct || 0) > 2) return false;
      if (filterCoastal && !d.is_coastal) return false;
      if (priceMin && (d.price_avg || 0) < parseFloat(priceMin)) return false;
      if (priceMax && (d.price_avg || 0) > parseFloat(priceMax)) return false;
      if (search && !d.delegation?.toLowerCase().includes(search.toLowerCase()) &&
          !d.governorate?.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [allDelegations, filterGov, filterTrend, filterCoastal, priceMin, priceMax, search]);

  const activeFilters = [filterGov, filterTrend !== 'all' && filterTrend, filterCoastal && 'Coastal only', priceMin && `≥${priceMin}`, priceMax && `≤${priceMax}`].filter(Boolean);

  // ── Derived datasets ───────────────────────────────────────────────────────
  const sorted = useMemo(() => [...filtered].sort((a,b) => {
    const av = a[sortKey] ?? (sortDir==='asc' ? Infinity : -Infinity);
    const bv = b[sortKey] ?? (sortDir==='asc' ? Infinity : -Infinity);
    return sortDir === 'asc' ? av - bv : bv - av;
  }), [filtered, sortKey, sortDir]);

  const top20Price = useMemo(() =>
    [...filtered].sort((a,b) => (b.price_avg||0)-(a.price_avg||0)).slice(0,20), [filtered]);

  const top10Growing = useMemo(() =>
    [...filtered].filter(d=>(d.annual_trend_pct||0)>0)
      .sort((a,b)=>(b.annual_trend_pct||0)-(a.annual_trend_pct||0)).slice(0,10), [filtered]);

  const top10Declining = useMemo(() =>
    [...filtered].filter(d=>(d.annual_trend_pct||0)<0)
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
      if (!m[d.governorate]) m[d.governorate] = { prices:[], trends:[], count:0, coastal: d.is_coastal };
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
    children: govAgg.slice(0,20).map(g => ({
      name: g.governorate,
      size: g.avg_price,
      trend: g.avg_trend,
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
    const growing = filtered.filter(d=>(d.annual_trend_pct||0)>0).length;
    const declining = filtered.filter(d=>(d.annual_trend_pct||0)<0).length;
    const topP = [...filtered].sort((a,b)=>(b.price_avg||0)-(a.price_avg||0))[0];
    const topG = [...filtered].filter(d=>(d.annual_trend_pct||0)>0).sort((a,b)=>(b.annual_trend_pct||0)-(a.annual_trend_pct||0))[0];
    const cheapest = [...filtered].sort((a,b)=>(a.price_avg||Infinity)-(b.price_avg||Infinity))[0];
    return { natAvg, growing, declining, topP, topG, cheapest,
      coastalPremium: inlandAvg ? ((coastalAvg/inlandAvg-1)*100).toFixed(1) : '—',
      total: filtered.length };
  }, [filtered]);

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
  if (error) return (
    <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
      <AlertTriangle size={15} />{error}
    </div>
  );

  return (
    <section className="space-y-8">

      {/* ── Header ── */}
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-[#FF6B35]/30 bg-[#FF6B35]/10 px-3 py-1.5 text-xs font-semibold text-[#FFB38F] mb-3">
          <LayoutDashboard size={13} /> Real Market Data · {marketData?.total_delegations} Delegations · 2026
        </div>
        <h2 className="text-3xl font-black text-white">Market Intelligence Dashboard</h2>
        <p className="mt-1.5 text-gray-400 max-w-2xl">
          Comprehensive price analytics, geographic distribution, growth trends and investment signals across all 278 Tunisian delegations.
        </p>
      </div>

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
            <label className="flex items-center gap-2 mt-2 cursor-pointer">
              <input type="checkbox" checked={filterCoastal} onChange={e=>setFilterCoastal(e.target.checked)}
                className="rounded accent-[#FF6B35]" />
              <span className="text-xs text-gray-400 flex items-center gap-1"><Waves size={11} /> Coastal only</span>
            </label>
          </div>
        </div>
      </div>

      {/* ── KPI Strip ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-[#FF6B35]/25 bg-[#FF6B35]/8 p-5 flex flex-col gap-1">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-1" style={{background:'#FF6B3520',border:'1px solid #FF6B3530'}}>
            <Building2 size={14} className="text-[#FF6B35]" />
          </div>
          <p className="text-xs uppercase tracking-widest text-gray-500">National Avg</p>
          <p className="text-2xl font-black text-white">{Math.round(kpis.natAvg||0).toLocaleString()} <span className="text-sm font-normal text-gray-500">TND/m²</span></p>
          <p className="text-xs text-gray-500">{kpis.total} delegations shown</p>
        </div>
        <div className="rounded-2xl border border-green-500/20 bg-green-500/8 p-5 flex flex-col gap-1">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-1" style={{background:'#16a34a20',border:'1px solid #16a34a30'}}>
            <TrendingUp size={14} className="text-green-400" />
          </div>
          <p className="text-xs uppercase tracking-widest text-gray-500">Growing Markets</p>
          <p className="text-2xl font-black text-green-400">{kpis.growing}</p>
          <p className="text-xs text-gray-500">{kpis.declining} declining · {(kpis.total||0)-(kpis.growing||0)-(kpis.declining||0)} stable</p>
        </div>
        <div className="rounded-2xl border border-yellow-500/20 bg-yellow-500/8 p-5 flex flex-col gap-1">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-1" style={{background:'#d9770620',border:'1px solid #d9770630'}}>
            <Star size={14} className="text-yellow-400" />
          </div>
          <p className="text-xs uppercase tracking-widest text-gray-500">Highest Priced</p>
          <p className="text-base font-black text-white leading-tight truncate">{kpis.topP?.delegation || '—'}</p>
          <p className="text-xs text-gray-500">{kpis.topP ? `${Math.round(kpis.topP.price_avg).toLocaleString()} TND/m² · ${kpis.topP.governorate}` : '—'}</p>
        </div>
        <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/8 p-5 flex flex-col gap-1">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-1" style={{background:'#0284c720',border:'1px solid #0284c730'}}>
            <Zap size={14} className="text-cyan-400" />
          </div>
          <p className="text-xs uppercase tracking-widest text-gray-500">Fastest Growing</p>
          <p className="text-base font-black text-white leading-tight truncate">{kpis.topG?.delegation || '—'}</p>
          <p className="text-xs text-gray-500">{kpis.topG ? `+${kpis.topG.annual_trend_pct}% · ${kpis.topG.governorate}` : 'No growth data'}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col gap-1">
          <p className="text-xs uppercase tracking-widest text-gray-500">Most Affordable</p>
          <p className="text-base font-black text-white leading-tight truncate">{kpis.cheapest?.delegation || '—'}</p>
          <p className="text-xs text-gray-500">{kpis.cheapest ? `${Math.round(kpis.cheapest.price_avg).toLocaleString()} TND/m²` : '—'}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col gap-1">
          <p className="text-xs uppercase tracking-widest text-gray-500">Coastal Premium</p>
          <p className="text-2xl font-black text-[#4ECDC4]">{kpis.coastalPremium !== '—' ? `+${kpis.coastalPremium}%` : '—'}</p>
          <p className="text-xs text-gray-500">vs inland avg</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col gap-1">
          <p className="text-xs uppercase tracking-widest text-gray-500">Governorates</p>
          <p className="text-2xl font-black text-white">{govAgg.length}</p>
          <p className="text-xs text-gray-500">in filtered view</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col gap-1">
          <p className="text-xs uppercase tracking-widest text-gray-500">Price Spread</p>
          <p className="text-sm font-black text-white leading-tight">
            {filtered.length ? `${Math.round(Math.min(...filtered.map(d=>d.price_avg||0).filter(p=>p>0))).toLocaleString()}` : '—'}
            <span className="text-gray-500 font-normal"> – </span>
            {filtered.length ? `${Math.round(Math.max(...filtered.map(d=>d.price_avg||0))).toLocaleString()}` : '—'}
          </p>
          <p className="text-xs text-gray-500">TND/m² range</p>
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
            <p className="text-xs text-gray-600 mb-4">Growing vs stable vs declining</p>
            {(() => {
              const grow = filtered.filter(d=>(d.annual_trend_pct||0)>2).length;
              const decl = filtered.filter(d=>(d.annual_trend_pct||0)<-2).length;
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
        <p className="text-xs text-gray-600 mb-5">Current avg asking price per m² (TND) · filtered view</p>
        {top20Price.length > 0 ? (
          <ResponsiveContainer width="100%" height={520}>
            <BarChart data={top20Price} layout="vertical" margin={{left:0,right:70,top:0,bottom:0}}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false}/>
              <XAxis type="number" tick={{fill:'#6b7280',fontSize:10}} axisLine={false} tickLine={false}
                tickFormatter={v=>`${(v/1000).toFixed(0)}k`}/>
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
                  tickFormatter={v=>`${(v/1000).toFixed(0)}k`}
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
                      fill={(e.annual_trend_pct||0)>=0?'#4ECDC4':'#EF4444'} fillOpacity={0.72}/>
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          ) : <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No scatter data</div>}
          <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#4ECDC4] inline-block"/> Growing</span>
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
                content={({ x, y, width, height, name, size, trend }) => {
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
          <p className="text-xs text-gray-600 mb-4">Top 8 governorates · avg price index</p>
          {radarGovs.length >= 3 ? (
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={radarGovs.map(g => ({...g, score: Math.round(g.avg_price/100) }))}>
                <PolarGrid stroke="rgba(255,255,255,0.06)"/>
                <PolarAngleAxis dataKey="governorate" tick={{fill:'#9ca3af',fontSize:10}}/>
                <PolarRadiusAxis tick={{fill:'#6b7280',fontSize:8}} axisLine={false}/>
                <Radar name="Avg Price Index" dataKey="score" stroke="#FF6B35" fill="#FF6B35" fillOpacity={0.22} strokeWidth={2}/>
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
                tickFormatter={v=>`${(v/1000).toFixed(0)}k`}/>
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
                  tickFormatter={v=>`${(v/1000).toFixed(0)}k`}/>
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
        <p className="text-xs text-gray-600 mb-5">Radial bars showing relative price per m² across top delegations</p>
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
                <SortTh label="12M Forecast" col="price_12m"        active={sortKey==='price_12m'}        dir={sortDir} onClick={()=>handleSort('price_12m')}/>
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
          <Info size={11}/>All prices TND/m². 12M = Dec 2026 projection. Trend = annual growth rate.
        </p>
      </div>

    </section>
  );
}

// ── Climate Risk Tab ──────────────────────────────────────────────────────────
const RISK_COLORS = {
  Low: { bg: 'bg-emerald-500/15', border: 'border-emerald-500/30', text: 'text-emerald-400', hex: '#10b981' },
  Moderate: { bg: 'bg-yellow-500/15', border: 'border-yellow-500/30', text: 'text-yellow-400', hex: '#f59e0b' },
  High: { bg: 'bg-orange-500/15', border: 'border-orange-500/30', text: 'text-orange-400', hex: '#f97316' },
  'Very High': { bg: 'bg-red-500/15', border: 'border-red-500/30', text: 'text-red-400', hex: '#ef4444' },
};
const RISK_ORDER_NUM = { Low: 1, Moderate: 2, High: 3, 'Very High': 4 };
const SUSTAIN_GRADE_COLOR = { A: '#10b981', B: '#3b82f6', C: '#f59e0b', D: '#f97316', F: '#ef4444' };

function RiskBadge({ level }) {
  const c = RISK_COLORS[level] || RISK_COLORS.Moderate;
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold border ${c.bg} ${c.border} ${c.text}`}>
      {level}
    </span>
  );
}

function ClimateKpiCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4 flex flex-col gap-1.5">
      <div className="flex items-center gap-2 mb-1">
        <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${color}20`, border: `1px solid ${color}30` }}>
          <Icon size={13} style={{ color }} />
        </div>
        <p className="text-xs uppercase tracking-widest text-gray-500">{label}</p>
      </div>
      <p className="text-lg font-black text-white leading-tight">{value}</p>
      {sub && <p className="text-xs text-gray-500">{sub}</p>}
    </div>
  );
}

function ClimateRiskSection() {
  const [dashboard, setDashboard] = useState(null);
  const [scenarios, setScenarios] = useState(null);
  const [regional, setRegional]   = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [search, setSearch]       = useState('');
  const [sortKey, setSortKey]     = useState('combined_risk_score');
  const [sortDir, setSortDir]     = useState('asc');
  const [activeView, setActiveView] = useState('overview');
  const [selectedGov, setSelectedGov] = useState(null);
  const [weather, setWeather]     = useState(null);
  const [weatherLoading, setWeatherLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getClimateDashboard(),
      getClimateScenarios(),
      getClimateRegionalHeatmap(),
    ])
      .then(([d, s, r]) => {
        setDashboard(d.data);
        setScenarios(s.data);
        setRegional(r.data);
      })
      .catch(() => setError('Could not load climate data.'))
      .finally(() => setLoading(false));
  }, []);

  const handleSelectGov = useCallback(async (gov) => {
    setSelectedGov(gov);
    setWeather(null);
    if (!gov) return;
    setWeatherLoading(true);
    try {
      const res = await getClimateWeather(gov.governorate);
      setWeather(res.data);
    } catch { /* no live weather */ }
    finally { setWeatherLoading(false); }
  }, []);

  const govRows = useMemo(() => {
    const rows = dashboard?.results || [];
    const q = search.trim().toLowerCase();
    const filtered = q ? rows.filter(r => r.governorate?.toLowerCase().includes(q)) : rows;
    return [...filtered].sort((a, b) => {
      let av = a[sortKey] ?? 0, bv = b[sortKey] ?? 0;
      if (typeof av === 'string') av = RISK_ORDER_NUM[av] ?? 0;
      if (typeof bv === 'string') bv = RISK_ORDER_NUM[bv] ?? 0;
      return sortDir === 'asc' ? av - bv : bv - av;
    });
  }, [dashboard, search, sortKey, sortDir]);

  const toggleSort = useCallback((key) => {
    setSortKey(prev => { if (prev === key) { setSortDir(d => d === 'asc' ? 'desc' : 'asc'); return key; } setSortDir('asc'); return key; });
  }, []);

  const riskDist = useMemo(() => {
    const rows = dashboard?.results || [];
    const counts = { Low: 0, Moderate: 0, High: 0, 'Very High': 0 };
    rows.forEach(r => { if (counts[r.risk_category] !== undefined) counts[r.risk_category]++; });
    return Object.entries(counts).map(([name, value]) => ({ name, value, color: RISK_COLORS[name]?.hex || '#888' }));
  }, [dashboard]);

  const scenarioRows = useMemo(() => {
    const rows = scenarios?.results || [];
    return [...rows].sort((a, b) => (a.delta_4c ?? 0) - (b.delta_4c ?? 0));
  }, [scenarios]);

  const regionalRows = useMemo(() => regional?.regions || [], [regional]);

  if (loading) return (
    <div className="flex items-center justify-center py-32">
      <Loader2 className="w-8 h-8 text-[#FF6B35] animate-spin" />
    </div>
  );
  if (error) return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-red-400 text-sm">{error}</div>
  );

  const govCount = dashboard?.count || 0;
  const avgRisk = govRows.length ? (govRows.reduce((s, r) => s + (r.combined_risk_score || 0), 0) / govRows.length).toFixed(1) : '—';
  const safest = [...(dashboard?.results || [])].sort((a, b) => (a.combined_risk_score || 0) - (b.combined_risk_score || 0))[0]?.governorate || '—';
  const riskiest = [...(dashboard?.results || [])].sort((a, b) => (b.combined_risk_score || 0) - (a.combined_risk_score || 0))[0]?.governorate || '—';

  return (
    <section className="space-y-8">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1.5 text-xs font-semibold text-blue-300 mb-3">
          <Shield size={11} /> Climate Risk Intelligence
        </div>
        <h2 className="text-2xl font-black text-white mb-1">Tunisia Climate Risk Analysis</h2>
        <p className="text-gray-400 text-sm">Comprehensive climate risk assessment for all 24 governorates — flood, heat, drought, and long-term scenario projections.</p>
      </div>

      {/* Sub-navigation */}
      <div className="flex gap-1 rounded-xl border border-white/10 bg-white/5 p-1">
        {[
          { id: 'overview', label: 'Risk Overview' },
          { id: 'compare', label: 'Governorate Table' },
          { id: 'scenarios', label: '+2°C / +4°C Scenarios' },
          { id: 'regional', label: 'Regional Heatmap' },
        ].map(v => (
          <button key={v.id} onClick={() => setActiveView(v.id)}
            className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-all ${
              activeView === v.id ? 'bg-blue-600/80 text-white' : 'text-gray-400 hover:text-gray-200'
            }`}>
            {v.label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ── */}
      {activeView === 'overview' && (
        <div className="space-y-6">
          {/* KPI row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <ClimateKpiCard icon={Globe} label="Governorates" value={govCount} sub="All of Tunisia" color="#3b82f6" />
            <ClimateKpiCard icon={Activity} label="Avg Risk Score" value={avgRisk} sub="Out of 10" color="#f97316" />
            <ClimateKpiCard icon={Shield} label="Safest Region" value={safest} sub="Lowest risk score" color="#10b981" />
            <ClimateKpiCard icon={AlertTriangle} label="Highest Risk" value={riskiest} sub="Highest risk score" color="#ef4444" />
          </div>

          {/* Risk distribution pie + regional bar */}
          <div className="grid md:grid-cols-2 gap-6">
            <div className={CARD}>
              <p className="text-sm font-bold text-white mb-1">Risk Distribution</p>
              <p className="text-xs text-gray-500 mb-4">Governorates by climate risk category</p>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={riskDist} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                    {riskDist.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip content={({ active, payload }) => active && payload?.length ? (
                    <div className="rounded-lg border border-white/20 bg-[#111827] px-3 py-2 text-xs">
                      <p className="font-bold text-white">{payload[0].name}</p>
                      <p className="text-gray-400">{payload[0].value} governorates</p>
                    </div>
                  ) : null} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className={CARD}>
              <p className="text-sm font-bold text-white mb-1">Top Risk Governorates</p>
              <p className="text-xs text-gray-500 mb-4">Combined risk score (higher = more risk)</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={[...govRows].sort((a,b)=>(b.combined_risk_score||0)-(a.combined_risk_score||0)).slice(0,8)}
                  layout="vertical" margin={{ left: 8, right: 12 }}>
                  <XAxis type="number" domain={[0,10]} tick={{ fill:'#9ca3af', fontSize:10 }} />
                  <YAxis type="category" dataKey="governorate" tick={{ fill:'#9ca3af', fontSize:10 }} width={80} />
                  <Tooltip content={<DashTooltip />} />
                  <Bar dataKey="combined_risk_score" radius={4}>
                    {[...govRows].sort((a,b)=>(b.combined_risk_score||0)-(a.combined_risk_score||0)).slice(0,8).map((r, i) => (
                      <Cell key={i} fill={RISK_COLORS[r.risk_category]?.hex || '#888'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Sustainability vs Risk scatter */}
          <div className={CARD}>
            <p className="text-sm font-bold text-white mb-1">Sustainability vs Risk Score</p>
            <p className="text-xs text-gray-500 mb-4">Ideal: low risk (left) + high sustainability (top)</p>
            <ResponsiveContainer width="100%" height={280}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                <XAxis dataKey="combined_risk_score" name="Risk Score" type="number" domain={[0,10]}
                  tick={{ fill:'#9ca3af', fontSize:10 }} label={{ value:'Risk Score', position:'insideBottom', offset:-4, fill:'#6b7280', fontSize:10 }} />
                <YAxis dataKey="sustainability_score" name="Sustainability" type="number" domain={[0,100]}
                  tick={{ fill:'#9ca3af', fontSize:10 }} label={{ value:'Sustainability', angle:-90, position:'insideLeft', fill:'#6b7280', fontSize:10 }} />
                <Tooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0]?.payload;
                  const c = RISK_COLORS[d?.risk_category] || RISK_COLORS.Moderate;
                  return (
                    <div className="rounded-lg border border-white/20 bg-[#111827] px-3 py-2 text-xs space-y-0.5">
                      <p className="font-bold text-white">{d?.governorate}</p>
                      <p className="text-gray-400">Risk: <span style={{color: c.hex}}>{d?.combined_risk_score?.toFixed(1)}</span></p>
                      <p className="text-gray-400">Sustainability: <span className="text-blue-300">{d?.sustainability_score}%</span></p>
                      {d?.sustainability_grade && <p className="text-gray-400">Grade: <span className="font-bold" style={{color: SUSTAIN_GRADE_COLOR[d.sustainability_grade]}}>{d.sustainability_grade}</span></p>}
                    </div>
                  );
                }} />
                <Scatter data={govRows} fill="#FF6B35">
                  {govRows.map((r, i) => <Cell key={i} fill={RISK_COLORS[r.risk_category]?.hex || '#888'} />)}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* Price adjustment overview */}
          <div className={CARD}>
            <p className="text-sm font-bold text-white mb-1">Climate Price Adjustment by Governorate</p>
            <p className="text-xs text-gray-500 mb-4">% adjustment to property price driven by climate risk (+premium / −discount)</p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={[...govRows].sort((a,b)=>(a.price_adjustment_pct||0)-(b.price_adjustment_pct||0))} margin={{ left:0, right:12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                <XAxis dataKey="governorate" tick={{ fill:'#9ca3af', fontSize:9 }} angle={-35} textAnchor="end" height={52} />
                <YAxis tick={{ fill:'#9ca3af', fontSize:10 }} tickFormatter={v => `${v}%`} />
                <Tooltip content={({ active, payload, label }) => active && payload?.length ? (
                  <div className="rounded-lg border border-white/20 bg-[#111827] px-3 py-2 text-xs">
                    <p className="font-bold text-white">{label}</p>
                    <p className="text-gray-400">Adjustment: <span className={payload[0].value >= 0 ? 'text-green-400' : 'text-red-400'}>{payload[0].value?.toFixed(1)}%</span></p>
                  </div>
                ) : null} />
                <ReferenceLine y={0} stroke="#ffffff30" />
                <Bar dataKey="price_adjustment_pct" radius={3}>
                  {[...govRows].sort((a,b)=>(a.price_adjustment_pct||0)-(b.price_adjustment_pct||0)).map((r,i) => (
                    <Cell key={i} fill={(r.price_adjustment_pct||0) >= 0 ? '#10b981' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── GOVERNORATE TABLE ── */}
      {activeView === 'compare' && (
        <div className="space-y-5">
          <div className="flex gap-3 items-center">
            <div className="relative flex-1 max-w-sm">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search governorate…"
                className="w-full rounded-xl border border-white/15 bg-black/30 pl-8 pr-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500/50" />
            </div>
            {search && <button onClick={() => setSearch('')} className="text-gray-500 hover:text-white"><X size={14}/></button>}
          </div>

          {selectedGov && (
            <div className="rounded-2xl border border-blue-500/30 bg-blue-500/5 p-5 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-black text-white">{selectedGov.governorate}</h3>
                  <p className="text-xs text-gray-500">{selectedGov.climate_region} · {selectedGov.is_coastal ? 'Coastal' : 'Inland'}</p>
                </div>
                <button onClick={() => setSelectedGov(null)} className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-gray-400">
                  <X size={14}/>
                </button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-center">
                  <p className="text-xs text-gray-500 mb-1">Risk Score</p>
                  <p className="text-xl font-black" style={{color: RISK_COLORS[selectedGov.risk_category]?.hex}}>{(selectedGov.combined_risk_score||0).toFixed(1)}/10</p>
                  <RiskBadge level={selectedGov.risk_category} />
                </div>
                <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-center">
                  <p className="text-xs text-gray-500 mb-1">Sustainability</p>
                  <p className="text-xl font-black text-blue-300">{selectedGov.sustainability_score ?? '—'}%</p>
                  {selectedGov.sustainability_grade && <span className="text-sm font-bold" style={{color: SUSTAIN_GRADE_COLOR[selectedGov.sustainability_grade]}}>Grade {selectedGov.sustainability_grade}</span>}
                </div>
                <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-center">
                  <p className="text-xs text-gray-500 mb-1">Avg Temp</p>
                  <p className="text-xl font-black text-orange-400">{selectedGov.avg_temp_c ?? '—'}°C</p>
                  <p className="text-xs text-gray-600">{selectedGov.days_above_35c ?? '—'} days &gt;35°C/yr</p>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-center">
                  <p className="text-xs text-gray-500 mb-1">Rainfall</p>
                  <p className="text-xl font-black text-cyan-400">{selectedGov.avg_rainfall_mm ?? '—'} mm</p>
                  <p className="text-xs text-gray-600">annual avg</p>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Flood Risk', val: selectedGov.flood_risk },
                  { label: 'Heat Stress', val: selectedGov.heat_stress_risk },
                  { label: 'Drought', val: selectedGov.drought_risk },
                  { label: 'Earthquake', val: selectedGov.earthquake_risk },
                ].map(({label, val}) => (
                  <div key={label} className="rounded-lg border border-white/10 bg-white/5 p-3 text-center">
                    <p className="text-xs text-gray-500 mb-1.5">{label}</p>
                    <RiskBadge level={val || 'Low'} />
                  </div>
                ))}
              </div>
              {weatherLoading && <p className="text-xs text-gray-500 flex items-center gap-1.5"><Loader2 size={11} className="animate-spin"/>Loading live weather…</p>}
              {weather && (
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs font-bold text-white mb-3">Live Weather · {weather.source === 'live' ? '🟢 Live' : '⚪ Simulated'}</p>
                  <div className="grid grid-cols-3 md:grid-cols-6 gap-3 text-center">
                    {[
                      { label: 'Temperature', val: `${weather.current?.temperature}°C`, icon: Thermometer, color: '#f97316' },
                      { label: 'Humidity', val: `${weather.current?.humidity}%`, icon: Droplets, color: '#3b82f6' },
                      { label: 'Wind', val: `${weather.current?.wind_speed} km/h`, icon: Wind, color: '#8b5cf6' },
                      { label: 'Precipitation', val: `${weather.current?.precipitation} mm`, icon: CloudRain, color: '#06b6d4' },
                      { label: 'Heat Index', val: weather.heat_index?.level || '—', icon: Sun, color: '#f59e0b' },
                      { label: 'Drought SPI', val: weather.drought_spi?.level || '—', icon: FlameKindling, color: '#ef4444' },
                    ].map(({label, val, icon: Ic, color}) => (
                      <div key={label}>
                        <Ic size={14} style={{color}} className="mx-auto mb-1" />
                        <p className="text-xs font-bold text-white">{val}</p>
                        <p className="text-xs text-gray-500">{label}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-sm">
              <thead className="border-b border-white/10 bg-white/5">
                <tr>
                  {[
                    { label: 'Governorate', key: 'governorate' },
                    { label: 'Region', key: 'climate_region' },
                    { label: 'Risk Score', key: 'combined_risk_score' },
                    { label: 'Category', key: 'risk_category' },
                    { label: 'Sustainability', key: 'sustainability_score' },
                    { label: 'Flood', key: 'flood_risk' },
                    { label: 'Heat', key: 'heat_stress_risk' },
                    { label: 'Drought', key: 'drought_risk' },
                    { label: 'Price Adj %', key: 'price_adjustment_pct' },
                  ].map(({label, key}) => (
                    <th key={key} onClick={() => toggleSort(key)}
                      className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 cursor-pointer hover:text-white transition-colors">
                      <span className="flex items-center gap-1">{label}
                        {sortKey === key ? (sortDir === 'asc' ? <ChevronUp size={11} className="text-blue-400"/> : <ChevronDown size={11} className="text-blue-400"/>) : <ArrowUpDown size={11} className="text-gray-600"/>}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {govRows.map((r, i) => (
                  <tr key={r.governorate || i} onClick={() => handleSelectGov(r)}
                    className={`cursor-pointer transition-colors hover:bg-white/5 ${selectedGov?.governorate === r.governorate ? 'bg-blue-500/10' : ''}`}>
                    <td className="px-3 py-2.5 font-semibold text-white">{r.governorate}</td>
                    <td className="px-3 py-2.5 text-gray-400 text-xs">{r.climate_region || '—'}</td>
                    <td className="px-3 py-2.5">
                      <span className="font-bold" style={{color: RISK_COLORS[r.risk_category]?.hex || '#888'}}>{(r.combined_risk_score||0).toFixed(1)}</span>
                    </td>
                    <td className="px-3 py-2.5"><RiskBadge level={r.risk_category || 'Low'} /></td>
                    <td className="px-3 py-2.5 text-blue-300 font-semibold">{r.sustainability_score ?? '—'}{r.sustainability_score ? '%' : ''}</td>
                    <td className="px-3 py-2.5"><RiskBadge level={r.flood_risk || 'Low'} /></td>
                    <td className="px-3 py-2.5"><RiskBadge level={r.heat_stress_risk || 'Low'} /></td>
                    <td className="px-3 py-2.5"><RiskBadge level={r.drought_risk || 'Low'} /></td>
                    <td className="px-3 py-2.5">
                      <span className={(r.price_adjustment_pct||0) >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {(r.price_adjustment_pct||0) >= 0 ? '+' : ''}{(r.price_adjustment_pct||0).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
                {govRows.length === 0 && (
                  <tr><td colSpan={9} className="text-center text-gray-500 text-sm py-10">No governorates match search</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-600 flex items-center gap-1"><Info size={11}/>Click any row to see full details and live weather.</p>
        </div>
      )}

      {/* ── SCENARIOS ── */}
      {activeView === 'scenarios' && (
        <div className="space-y-6">
          <div className={CARD}>
            <p className="text-sm font-bold text-white mb-1">Climate Scenario Projections</p>
            <p className="text-xs text-gray-500 mb-4">Sustainability score change under +2°C and +4°C global warming. Negative = worsening conditions.</p>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={scenarioRows.slice(0, 20)} margin={{ left:0, right:12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                <XAxis dataKey="governorate" tick={{ fill:'#9ca3af', fontSize:9 }} angle={-35} textAnchor="end" height={56} />
                <YAxis tick={{ fill:'#9ca3af', fontSize:10 }} />
                <Tooltip content={({ active, payload, label }) => active && payload?.length ? (
                  <div className="rounded-lg border border-white/20 bg-[#111827] px-3 py-2 text-xs space-y-1">
                    <p className="font-bold text-white">{label}</p>
                    {payload.map((p,i) => <p key={i} style={{color: p.color}}>{p.name}: {p.value?.toFixed(2)}</p>)}
                  </div>
                ) : null} />
                <Legend wrapperStyle={{ fontSize: '11px', color: '#9ca3af' }} />
                <ReferenceLine y={0} stroke="#ffffff30" />
                <Bar dataKey="delta_2c" name="+2°C Δ" fill="#f59e0b" radius={2} />
                <Bar dataKey="delta_4c" name="+4°C Δ" fill="#ef4444" radius={2} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-sm">
              <thead className="border-b border-white/10 bg-white/5">
                <tr>
                  {['Governorate','Climate Region','Risk Category','Baseline Score','+2°C Score','+4°C Score','Δ +2°C','Δ +4°C'].map(h => (
                    <th key={h} className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {scenarioRows.map((r, i) => (
                  <tr key={r.governorate || i} className="hover:bg-white/5 transition-colors">
                    <td className="px-3 py-2.5 font-semibold text-white">{r.governorate}</td>
                    <td className="px-3 py-2.5 text-gray-400 text-xs">{r.climate_region || '—'}</td>
                    <td className="px-3 py-2.5"><RiskBadge level={r.risk_category || 'Low'} /></td>
                    <td className="px-3 py-2.5 text-gray-300">{r.baseline?.toFixed(1) ?? '—'}</td>
                    <td className="px-3 py-2.5 text-yellow-300">{r.plus_2c?.toFixed(1) ?? '—'}</td>
                    <td className="px-3 py-2.5 text-red-300">{r.plus_4c?.toFixed(1) ?? '—'}</td>
                    <td className="px-3 py-2.5">
                      <span className={(r.delta_2c||0) >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {(r.delta_2c||0) >= 0 ? '+' : ''}{(r.delta_2c||0).toFixed(2)}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={(r.delta_4c||0) >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {(r.delta_4c||0) >= 0 ? '+' : ''}{(r.delta_4c||0).toFixed(2)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-600 flex items-center gap-1"><Info size={11}/>Δ values show change in sustainability score from baseline. Negative = increased climate stress.</p>
        </div>
      )}

      {/* ── REGIONAL HEATMAP ── */}
      {activeView === 'regional' && (
        <div className="space-y-6">
          <div className={CARD}>
            <p className="text-sm font-bold text-white mb-1">Regional Climate Risk Heatmap</p>
            <p className="text-xs text-gray-500 mb-4">Average risk, sustainability, and price adjustment grouped by climate region</p>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={regionalRows} cx="50%" cy="50%" outerRadius={100}>
                <PolarGrid stroke="#ffffff15" />
                <PolarAngleAxis dataKey="climate_region" tick={{ fill:'#9ca3af', fontSize:10 }} />
                <PolarRadiusAxis angle={30} domain={[0,10]} tick={{ fill:'#9ca3af', fontSize:9 }} />
                <Radar name="Avg Risk" dataKey="avg_risk_score" stroke="#ef4444" fill="#ef4444" fillOpacity={0.25} />
                <Radar name="Avg Sustainability /10" dataKey="avg_sustainability" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} />
                <Legend wrapperStyle={{ fontSize: '11px', color: '#9ca3af' }} />
                <Tooltip content={<DashTooltip />} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            {regionalRows.map((r, i) => {
              const rcat = r.avg_risk_score >= 7.5 ? 'Very High' : r.avg_risk_score >= 5 ? 'High' : r.avg_risk_score >= 2.5 ? 'Moderate' : 'Low';
              const c = RISK_COLORS[rcat] || RISK_COLORS.Moderate;
              return (
                <div key={i} className={`rounded-xl border p-4 ${c.border} ${c.bg}`}>
                  <div className="flex items-center justify-between mb-3">
                    <p className="font-bold text-white">{r.climate_region}</p>
                    <RiskBadge level={rcat} />
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div>
                      <p className="text-lg font-black" style={{color: c.hex}}>{(r.avg_risk_score||0).toFixed(1)}</p>
                      <p className="text-xs text-gray-500">Avg Risk</p>
                    </div>
                    <div>
                      <p className="text-lg font-black text-blue-300">{(r.avg_sustainability||0).toFixed(0)}%</p>
                      <p className="text-xs text-gray-500">Sustainability</p>
                    </div>
                    <div>
                      <p className={`text-lg font-black ${(r.avg_price_adjustment_pct||0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {(r.avg_price_adjustment_pct||0) >= 0 ? '+' : ''}{(r.avg_price_adjustment_pct||0).toFixed(1)}%
                      </p>
                      <p className="text-xs text-gray-500">Price Adj</p>
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-2">{r.governorate_count} governorate{r.governorate_count !== 1 ? 's' : ''}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

// ── Page root ──────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'dashboard', label: 'Market Dashboard', icon: LayoutDashboard },
  { id: 'forecast',  label: 'Price Forecast',   icon: BarChart3       },
  { id: 'climate',   label: 'Climate Risk',      icon: Shield          },
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
            AI-powered market intelligence — real prices, forecasts, and full climate risk analysis for every governorate in Tunisia.
          </p>
        </section>

        <div className="flex gap-1 rounded-2xl border border-white/10 bg-white/5 p-1.5">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setActiveTab(id)}
              className={`flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-all
                ${activeTab === id
                  ? id === 'climate'
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                    : 'bg-[#FF6B35] text-white shadow-lg shadow-[#FF6B35]/20'
                  : 'text-gray-400 hover:text-gray-200'}`}>
              <Icon size={15} />{label}
            </button>
          ))}
        </div>

        {activeTab === 'dashboard' && <DashboardSection />}
        {activeTab === 'forecast'  && <PriceForecastSection />}
        {activeTab === 'climate'   && <ClimateRiskSection />}

      </div>
    </main>
  );
}
