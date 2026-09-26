import React, { useState, useEffect } from 'react';
import {
  Plus, Trash2, RefreshCw, TrendingUp, TrendingDown,
  Building2, Home, Store, Trees, X, ChevronDown, ChevronUp,
} from 'lucide-react';
import {
  getPortfolioAssets, addPortfolioAsset, deletePortfolioAsset,
  scorePortfolio, scorePortfolioAsset, getForecastDelegationList,
} from '../../services/api';

/* ── Design tokens ─────────────────────────────────────────── */
const CARD  = 'rounded-2xl border border-white/10 bg-white/5';
const INP   = 'w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2.5 text-sm ' +
              'text-white placeholder:text-gray-600 focus:outline-none ' +
              'focus:border-[#FF6B35]/60 focus:ring-1 focus:ring-[#FF6B35]/30 transition-colors';
const ORANGE = '#FF6B35';

const GRADE_COLOR = { A: '#22c55e', B: '#3b82f6', C: '#f59e0b', D: '#ef4444' };
const GRADE_LABEL = { A: 'Prime',   B: 'Good',    C: 'Fair',    D: 'Caution' };
const RISK_COLOR  = { Low: '#22c55e', Medium: '#f59e0b', High: '#ef4444' };

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

const EMPTY_FORM = {
  property_name: '', property_type: 'apartment', governorate: 'Tunis',
  delegation: '', surface_m2: '', room_count: 3, floor_level: 0, amenity_score: 1,
  acquisition_price_tnd: '', acquisition_date: new Date().toISOString().slice(0, 10),
  is_rented: false,
  monthly_rent_tnd: '', monthly_opex_tnd: '', notes: '',
};

/* ── Add Asset Drawer ──────────────────────────────────────── */
function AddDrawer({ onClose, onSave }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [delegs, setDelegs] = useState([]);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!form.governorate) {
      setDelegs([]);
      return;
    }
    getForecastDelegationList(form.governorate)
      .then(r => setDelegs(r.data?.delegations || r.data || []))
      .catch(() => setDelegs([]));
  }, [form.governorate]);

  const submit = async (e) => {
    e?.preventDefault();
    if (!form.property_name.trim())      { setErr('Property name is required.'); return; }
    if (!form.acquisition_price_tnd)     { setErr('Purchase price is required.'); return; }
    if (!form.surface_m2)                { setErr('Surface area is required.');   return; }
    setSaving(true);
    try {
      const res = await addPortfolioAsset({
        ...form,
        surface_m2:            parseFloat(form.surface_m2),
        acquisition_price_tnd: parseFloat(form.acquisition_price_tnd),
        monthly_rent_tnd:      parseFloat(form.monthly_rent_tnd  || 0),
        monthly_opex_tnd:      parseFloat(form.monthly_opex_tnd || 0),
      });
      onSave(res.data);
    } catch (e) {
      setErr(e?.response?.data?.error || 'Could not save. Please try again.');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="w-full max-w-[480px] bg-[#0B0F19] border-l border-white/10
        flex flex-col shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/10">
          <div>
            <h2 className="text-base font-bold text-white">Add Property</h2>
            <p className="text-xs text-gray-500 mt-0.5">Track this asset in your portfolio</p>
          </div>
          <button onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg
              text-gray-500 hover:text-white hover:bg-white/[0.06] transition-colors">
            <X size={15} />
          </button>
        </div>

        {/* Form */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {err && (
            <div className="px-4 py-3 rounded-xl border border-red-500/30 bg-red-500/8
              text-red-400 text-sm">
              {err}
            </div>
          )}

          {/* Property type */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-2">Property Type</label>
            <div className="grid grid-cols-4 gap-2">
              {PTYPES.map(({ value, label, icon: Icon }) => (
                <button key={value} type="button" onClick={() => set('property_type', value)}
                  className={`flex flex-col items-center gap-1.5 py-3 rounded-xl border
                    text-[11px] font-medium transition-all
                    ${form.property_type === value
                      ? 'border-[#FF6B35]/50 bg-[#FF6B35]/10 text-[#FF6B35]'
                      : 'border-white/10 bg-white/[0.03] text-gray-400 hover:border-white/20'}`}>
                  <Icon size={15} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Name */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              Property Name <span className="text-[#FF6B35]">*</span>
            </label>
            <input className={INP} value={form.property_name}
              onChange={e => set('property_name', e.target.value)}
              placeholder="e.g. Carthage Residence" />
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
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Area / Delegation</label>
              <input
                list="portfolio-delegations"
                className={INP}
                value={form.delegation}
                onChange={e => set('delegation', e.target.value)}
                placeholder="e.g. La Marsa" />
              <datalist id="portfolio-delegations">
                {delegs.map(d => <option key={d} value={d} />)}
              </datalist>
              <p className="mt-1 text-[10px] text-gray-600">Type to search delegations in the selected governorate.</p>
            </div>
          </div>

          {/* Dimensions */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Size (m²) <span className="text-[#FF6B35]">*</span>
              </label>
              <input type="number" className={INP} value={form.surface_m2}
                onChange={e => set('surface_m2', e.target.value)} placeholder="120" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Rooms</label>
              <input type="number" min={1} className={INP} value={form.room_count}
                onChange={e => set('room_count', parseInt(e.target.value))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Floor</label>
              <input type="number" min={0} className={INP} value={form.floor_level}
                onChange={e => set('floor_level', parseInt(e.target.value))} />
            </div>
          </div>

          {/* Pricing */}
          <div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Purchase Price (TND) <span className="text-[#FF6B35]">*</span>
              </label>
              <input type="number" className={INP} value={form.acquisition_price_tnd}
                onChange={e => set('acquisition_price_tnd', e.target.value)}
                placeholder="250 000" />
            </div>
          </div>

          {/* Date */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Purchase Date</label>
            <input type="date" className={INP} value={form.acquisition_date}
              onChange={e => set('acquisition_date', e.target.value)} />
          </div>

          {/* Rental toggle */}
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <label className="flex items-center justify-between cursor-pointer">
              <div>
                <p className="text-sm font-medium text-white">Currently Rented</p>
                <p className="text-xs text-gray-500 mt-0.5">Track rental income and expenses</p>
              </div>
              <button type="button" onClick={() => set('is_rented', !form.is_rented)}
                className={`relative w-10 h-[22px] rounded-full transition-colors
                  ${form.is_rented ? 'bg-[#FF6B35]' : 'bg-white/[0.1]'}`}>
                <span className={`absolute top-[3px] w-4 h-4 rounded-full bg-white shadow
                  transition-transform
                  ${form.is_rented ? 'translate-x-5' : 'translate-x-[3px]'}`} />
              </button>
            </label>
            {form.is_rented && (
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Monthly Rent (TND)</label>
                  <input type="number" className={INP} value={form.monthly_rent_tnd}
                    onChange={e => set('monthly_rent_tnd', e.target.value)} placeholder="1 200" />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Monthly Costs (TND)</label>
                  <input type="number" className={INP} value={form.monthly_opex_tnd}
                    onChange={e => set('monthly_opex_tnd', e.target.value)} placeholder="200" />
                </div>
              </div>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Notes</label>
            <textarea className={INP + ' h-20 resize-none'} value={form.notes}
              onChange={e => set('notes', e.target.value)}
              placeholder="Any additional details…" />
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-5 border-t border-white/10 flex gap-3">
          <button type="button" onClick={onClose}
            className="flex-1 py-2.5 rounded-xl border border-white/[0.1]
              text-sm text-gray-300 hover:bg-white/[0.04] transition-colors">
            Cancel
          </button>
          <button onClick={submit} disabled={saving}
            className="flex-1 py-2.5 rounded-xl bg-[#FF6B35] text-white text-sm font-semibold
              hover:bg-[#e55a1f] disabled:opacity-50 transition-colors
              shadow-lg shadow-[#FF6B35]/20">
            {saving ? 'Saving…' : 'Add to Portfolio'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Asset Row ─────────────────────────────────────────────── */
function AssetRow({ asset: a, score: s, onDelete, onScore, scoring }) {
  const [expanded, setExpanded] = useState(false);
  const gc   = GRADE_COLOR[s?.grade];
  const gl   = GRADE_LABEL[s?.grade];
  const gain = a.unrealized_gain_pct ?? 0;
  const Icon = PTYPES.find(t => t.value === a.property_type)?.icon || Building2;

  return (
    <>
      <tr className="border-b border-white/[0.05] hover:bg-white/[0.02] transition-colors group">

        {/* Property */}
        <td className="px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-white/[0.05] flex items-center justify-center flex-shrink-0">
              <Icon size={14} className="text-gray-400" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white truncate max-w-[180px]">
                {a.property_name}
              </p>
              <p className="text-xs text-gray-500">
                {[a.delegation, a.governorate].filter(Boolean).join(', ')}
              </p>
            </div>
          </div>
        </td>

        {/* Surface */}
        <td className="px-4 py-4 text-sm text-gray-300">{a.surface_m2} m²</td>

        {/* Purchase price */}
        <td className="px-4 py-4 text-sm text-gray-300 text-right">
          {Math.round(a.acquisition_price_tnd).toLocaleString()}
          <span className="text-xs text-gray-600 ml-1">TND</span>
        </td>

        {/* Gain */}
        <td className="px-4 py-4 text-right">
          <span className={`text-sm font-semibold ${gain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {gain > 0 ? '+' : ''}{gain}%
          </span>
        </td>

        {/* Yield */}
        <td className="px-4 py-4 text-right">
          <span className="text-sm font-semibold" style={{ color: ORANGE }}>
            {s?.yield?.gross_yield_pct != null ? `${s.yield.gross_yield_pct}%` : '—'}
          </span>
        </td>

        {/* Rating */}
        <td className="px-4 py-4 text-center">
          {s?.grade ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-lg text-xs font-bold"
              style={{ background: gc + '18', color: gc, border: `1px solid ${gc}25` }}>
              {gl}
            </span>
          ) : (
            <span className="text-xs text-gray-600">—</span>
          )}
        </td>

        {/* Rented */}
        <td className="px-4 py-4 text-center">
          {a.is_rented ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
              {Math.round(a.monthly_rent_tnd).toLocaleString()} TND
            </span>
          ) : (
            <span className="text-xs text-gray-600">—</span>
          )}
        </td>

        {/* Actions */}
        <td className="px-4 py-4">
          <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button onClick={() => setExpanded(e => !e)}
              className="w-7 h-7 flex items-center justify-center rounded-lg
                text-gray-500 hover:text-white hover:bg-white/[0.06] transition-colors"
              title="View details">
              {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
            <button onClick={() => onScore(a.id)} disabled={scoring}
              className="w-7 h-7 flex items-center justify-center rounded-lg
                text-gray-500 hover:text-white hover:bg-white/[0.06] transition-colors disabled:opacity-40"
              title="Refresh score">
              <RefreshCw size={13} className={scoring ? 'animate-spin' : ''} />
            </button>
            <button onClick={() => onDelete(a.id)}
              className="w-7 h-7 flex items-center justify-center rounded-lg
                text-gray-600 hover:text-red-400 hover:bg-red-500/[0.08] transition-colors"
              title="Remove">
              <Trash2 size={13} />
            </button>
          </div>
        </td>
      </tr>

      {/* Expanded detail row */}
      {expanded && s && (
        <tr className="border-b border-white/[0.05] bg-white/[0.015]">
          <td colSpan={8} className="px-5 py-4">
            <div className="flex flex-wrap gap-6 text-xs">
              {/* IRR */}
              <div>
                <p className="text-gray-500 mb-1 uppercase tracking-wider">Est. IRR</p>
                <p className="font-bold text-blue-400">
                  {s.irr?.irr_pct != null ? `${s.irr.irr_pct}%` : '—'}
                </p>
              </div>
              {/* Risk */}
              <div>
                <p className="text-gray-500 mb-1 uppercase tracking-wider">Risk Level</p>
                <p className="font-bold" style={{ color: RISK_COLOR[s.risk?.risk_level] || '#9ca3af' }}>
                  {s.risk?.risk_level || '—'}
                </p>
              </div>
              {/* 6m forecast */}
              {s.forecast && (
                <div>
                  <p className="text-gray-500 mb-1 uppercase tracking-wider">6-Month Outlook</p>
                  <p className="font-bold text-green-400">+{s.forecast.forecast_6m_pct}%</p>
                </div>
              )}
              {/* 12m forecast */}
              {s.forecast && (
                <div>
                  <p className="text-gray-500 mb-1 uppercase tracking-wider">12-Month Outlook</p>
                  <p className="font-bold text-green-400">+{s.forecast.forecast_12m_pct}%</p>
                </div>
              )}
              {/* Net yield */}
              {s.yield?.net_yield_pct != null && (
                <div>
                  <p className="text-gray-500 mb-1 uppercase tracking-wider">Net Yield</p>
                  <p className="font-bold" style={{ color: ORANGE }}>{s.yield.net_yield_pct}%</p>
                </div>
              )}
              {/* Holding days */}
              <div>
                <p className="text-gray-500 mb-1 uppercase tracking-wider">Held</p>
                <p className="font-bold text-white">{a.holding_days} days</p>
              </div>
              {/* Notes */}
              {a.notes && (
                <div className="flex-1 min-w-[160px]">
                  <p className="text-gray-500 mb-1 uppercase tracking-wider">Notes</p>
                  <p className="text-gray-300">{a.notes}</p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/* ── Page ──────────────────────────────────────────────────── */
export default function PortfolioPage() {
  const [assets,  setAssets]  = useState([]);
  const [scores,  setScores]  = useState({});
  const [scoring, setScoring] = useState({});
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [summary, setSummary] = useState(null);

  const loadAssets = async () => {
    setLoading(true);
    try {
      const r = await getPortfolioAssets();
      setAssets(r.data);
    } catch (err) {
      if (err?.response?.status === 401) {
        window.location.href = '/login';
      }
    } finally {
      setLoading(false);
    }
  };

  const loadScores = async () => {
    try {
      const r = await scorePortfolio();
      const map = {};
      (r.data.assets || []).forEach(e => { if (e.asset?.id) map[e.asset.id] = e.score; });
      setScores(map);
      setSummary(r.data.summary);
    } catch {}
  };

  useEffect(() => { loadAssets().then(loadScores); }, []);

  const handleAdd = (a) => { setAssets(p => [a, ...p]); setShowAdd(false); scoreOne(a.id); };

  const handleDelete = async (id) => {
    if (!window.confirm('Remove this property from your portfolio?')) return;
    await deletePortfolioAsset(id);
    setAssets(p => p.filter(x => x.id !== id));
    setScores(s => { const c = { ...s }; delete c[id]; return c; });
  };

  const scoreOne = async (id) => {
    setScoring(s => ({ ...s, [id]: true }));
    try {
      const r = await scorePortfolioAsset(id);
      setScores(s => ({ ...s, [id]: r.data.score }));
    } catch {}
    finally { setScoring(s => ({ ...s, [id]: false })); }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-72">
      <div className="animate-spin h-7 w-7 rounded-full border-2 border-[#FF6B35] border-t-transparent" />
    </div>
  );

  const hasSummary = summary && assets.length > 0;

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">My Portfolio</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            {assets.length > 0
              ? `${assets.length} ${assets.length === 1 ? 'property' : 'properties'} tracked`
              : 'No properties yet'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {assets.length > 0 && (
            <button onClick={loadScores}
              className="flex items-center gap-2 px-4 py-2 rounded-xl border border-white/[0.1]
                text-sm text-gray-300 hover:bg-white/[0.04] transition-colors">
              <RefreshCw size={13} /> Refresh Scores
            </button>
          )}
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#FF6B35] text-white
              text-sm font-semibold hover:bg-[#e55a1f] transition-colors shadow-lg shadow-[#FF6B35]/20">
            <Plus size={13} /> Add Property
          </button>
        </div>
      </div>

      {/* ── Summary KPIs ───────────────────────────────── */}
      {hasSummary && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {[
            {
              label: 'Portfolio Value',
              value: `${Math.round((summary.total_value_tnd || 0) / 1000)}k TND`,
              color: ORANGE,
            },
            {
              label: 'Total Return',
              value: `${summary.total_return_pct > 0 ? '+' : ''}${summary.total_return_pct}%`,
              color: summary.total_return_pct >= 0 ? '#22c55e' : '#ef4444',
            },
            {
              label: 'Avg Annual Yield',
              value: `${summary.avg_gross_yield_pct}%`,
              color: ORANGE,
            },
            {
              label: 'Avg IRR',
              value: `${summary.avg_irr_pct}%`,
              color: '#3b82f6',
            },
            {
              label: 'Risk Profile',
              value: summary.avg_risk_score < 35 ? 'Low'
                   : summary.avg_risk_score < 65 ? 'Moderate' : 'Elevated',
              color: summary.avg_risk_score < 35 ? '#22c55e'
                   : summary.avg_risk_score < 65 ? '#f59e0b' : '#ef4444',
            },
          ].map(item => (
            <div key={item.label}
              className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4">
              <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest mb-2">
                {item.label}
              </p>
              <p className="text-lg font-bold" style={{ color: item.color }}>{item.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Table / Empty state ─────────────────────────── */}
      {assets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-28 text-center
          rounded-2xl border border-dashed border-white/[0.1]">
          <div className="w-14 h-14 rounded-2xl bg-white/[0.04] flex items-center justify-center mb-5">
            <Building2 size={24} className="text-gray-600" />
          </div>
          <h2 className="text-base font-semibold text-gray-300">Your portfolio is empty</h2>
          <p className="text-sm text-gray-500 mt-2 mb-7 max-w-xs">
            Add properties to track performance, yield, and capital appreciation.
          </p>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#FF6B35]
              text-white text-sm font-semibold hover:bg-[#e55a1f] transition-colors
              shadow-lg shadow-[#FF6B35]/20">
            <Plus size={14} /> Add First Property
          </button>
        </div>
      ) : (
        <div className={CARD + ' overflow-hidden'}>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  {[
                    { label: 'Property',        align: 'left',   cls: 'pl-5'  },
                    { label: 'Size',             align: 'left',   cls: 'pl-4'  },
                    { label: 'Purchase Price',   align: 'right',  cls: 'px-4'  },
                    { label: 'Capital Gain',     align: 'right',  cls: 'px-4'  },
                    { label: 'Annual Yield',     align: 'right',  cls: 'px-4'  },
                    { label: 'Rating',           align: 'center', cls: 'px-4'  },
                    { label: 'Rental Income',    align: 'center', cls: 'px-4'  },
                    { label: '',                 align: 'right',  cls: 'pr-4'  },
                  ].map(h => (
                    <th key={h.label}
                      className={`py-3.5 text-[10px] font-semibold text-gray-500 uppercase
                        tracking-wider ${h.cls} text-${h.align}`}>
                      {h.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {assets.map(a => (
                  <AssetRow
                    key={a.id}
                    asset={a}
                    score={scores[a.id]}
                    onDelete={handleDelete}
                    onScore={scoreOne}
                    scoring={!!scoring[a.id]}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showAdd && <AddDrawer onClose={() => setShowAdd(false)} onSave={handleAdd} />}
    </div>
  );
}
