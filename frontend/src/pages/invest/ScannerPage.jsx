import React, { useState, useEffect } from 'react';
import {
  TrendingUp, TrendingDown, CheckCircle2, AlertCircle,
  Building2, Home, Store, Trees, ScanSearch, Clock,
} from 'lucide-react';
import { scanListing, getScanHistory, getForecastDelegationList } from '../../services/api';

/* ── Design tokens ─────────────────────────────────────────── */
const CARD   = 'rounded-2xl border border-white/10 bg-white/5';
const INP    = 'w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2.5 text-sm ' +
               'text-white placeholder:text-gray-600 focus:outline-none ' +
               'focus:border-[#FF6B35]/60 focus:ring-1 focus:ring-[#FF6B35]/30 transition-colors';
const ORANGE = '#FF6B35';

const PTYPES = [
  { value: 'apartment',  label: 'Apartment',  icon: Building2 },
  { value: 'house',      label: 'House',       icon: Home      },
  { value: 'commercial', label: 'Commercial',  icon: Store     },
  { value: 'land',       label: 'Land',        icon: Trees     },
];

const GOVS = [
  'Tunis','Ariana','Ben Arous','La Manouba','Nabeul','Bizerte',
  'Béja','Jendouba','Zaghouan','Sousse','Monastir','Mahdia','Sfax',
  'Kairouan','Kasserine','Sidi Bouzid','Gabès','Médenine','Tataouine',
  'Gafsa','Tozeur','Kébili','Siliana','Le Kef',
];

const ASSESSMENT = {
  SEVERELY_UNDERVALUED: { label: 'Strong Value',  color: '#22c55e' },
  UNDERVALUED:          { label: 'Below Market',  color: '#86efac' },
  FAIRLY_PRICED:        { label: 'Fair Price',    color: '#f59e0b' },
  OVERPRICED:           { label: 'Above Market',  color: '#ef4444' },
};

const GRADE = {
  A: { label: 'Prime',   color: '#22c55e', desc: 'Exceptional opportunity'           },
  B: { label: 'Good',    color: '#3b82f6', desc: 'Solid fundamentals'                },
  C: { label: 'Fair',    color: '#f59e0b', desc: 'Average — proceed with care'        },
  D: { label: 'Caution', color: '#ef4444', desc: 'High risk or limited upside'        },
};

const EMPTY = {
  listing_price_tnd: '', surface_m2: '', property_type: 'apartment',
  governorate: 'Tunis', delegation: '', room_count: 3, floor_level: 0,
  has_parking: false, has_garden: false, has_pool: false, sea_view: false, elevator: false,
};

/* ── Score bar ─────────────────────────────────────────────── */
function ScoreBar({ value }) {
  const pct   = Math.min(value, 100);
  const color = pct >= 65 ? '#22c55e' : pct >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-white/[0.08] overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-sm font-bold w-9 text-right" style={{ color }}>
        {Math.round(value)}
      </span>
    </div>
  );
}

/* ── Metric row ────────────────────────────────────────────── */
function Row({ label, value, valueColor }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-white/[0.05] last:border-0">
      <span className="text-xs text-gray-500">{label}</span>
      <span className="text-sm font-semibold" style={{ color: valueColor || '#e5e7eb' }}>{value}</span>
    </div>
  );
}

/* ── Result panel ──────────────────────────────────────────── */
function Result({ result }) {
  const assessment = ASSESSMENT[result.undervaluation?.label] || ASSESSMENT.FAIRLY_PRICED;
  const grade      = GRADE[result.investment_grade]           || GRADE.C;
  const isBuy      = result.buy_signal?.signal === 'BUY_NOW';
  const p = result.pricing  || {};
  const y = result.yield    || {};
  const f = result.forecast || {};
  const z = result.zone     || {};

  return (
    <div className="space-y-4">

      {/* ── Verdict banner ─────────────────────────── */}
      <div className={`rounded-2xl border p-5 flex items-center justify-between
        ${isBuy
          ? 'bg-green-500/[0.06] border-green-500/20'
          : 'bg-yellow-500/[0.05] border-yellow-500/20'}`}>
        <div className="flex items-center gap-4">
          {isBuy
            ? <CheckCircle2 size={32} className="text-green-400 flex-shrink-0" />
            : <AlertCircle  size={32} className="text-yellow-400 flex-shrink-0" />}
          <div>
            <p className={`text-lg font-bold ${isBuy ? 'text-green-400' : 'text-yellow-400'}`}>
              {isBuy ? 'Buy Now' : 'Wait'}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {isBuy
                ? 'Market conditions favour this acquisition'
                : 'Better opportunities may emerge — monitor this deal'}
            </p>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Investment Score</p>
          <p className="text-2xl font-bold"
            style={{ color: result.opportunity_score >= 65 ? '#22c55e'
              : result.opportunity_score >= 40 ? '#f59e0b' : '#ef4444' }}>
            {Math.round(result.opportunity_score)}<span className="text-sm text-gray-500">/100</span>
          </p>
        </div>
      </div>

      {/* ── Key metrics strip ──────────────────────── */}
      <div className="grid grid-cols-4 gap-3">
        {[
          {
            label: 'Rating',
            value: grade.label,
            sub: grade.desc,
            color: grade.color,
          },
          {
            label: 'Market Position',
            value: assessment.label,
            sub: null,
            color: assessment.color,
          },
          {
            label: 'Annual Yield',
            value: `${y.gross_yield_pct}%`,
            sub: `≈ ${Math.round(y.monthly_rent_est || 0).toLocaleString()} TND/mo`,
            color: ORANGE,
          },
          {
            label: 'Net Yield',
            value: `${y.net_yield_pct}%`,
            sub: 'After estimated costs',
            color: '#3b82f6',
          },
        ].map(m => (
          <div key={m.label} className={`${CARD} p-4 text-center`}>
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
              {m.label}
            </p>
            <p className="text-base font-bold leading-tight" style={{ color: m.color }}>{m.value}</p>
            {m.sub && <p className="text-[10px] text-gray-500 mt-1 leading-tight">{m.sub}</p>}
          </div>
        ))}
      </div>

      {/* ── Score bar ──────────────────────────────── */}
      <div className={`${CARD} px-5 py-4`}>
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-white">Investment Score</p>
          <span className="text-xs text-gray-500">Out of 100</span>
        </div>
        <ScoreBar value={result.opportunity_score} />
        <p className="mt-2 text-xs text-gray-500">
          {result.opportunity_score >= 65
            ? 'Strong opportunity — conditions are favourable for acquisition'
            : result.opportunity_score >= 40
            ? 'Decent opportunity with manageable risk'
            : 'Below-average opportunity — review carefully before proceeding'}
        </p>
      </div>

      {/* ── Detail cards ───────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Pricing */}
        <div className={`${CARD} p-5`}>
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-4">
            Pricing Analysis
          </p>
          <Row label="Asking Price"
            value={`${Math.round(p.listing_price_tnd || 0).toLocaleString()} TND`} />
          <Row label="Fair Market Est."
            value={`${Math.round(p.fair_value_est_tnd || 0).toLocaleString()} TND`} />
          <Row label="Price vs Market"
            value={`${p.price_gap_pct > 0 ? '+' : ''}${p.price_gap_pct}%`}
            valueColor={p.price_gap_pct <= 0 ? '#22c55e' : '#ef4444'} />
          <Row label="Zone Avg / m²"
            value={`${Math.round(p.zone_avg_pm2 || 0).toLocaleString()} TND`} />
          <Row label="This Deal / m²"
            value={`${Math.round(p.listing_pm2 || 0).toLocaleString()} TND`} />
        </div>

        {/* Outlook */}
        <div className={`${CARD} p-5`}>
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-4">
            Price Outlook
          </p>
          <Row label="Market Direction"
            value={
              <span className={`flex items-center gap-1
                ${f.direction === 'UP' ? 'text-green-400' : 'text-red-400'}`}>
                {f.direction === 'UP'
                  ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                {f.direction}
              </span>
            } />
          <Row label="Next 6 Months"
            value={`+${f.forecast_6m_pct}%`}
            valueColor="#22c55e" />
          <Row label="Next 12 Months"
            value={`+${f.forecast_12m_pct}%`}
            valueColor="#22c55e" />
          <Row label="Forecast Confidence"
            value={`${((f.reliability || 0) * 100).toFixed(0)}%`} />
        </div>

        {/* Area */}
        <div className={`${CARD} p-5`}>
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-4">
            Area Dynamics
          </p>
          <Row label="Buyer Demand"
            value={`${z.demand_intensity || 0}/100`} />
          <Row label="Market Balance"
            value={
              z.supply_demand_ratio < 1     ? 'High Demand'
              : z.supply_demand_ratio < 1.3 ? 'Balanced'
              : 'Oversupply'
            } />
          <Row label="Vacancy Rate"
            value={`${z.vacancy_rate_pct || 0}%`} />
          <Row label="Avg Time to Sell"
            value={`${Math.round(z.median_dom || 0)} days`} />
        </div>
      </div>
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────── */
export default function ScannerPage() {
  const [form,    setForm]    = useState(EMPTY);
  const [delegs,  setDelegs]  = useState([]);
  const [result,  setResult]  = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err,     setErr]     = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  useEffect(() => {
    getScanHistory().then(r => setHistory(r.data || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!form.governorate) return;
    getForecastDelegationList(form.governorate)
      .then(r => setDelegs(r.data?.delegations || r.data || []))
      .catch(() => setDelegs([]));
  }, [form.governorate]);

  const handleScan = async (e) => {
    e.preventDefault();
    if (!form.listing_price_tnd || !form.surface_m2) {
      setErr('Asking price and surface area are required.');
      return;
    }
    setErr('');
    setLoading(true);
    try {
      const res = await scanListing({
        ...form,
        listing_price_tnd:    parseFloat(form.listing_price_tnd),
        surface_m2:           parseFloat(form.surface_m2),
        room_count:           parseInt(form.room_count),
        floor_level:          parseInt(form.floor_level),
        days_active:          15,
        repost_count:         0,
        price_reduction_count: 0,
      });
      setResult(res.data);
      setHistory(h => [res.data, ...h].slice(0, 20));
    } catch (e) {
      setErr(e?.response?.data?.error || 'Analysis failed. Please check your connection and try again.');
    } finally { setLoading(false); }
  };

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold text-white">Deal Scanner</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          Enter any listing to get an instant investment analysis
        </p>
      </div>

      {/* ── Main layout ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">

        {/* Form */}
        <div className={`xl:col-span-2 ${CARD} p-6 space-y-5 self-start`}>
          <p className="text-sm font-semibold text-white">Property Details</p>

          {err && (
            <div className="px-4 py-3 rounded-xl border border-red-500/25 bg-red-500/[0.07]
              text-red-400 text-sm">
              {err}
            </div>
          )}

          {/* Type */}
          <div className="grid grid-cols-4 gap-2">
            {PTYPES.map(({ value, label, icon: Icon }) => (
              <button key={value} type="button" onClick={() => set('property_type', value)}
                className={`flex flex-col items-center gap-1.5 py-3 rounded-xl border
                  text-[11px] font-medium transition-all
                  ${form.property_type === value
                    ? 'border-[#FF6B35]/50 bg-[#FF6B35]/10 text-[#FF6B35]'
                    : 'border-white/10 bg-white/[0.03] text-gray-400 hover:border-white/20'}`}>
                <Icon size={14} />{label}
              </button>
            ))}
          </div>

          {/* Price + Surface */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Asking Price (TND) <span className="text-[#FF6B35]">*</span>
              </label>
              <input type="number" className={INP} value={form.listing_price_tnd}
                onChange={e => set('listing_price_tnd', e.target.value)}
                placeholder="280 000" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Size (m²) <span className="text-[#FF6B35]">*</span>
              </label>
              <input type="number" className={INP} value={form.surface_m2}
                onChange={e => set('surface_m2', e.target.value)}
                placeholder="110" />
            </div>
          </div>

          {/* Location */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Governorate</label>
              <select className={INP} value={form.governorate}
                onChange={e => set('governorate', e.target.value)}>
                {GOVS.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Area</label>
              {delegs.length > 0 ? (
                <select className={INP} value={form.delegation}
                  onChange={e => set('delegation', e.target.value)}>
                  <option value="">— Any —</option>
                  {delegs.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              ) : (
                <input className={INP} value={form.delegation}
                  onChange={e => set('delegation', e.target.value)}
                  placeholder="e.g. La Marsa" />
              )}
            </div>
          </div>

          {/* Rooms + Floor */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Rooms</label>
              <input type="number" min={1} className={INP} value={form.room_count}
                onChange={e => set('room_count', e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Floor</label>
              <input type="number" min={0} className={INP} value={form.floor_level}
                onChange={e => set('floor_level', e.target.value)} />
            </div>
          </div>

          {/* Features */}
          <div>
            <p className="text-xs font-medium text-gray-400 mb-2.5">Features</p>
            <div className="grid grid-cols-2 gap-2">
              {[
                ['has_parking', 'Parking'],
                ['has_garden',  'Garden'],
                ['has_pool',    'Pool'],
                ['sea_view',    'Sea View'],
                ['elevator',    'Elevator'],
              ].map(([key, label]) => (
                <label key={key}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl border
                    cursor-pointer transition-all text-xs
                    ${form[key]
                      ? 'border-[#FF6B35]/40 bg-[#FF6B35]/8 text-[#FF6B35]'
                      : 'border-white/10 bg-white/[0.03] text-gray-400 hover:border-white/20'}`}>
                  <input type="checkbox" className="hidden"
                    checked={form[key]} onChange={e => set(key, e.target.checked)} />
                  <span className={`w-3.5 h-3.5 rounded border flex-shrink-0
                    flex items-center justify-center
                    ${form[key] ? 'bg-[#FF6B35] border-[#FF6B35]' : 'border-gray-600'}`}>
                    {form[key] && <span className="text-[8px] text-white font-black">✓</span>}
                  </span>
                  {label}
                </label>
              ))}
            </div>
          </div>

          {/* Submit */}
          <button onClick={handleScan} disabled={loading}
            className="w-full py-3 rounded-xl bg-[#FF6B35] text-white font-semibold text-sm
              hover:bg-[#e55a1f] disabled:opacity-50 transition-colors
              shadow-lg shadow-[#FF6B35]/20 flex items-center justify-center gap-2">
            {loading
              ? <><div className="animate-spin h-4 w-4 rounded-full border-2 border-white border-t-transparent" />Analyzing…</>
              : <><ScanSearch size={14} />Analyze Investment</>
            }
          </button>
        </div>

        {/* Results */}
        <div className="xl:col-span-3">
          {result ? (
            <Result result={result} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full min-h-[420px]
              rounded-2xl border border-dashed border-white/[0.1] text-center px-10">
              <div className="w-14 h-14 rounded-2xl bg-white/[0.04] flex items-center justify-center mb-5">
                <ScanSearch size={24} className="text-gray-600" />
              </div>
              <p className="text-base font-semibold text-gray-300">No analysis yet</p>
              <p className="text-sm text-gray-500 mt-2">
                Fill in the property details and click Analyze Investment
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Scan history ───────────────────────────────────────── */}
      {history.length > 0 && (
        <div className={CARD + ' overflow-hidden'}>
          <div className="px-6 py-4 border-b border-white/10 flex items-center gap-2">
            <Clock size={13} className="text-gray-500" />
            <p className="text-sm font-semibold text-white">Recent Analyses</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {['Location', 'Type', 'Price', 'Rating', 'Verdict', 'Yield', 'Score'].map(h => (
                    <th key={h} className="px-5 py-3 text-left text-[10px] font-semibold
                      text-gray-500 uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {history.slice(0, 8).map((h, i) => {
                  const g  = GRADE[h.investment_grade];
                  const isBuy = h.buy_signal === 'BUY_NOW';
                  return (
                    <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-5 py-3.5 text-sm text-white font-medium">
                        {h.delegation || h.governorate || '—'}
                      </td>
                      <td className="px-5 py-3.5 text-sm text-gray-400 capitalize">
                        {h.property_type}
                      </td>
                      <td className="px-5 py-3.5 text-sm text-gray-300">
                        {Math.round(h.listing_price_tnd || 0).toLocaleString()} TND
                      </td>
                      <td className="px-5 py-3.5">
                        {g && (
                          <span className="text-xs font-bold px-2 py-0.5 rounded-lg"
                            style={{ background: g.color + '18', color: g.color,
                              border: `1px solid ${g.color}25` }}>
                            {g.label}
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`text-xs font-semibold
                          ${isBuy ? 'text-green-400' : 'text-yellow-400'}`}>
                          {isBuy ? 'Buy Now' : 'Wait'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-sm font-semibold" style={{ color: ORANGE }}>
                        {(h.gross_yield_pct || 0).toFixed(1)}%
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="text-sm font-bold"
                          style={{ color: (h.opportunity_score || 0) >= 65 ? '#22c55e'
                            : (h.opportunity_score || 0) >= 40 ? '#f59e0b' : '#ef4444' }}>
                          {Math.round(h.opportunity_score || 0)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
