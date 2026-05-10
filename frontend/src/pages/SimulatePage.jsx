import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  Play, Square, RotateCcw, Loader2, CheckCircle2, AlertTriangle,
  Trash2, RefreshCw, Activity, TrendingUp, TrendingDown, Building2,
  Zap, Droplets, Shield, Home, Flame, Wind, Users, BarChart2,
  FlaskConical, Map, ChevronDown, ChevronUp, Clock,
  ArrowUpRight, ArrowDownRight, Minus, Cpu,
} from 'lucide-react';
import {
  simStart, simListRuns, simGetRunDetail, simDeleteRun,
  simGetTimeseries, simGetMetrics, simGetAgents, simCompare, simGetZones,
} from '../services/api';

/* ─── Data ──────────────────────────────────────────────────────────────── */
const SCENARIOS = [
  { id:'baseline',            label:'Baseline',           icon:TrendingUp,   color:'#6366f1', badge:'Neutral'  },
  { id:'infrastructure_push', label:'Infrastructure Push',icon:Building2,    color:'#10b981', badge:'Positive' },
  { id:'interest_rate_hike',  label:'Rate Hike',          icon:TrendingDown, color:'#f59e0b', badge:'Negative' },
  { id:'liquidity_crunch',    label:'Liquidity Crunch',   icon:Droplets,     color:'#ef4444', badge:'Negative' },
  { id:'policy_tightening',   label:'Policy Tightening',  icon:Shield,       color:'#8b5cf6', badge:'Neutral'  },
  { id:'monetary_easing',     label:'Monetary Easing',    icon:Zap,          color:'#06b6d4', badge:'Positive' },
  { id:'supply_expansion',    label:'Supply Expansion',   icon:Home,         color:'#84cc16', badge:'Neutral'  },
  { id:'speculative_boom',    label:'Speculative Boom',   icon:Flame,        color:'#f97316', badge:'Volatile' },
  { id:'climate_stress',      label:'Climate Stress',     icon:Wind,         color:'#64748b', badge:'Negative' },
];
const SCENARIOS_MAP = Object.fromEntries(SCENARIOS.map(s => [s.id, s]));

const SCALES = [
  { id:'tiny',   label:'Tiny',   sub:'~40 agents',  agents:{buyer:20, seller:10, broker:2, developer:2, bank:1, speculator:3,  government:1} },
  { id:'medium', label:'Medium', sub:'~200 agents', agents:{buyer:100,seller:50, broker:10,developer:8, bank:4, speculator:20, government:2} },
  { id:'large',  label:'Large',  sub:'~500 agents', agents:{buyer:260,seller:130,broker:25,developer:20,bank:10,speculator:50, government:5} },
];

const AGENT_COLORS = {
  buyer:'#2D8A5E', seller:'#C94F2E', broker:'#1A5FAB',
  developer:'#B87A14', speculator:'#9B4F96', bank:'#6b7280', government:'#3D6B5E',
};

// SVG polygon paths for Tunisia's 24 governorates (viewBox "0 0 270 408")
// Derived from geographic boundaries using transform x=(lon-7.35)*63, y=(37.7-lat)*54
const GOV_PATHS = [
  { id:'Bizerte',     name:'Bizerte',     label:{x:68, y:30},
    d:'M60,8 L110,8 L118,18 L105,32 L88,38 L72,34 L55,24 Z' },
  { id:'Ariana',     name:'Ariana',      label:{x:128,y:46},
    d:'M118,38 L138,36 L144,46 L138,56 L122,56 L112,48 Z' },
  { id:'Tunis',      name:'Tunis',       label:{x:136,y:62},
    d:'M122,56 L138,56 L148,64 L142,72 L126,70 L118,62 Z' },
  { id:'La Manouba', name:'La Manouba',  label:{x:108,y:56},
    d:'M105,44 L118,38 L112,48 L122,56 L118,62 L102,58 L96,50 Z' },
  { id:'Ben Arous',  name:'Ben Arous',   label:{x:140,y:76},
    d:'M126,70 L142,72 L148,82 L138,88 L122,82 L118,74 Z' },
  { id:'Nabeul',     name:'Nabeul',      label:{x:162,y:72},
    d:'M148,54 L172,54 L178,66 L175,82 L162,92 L148,86 L148,64 Z' },
  { id:'Zaghouan',   name:'Zaghouan',    label:{x:128,y:90},
    d:'M118,74 L138,88 L148,86 L145,102 L128,108 L112,100 L108,86 Z' },
  { id:'Béja',       name:'Béja',        label:{x:70, y:68},
    d:'M40,44 L82,42 L96,50 L102,58 L88,72 L70,78 L44,68 L36,56 Z' },
  { id:'Jendouba',   name:'Jendouba',    label:{x:40, y:86},
    d:'M18,60 L56,56 L70,78 L60,96 L38,100 L16,90 Z' },
  { id:'Kef',        name:'Le Kef',      label:{x:58, y:108},
    d:'M38,100 L60,96 L70,78 L88,72 L92,92 L80,118 L52,120 L34,112 Z' },
  { id:'Siliana',    name:'Siliana',     label:{x:98, y:106},
    d:'M88,72 L108,86 L112,100 L104,118 L80,118 L92,92 Z' },
  { id:'Kairouan',   name:'Kairouan',    label:{x:116,y:136},
    d:'M104,118 L128,108 L145,102 L150,128 L140,150 L118,154 L100,142 Z' },
  { id:'Kasserine',  name:'Kasserine',   label:{x:72, y:148},
    d:'M52,120 L80,118 L104,118 L100,142 L88,160 L64,162 L44,148 L46,130 Z' },
  { id:'Sidi Bouzid',name:'Sidi Bouzid', label:{x:104,y:168},
    d:'M100,142 L118,154 L122,174 L110,190 L86,190 L76,174 L88,160 Z' },
  { id:'Sousse',     name:'Sousse',      label:{x:152,y:128},
    d:'M145,102 L162,92 L175,104 L170,128 L158,140 L150,128 Z' },
  { id:'Monastir',   name:'Monastir',    label:{x:162,y:148},
    d:'M158,140 L175,134 L178,150 L166,158 L152,152 Z' },
  { id:'Mahdia',     name:'Mahdia',      label:{x:162,y:172},
    d:'M152,152 L166,158 L170,172 L160,184 L148,176 L142,162 Z' },
  { id:'Sfax',       name:'Sfax',        label:{x:148,y:200},
    d:'M140,150 L150,128 L170,172 L172,200 L158,216 L138,210 L128,192 Z' },
  { id:'Gafsa',      name:'Gafsa',       label:{x:84, y:204},
    d:'M64,162 L88,160 L86,190 L100,210 L90,228 L62,226 L46,208 L50,186 Z' },
  { id:'Tozeur',     name:'Tozeur',      label:{x:52, y:252},
    d:'M32,224 L62,226 L70,248 L56,268 L30,262 L24,244 Z' },
  { id:'Kébili',     name:'Kébili',      label:{x:100,y:256},
    d:'M62,226 L90,228 L110,240 L108,268 L82,278 L62,262 L70,248 Z' },
  { id:'Gabès',      name:'Gabès',       label:{x:148,y:222},
    d:'M128,192 L138,210 L158,216 L164,234 L150,248 L130,242 L118,224 L110,204 Z' },
  { id:'Médenine',   name:'Médenine',    label:{x:162,y:268},
    d:'M150,248 L164,234 L180,246 L186,270 L172,290 L150,286 L136,270 Z' },
  { id:'Tataouine',  name:'Tataouine',   label:{x:140,y:326},
    d:'M108,268 L136,270 L150,286 L154,320 L140,356 L116,360 L100,330 L96,298 Z' },
];

const TABS = [
  { id:'overview', label:'Overview',   icon:Map          },
  { id:'charts',   label:'Charts',     icon:BarChart2    },
  { id:'agents',   label:'Agents',     icon:Users        },
  { id:'policy',   label:'Policy Lab', icon:FlaskConical },
];

/* ─── Helpers ───────────────────────────────────────────────────────────── */
function fmt(n) {
  if (n == null || isNaN(n)) return '—';
  if (n >= 1_000_000) return `${(n/1_000_000).toFixed(2)}M`;
  if (n >= 1_000)     return `${(n/1_000).toFixed(0)}K`;
  return Number(n).toLocaleString();
}
function priceColor(p) {
  if (!p) return '#374151';
  if (p >= 3500) return '#ef4444';
  if (p >= 2500) return '#f97316';
  if (p >= 1800) return '#f59e0b';
  if (p >= 1200) return '#22c55e';
  return '#3b82f6';
}
function normaliseTs(raw) {
  return (raw?.months||[]).map((m,i) => ({
    label:         `Mo ${m.month??i+1}`,
    price:         Math.round(m.avg_price||0),
    transactions:  m.transactions||0,
    depth:         parseFloat(((m.liquidity_score||0)*100).toFixed(1)),
    affordability: parseFloat((m.affordability_index||0).toFixed(2)),
    growth:        parseFloat(((m.price_growth_rate||0)*100).toFixed(2)),
    bct:           parseFloat(((m.bcb_rate||0.08)*100).toFixed(2)),
    credit:        parseFloat(((m.credit_rate||0.55)*100).toFixed(1)),
  }));
}

/* ─── Sub-components ────────────────────────────────────────────────────── */
function ChartTip({ active, payload, label }) {
  if (!active||!payload?.length) return null;
  return (
    <div className="bg-[#1a2234] border border-white/10 rounded-xl px-3 py-2 text-xs shadow-2xl">
      <p className="text-gray-500 mb-1">{label}</p>
      {payload.map((p,i) => (
        <p key={i} style={{color:p.color}} className="font-bold">
          {p.name}: {typeof p.value==='number' ? p.value.toLocaleString() : p.value}
        </p>
      ))}
    </div>
  );
}

function Slider({ label, hint, min, max, step, value, onChange, display }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-300">{label}
          {hint && <span className="text-gray-600 ml-1.5 text-xs">{hint}</span>}
        </span>
        <span className="text-sm font-bold text-[#FF6B35] tabular-nums w-14 text-right">{display(value)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e=>onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
        style={{accentColor:'#FF6B35', background:`linear-gradient(to right,#FF6B35 ${pct}%,#1f2937 0%)`}} />
    </div>
  );
}

function KpiCard({ label, value, trend }) {
  const Icon = trend==='up' ? ArrowUpRight : trend==='down' ? ArrowDownRight : Minus;
  const tc   = trend==='up' ? 'text-emerald-400' : trend==='down' ? 'text-red-400' : 'text-gray-600';
  return (
    <div className="bg-white/[0.04] border border-white/[0.08] rounded-2xl p-5 flex flex-col gap-1">
      <p className="text-[11px] text-gray-500 uppercase tracking-widest">{label}</p>
      <p className="text-2xl font-black text-white tabular-nums leading-tight">{value}</p>
      {trend && <Icon size={13} className={tc} />}
    </div>
  );
}

function TunisiaMap({ zoneData, hoveredGov, onHover }) {
  return (
    <svg viewBox="0 0 270 408" className="w-full h-full overflow-visible" style={{maxHeight:'420px'}}>
      <rect x="0" y="0" width="270" height="408" rx="8" fill="rgba(255,255,255,0.01)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5"/>
      {GOV_PATHS.map(gov => {
        const price = zoneData?.[gov.id]?.avg_price_m2 || zoneData?.[gov.name]?.avg_price_m2;
        const fill  = priceColor(price);
        const isHov = hoveredGov?.id===gov.id;
        return (
          <g key={gov.id} onMouseEnter={()=>onHover({...gov,price})} onMouseLeave={()=>onHover(null)} style={{cursor:'pointer'}}>
            <path d={gov.d} fill={fill} fillOpacity={isHov?1:0.75}
              stroke={isHov?'#ffffff':'rgba(0,0,0,0.4)'} strokeWidth={isHov?1.5:0.6}
              style={{transition:'fill-opacity .15s ease, stroke .15s ease'}}/>
            <text x={gov.label.x} y={gov.label.y} fontSize={isHov?'8':'6.5'} fill={isHov?'#fff':'rgba(255,255,255,0.6)'}
              textAnchor="middle" dominantBaseline="middle" style={{pointerEvents:'none',fontWeight:isHov?'700':'400'}}>
              {gov.name}
            </text>
          </g>
        );
      })}
      {/* Legend */}
      {[['<1.2K','#3b82f6',16],['1.8K','#22c55e',70],['2.5K','#f59e0b',124],['3.5K+','#ef4444',178]].map(([lbl,c,x])=>(
        <g key={lbl} transform={`translate(${x},396)`}>
          <rect x="0" y="-5" width="10" height="10" rx="2" fill={c} fillOpacity={0.85}/>
          <text x="13" y="1" fontSize="8" fill="#6b7280">{lbl}</text>
        </g>
      ))}
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
export default function SimulatePage() {

  const [scenario,   setScenario]    = useState('baseline');
  const [scale,      setScale]       = useState('medium');
  const [months,     setMonths]      = useState(12);
  const [bctRate,    setBctRate]     = useState(8);
  const [maxLtv,     setMaxLtv]      = useState(80);
  const [diaspora,   setDiaspora]    = useState(15);
  const [tourism,    setTourism]     = useState(1.0);
  const [supplyShock,setSupplyShock] = useState(0);

  const [phase,    setPhase]    = useState('idle');
  const [runId,    setRunId]    = useState(null);
  const [progress, setProgress] = useState(0);
  const [liveKpis, setLiveKpis] = useState(null);
  const [errMsg,   setErrMsg]   = useState('');

  const [activeTab,  setActiveTab]  = useState('overview');
  const [tsData,     setTsData]     = useState([]);
  const [metrics,    setMetrics]    = useState(null);
  const [agentData,  setAgentData]  = useState([]);
  const [zoneMap,    setZoneMap]    = useState({});
  const [hoveredGov, setHoveredGov] = useState(null);
  const [feed,       setFeed]       = useState([]);

  const [runs,        setRuns]        = useState([]);
  const [histOpen,    setHistOpen]    = useState(false);
  const [histLoading, setHistLoading] = useState(false);

  const [compareA,      setCompareA]      = useState('');
  const [compareB,      setCompareB]      = useState('');
  const [compareResult, setCompareResult] = useState(null);

  const pollRef = useRef(null);

  const loadRuns = useCallback(async () => {
    setHistLoading(true);
    try { const r = await simListRuns(); setRuns(r.data?.runs||[]); } catch{}
    setHistLoading(false);
  }, []);

  useEffect(() => { loadRuns(); }, [loadRuns]);

  const buildOverrides = useCallback(() => ({
    bct_rate:             bctRate/100,
    credit_approval_rate: (maxLtv-20)/80,
    investor_multiplier:  1.0+diaspora/100,
    developer_activity:   1.0+supplyShock/100,
    demand_multiplier:    tourism,
  }), [bctRate,maxLtv,diaspora,supplyShock,tourism]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current=null; }
  }, []);

  const addEvent = useCallback((msg, type='info') => {
    setFeed(prev => [{msg,type,id:Date.now()+Math.random()},...prev].slice(0,60));
  }, []);

  const fetchResults = useCallback(async (id) => {
    const [tsRes,metRes,agRes,zoneRes] = await Promise.all([
      simGetTimeseries(id), simGetMetrics(id), simGetAgents(id),
      simGetZones(id).catch(()=>null),
    ]);
    setTsData(normaliseTs(tsRes.data));
    setMetrics(metRes.data?.metrics||metRes.data);
    setAgentData(agRes.data?.agents||[]);
    if (zoneRes?.data?.zones) {
      const zm={};
      zoneRes.data.zones.forEach(z=>{ zm[z.governorate]={avg_price_m2:z.avg_price_m2}; });
      setZoneMap(zm);
    }
  }, []);

  const startPolling = useCallback((id) => {
    stopPolling();
    let lastMonth=0;
    pollRef.current = setInterval(async () => {
      try {
        const det = await simGetRunDetail(id);
        const run = det.data?.run||det.data;
        setProgress(Math.round(run.progress_pct??0));
        const cur=run.current_month;
        const lm=run.latest_metrics||{};
        setLiveKpis({month:cur,transactions:run.total_transactions,avgPrice:lm.avg_price||run.avg_transaction_price,growth:lm.price_growth!=null?lm.price_growth*100:null,bct:lm.interest_rate!=null?lm.interest_rate*100:null});
        if (cur!==lastMonth) {
          lastMonth=cur;
          const n=run.total_transactions||0;
          const g=lm.price_growth!=null?(lm.price_growth*100).toFixed(2):null;
          if (n>0)     addEvent(`Month ${cur} — ${n} total transactions`,'success');
          if (g!=null) addEvent(`Month ${cur} — price ${g>=0?'▲':'▼'} ${Math.abs(g)}%`, g>=0?'up':'down');
        }
        if (run.status==='complete'||run.status==='error') {
          stopPolling();
          if (run.status==='complete') {
            setPhase('done'); addEvent('Simulation complete','success');
            await fetchResults(id); loadRuns();
          } else {
            setPhase('error'); setErrMsg(run.error_message||'Simulation failed.'); addEvent('Error','error');
          }
        }
      } catch {}
    }, 2000);
  }, [stopPolling,addEvent,fetchResults,loadRuns]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const handleRun = async () => {
    setPhase('running'); setProgress(0); setLiveKpis(null); setErrMsg('');
    setTsData([]); setMetrics(null); setAgentData([]); setZoneMap({}); setFeed([]);
    setActiveTab('overview');
    const sc = SCENARIOS_MAP[scenario];
    addEvent(`Starting — ${sc?.label} · ${scale} · ${months} months`,'info');
    try {
      const res = await simStart({scenario_name:scenario,num_months:months,agent_scale:scale,policy_overrides:buildOverrides()});
      const id  = res.data?.run_id;
      setRunId(id); startPolling(id); loadRuns();
    } catch (e) {
      setPhase('error'); setErrMsg(e?.response?.data?.error||'Failed to start.');
    }
  };

  const loadPastRun = async (run) => {
    if (run.status!=='complete') return;
    setPhase('done'); setRunId(run.run_id); setScenario(run.scenario_name);
    setScale(run.agent_scale); setMonths(run.num_months); setFeed([]); setActiveTab('overview');
    try { await fetchResults(run.run_id); } catch {}
  };

  const deleteRun = async (e,id) => {
    e.stopPropagation();
    try { await simDeleteRun(id); } catch {}
    if (id===runId) { setPhase('idle'); setRunId(null); }
    loadRuns();
  };

  const handleCompare = async () => {
    if (!compareA||!compareB) return;
    try { const r=await simCompare(compareA,compareB); setCompareResult(r.data); } catch {}
  };

  const sc         = SCENARIOS_MAP[scenario]||SCENARIOS[0];
  const ScenIcon   = sc.icon;
  const scaleObj   = SCALES.find(s=>s.id===scale)||SCALES[1];
  const lastTs     = tsData[tsData.length-1]||{};
  const firstTs    = tsData[0]||{};
  const priceChg   = firstTs.price&&lastTs.price ? (((lastTs.price-firstTs.price)/firstTs.price)*100).toFixed(1) : null;
  const isRunning  = phase==='running';
  const isDone     = phase==='done';
  const hasResults = isDone||(isRunning&&tsData.length>0);

  /* ─── render ─────────────────────────────────────────────────────────── */
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] pt-24 pb-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between mb-10">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-[#FF6B35]/10 border border-[#FF6B35]/20 flex items-center justify-center">
              <Cpu size={20} className="text-[#FF6B35]" />
            </div>
            <div>
              <h1 className="text-3xl font-black text-white">Market Simulation Engine</h1>
              <p className="text-gray-500 text-sm mt-0.5">Agent-based model of the Tunisian real-estate market · Mesa ABM</p>
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            {isRunning && (
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold">
                <Loader2 size={11} className="animate-spin" /> Running
              </span>
            )}
            {isDone && (
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
                <CheckCircle2 size={11} /> Complete
              </span>
            )}
          </div>
        </div>

        {/* ── Error ──────────────────────────────────────────────────────── */}
        {phase==='error' && (
          <div className="mb-6 flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
            <AlertTriangle size={15} className="text-red-400 flex-shrink-0"/>
            <span className="text-sm text-red-300 flex-1">{errMsg}</span>
            <button onClick={()=>setPhase('idle')} className="text-xs text-gray-500 hover:text-gray-300 underline">Dismiss</button>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            CONFIG SECTION
        ════════════════════════════════════════════════════════════════ */}
        <div className="space-y-3 mb-5">

          {/* ── 1. Scenarios ───────────────────────────────────────────────── */}
          <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-5">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-1 h-4 rounded-full bg-[#FF6B35]" />
              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Scenario</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {SCENARIOS.map(s => {
                const Icon   = s.icon;
                const active = scenario === s.id;
                return (
                  <button key={s.id} onClick={() => setScenario(s.id)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-all ${
                      active ? 'border' : 'border-white/[0.05] bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/[0.08]'
                    }`}
                    style={active ? {background:`${s.color}12`, borderColor:`${s.color}40`} : {}}>
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{background:`${s.color}18`}}>
                      <Icon size={14} style={{color: s.color}} />
                    </div>
                    <span className={`text-sm font-semibold flex-1 min-w-0 truncate ${active ? 'text-white' : 'text-gray-400'}`}>
                      {s.label}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-md font-semibold flex-shrink-0"
                      style={{background:`${s.color}18`, color:s.color}}>
                      {s.badge}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── 2. Scale · Duration · Agent Registry ───────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">

            {/* Scale */}
            <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-5">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-1 h-4 rounded-full bg-[#FF6B35]" />
                <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Agent Scale</span>
              </div>
              <div className="space-y-2">
                {SCALES.map(s => (
                  <button key={s.id} onClick={() => setScale(s.id)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border transition-all ${
                      scale === s.id
                        ? 'bg-[#FF6B35]/8 border-[#FF6B35]/30'
                        : 'border-white/[0.05] hover:bg-white/[0.03] hover:border-white/[0.1]'
                    }`}>
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 transition-colors ${scale===s.id ? 'bg-[#FF6B35]' : 'bg-gray-700'}`} />
                    <span className={`text-sm font-semibold flex-1 text-left ${scale===s.id ? 'text-white' : 'text-gray-500'}`}>
                      {s.label}
                    </span>
                    <span className="text-[11px] text-gray-600">{s.sub}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Duration */}
            <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-5">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-1 h-4 rounded-full bg-[#FF6B35]" />
                <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Duration</span>
              </div>
              <div className="grid grid-cols-5 gap-2">
                {[6, 12, 24, 36, 60].map(mo => (
                  <button key={mo} onClick={() => setMonths(mo)}
                    className={`py-3.5 rounded-xl border text-center transition-all ${
                      months === mo
                        ? 'bg-[#FF6B35]/8 border-[#FF6B35]/30 text-[#FF6B35]'
                        : 'border-white/[0.05] text-gray-500 hover:border-white/[0.1] hover:text-gray-300'
                    }`}>
                    <p className="text-sm font-bold">{mo}</p>
                    <p className="text-[9px] opacity-60 mt-0.5">mo</p>
                  </button>
                ))}
              </div>
              <div className="mt-4 px-1">
                <p className="text-xs text-gray-600">
                  Selected: <span className="text-white font-semibold">{months} months</span>
                  <span className="text-gray-700 ml-1.5">
                    ({months <= 12 ? 'short-term' : months <= 24 ? 'medium-term' : 'long-term'})
                  </span>
                </p>
              </div>
            </div>

            {/* Agent Registry */}
            <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-5">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-1 h-4 rounded-full bg-[#FF6B35]" />
                <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Agent Registry</span>
              </div>
              <div className="space-y-2.5">
                {Object.entries(AGENT_COLORS).map(([type, color]) => {
                  const count = scaleObj.agents[type] ?? '—';
                  return (
                    <div key={type} className="flex items-center justify-between py-1 border-b border-white/[0.04] last:border-0">
                      <div className="flex items-center gap-2.5">
                        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{background: color}} />
                        <span className="text-sm text-gray-400 capitalize">{type}</span>
                      </div>
                      <span className="text-sm font-bold tabular-nums font-mono" style={{color}}>{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* ── 3. Policy Overrides ─────────────────────────────────────────── */}
          <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-5">
            <div className="flex items-center gap-2.5 mb-5">
              <div className="w-1 h-4 rounded-full bg-[#FF6B35]" />
              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Policy Overrides</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-x-8 gap-y-6">
              <Slider label="BCT Rate"      hint="Central bank"  min={3}   max={18}  step={0.5} value={bctRate}     onChange={setBctRate}     display={v => `${v}%`} />
              <Slider label="Max LTV"       hint="Loan-to-value" min={50}  max={90}  step={5}   value={maxLtv}      onChange={setMaxLtv}      display={v => `${v}%`} />
              <Slider label="Diaspora"      hint="Buyer demand"  min={0}   max={30}  step={1}   value={diaspora}    onChange={setDiaspora}    display={v => `+${v}%`} />
              <Slider label="Tourism Index" hint="Multiplier"    min={0.3} max={2.5} step={0.1} value={tourism}     onChange={setTourism}     display={v => `${v}×`} />
              <Slider label="Supply Shock"  hint="New builds"    min={-30} max={30}  step={5}   value={supplyShock} onChange={setSupplyShock} display={v => `${v > 0 ? '+' : ''}${v}%`} />
            </div>
          </div>

          {/* ── 4. Run button ───────────────────────────────────────────────── */}
          <div className="flex items-center gap-3">
            {!isRunning ? (
              <button onClick={handleRun}
                className="flex items-center gap-2.5 px-8 py-3.5 rounded-xl bg-[#FF6B35] hover:bg-[#e85d2a] text-white font-black text-sm transition-all active:scale-[0.98] shadow-lg shadow-[#FF6B35]/20">
                <Play size={14} /> Run Simulation
              </button>
            ) : (
              <button onClick={() => { stopPolling(); setPhase('idle'); }}
                className="flex items-center gap-2.5 px-8 py-3.5 rounded-xl bg-red-500/10 border border-red-500/20 hover:bg-red-500/15 text-red-400 font-bold text-sm transition-all">
                <Square size={14} /> Stop
              </button>
            )}
            {phase !== 'idle' && (
              <button onClick={() => { stopPolling(); setPhase('idle'); setRunId(null); setTsData([]); setMetrics(null); setAgentData([]); setFeed([]); }}
                className="flex items-center gap-2 px-5 py-3.5 rounded-xl border border-white/[0.07] text-gray-500 hover:text-gray-300 hover:border-white/10 text-sm font-medium transition-all">
                <RotateCcw size={12} /> New
              </button>
            )}
            {(isRunning || isDone) && (
              <div className="flex items-center gap-2 ml-1 px-4 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <ScenIcon size={12} style={{color: sc.color}} />
                <span className="text-sm text-gray-400 font-medium">{sc.label}</span>
                <span className="text-gray-700 mx-1">·</span>
                <span className="text-sm text-gray-500">{scaleObj.label}</span>
                <span className="text-gray-700 mx-1">·</span>
                <span className="text-sm text-gray-500">{months}mo</span>
              </div>
            )}
          </div>
        </div>

        {/* ══════════════════════════════════════════════════════════════════
            RESULTS SECTION
        ════════════════════════════════════════════════════════════════ */}

        {/* Running: progress */}
        {isRunning && (
          <div className="bg-white/[0.03] border border-white/[0.08] rounded-3xl p-7 mb-5">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <Loader2 size={14} className="text-amber-400 animate-spin"/>
                <span className="text-sm font-semibold text-white">Simulation running…</span>
              </div>
              <span className="text-3xl font-black text-[#FF6B35] tabular-nums">{progress}%</span>
            </div>
            <div className="h-2.5 bg-white/[0.06] rounded-full overflow-hidden mb-6">
              <div className="h-full bg-gradient-to-r from-[#FF6B35] to-[#f97316] rounded-full transition-all duration-500"
                style={{width:`${progress}%`}}/>
            </div>
            {liveKpis && (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {[
                  {label:'Month',        value:`${liveKpis.month??0} / ${months}`},
                  {label:'Transactions', value:fmt(liveKpis.transactions)},
                  {label:'Avg Price',    value:liveKpis.avgPrice?`${fmt(liveKpis.avgPrice)} TND`:'—'},
                  {label:'BCT Rate',     value:liveKpis.bct!=null?`${liveKpis.bct.toFixed(1)}%`:'—'},
                  {label:'Price Δ',      value:liveKpis.growth!=null?`${liveKpis.growth>=0?'+':''}${liveKpis.growth.toFixed(2)}%`:'—'},
                ].map(k=>(
                  <div key={k.label} className="bg-white/[0.03] rounded-2xl px-4 py-3 text-center">
                    <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-1">{k.label}</p>
                    <p className="text-base font-black text-white tabular-nums">{k.value}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Idle placeholder */}
        {phase==='idle' && (
          <div className="border border-dashed border-white/[0.08] rounded-3xl p-14 flex flex-col items-center justify-center gap-4 text-center">
            <div className="w-16 h-16 rounded-3xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center">
              <ScenIcon size={24} style={{color:sc.color}}/>
            </div>
            <div>
              <p className="text-lg font-bold text-white">{sc.label}</p>
              <p className="text-gray-600 text-sm mt-1 max-w-sm">
                Configure your parameters above and press <span className="text-[#FF6B35] font-semibold">Run Simulation</span> to begin.
              </p>
            </div>
          </div>
        )}

        {/* Results */}
        {hasResults && (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
              <KpiCard label="Total Transactions" value={fmt(metrics?.total_transactions??liveKpis?.transactions)}/>
              <KpiCard label="Final Avg Price"    value={lastTs.price?`${fmt(lastTs.price)} TND`:'—'}/>
              <KpiCard label="Price Change"
                value={priceChg!=null?`${priceChg>0?'+':''}${priceChg}%`:'—'}
                trend={priceChg>0?'up':priceChg<0?'down':'neutral'}/>
              <KpiCard label="Affordability Ratio" value={lastTs.affordability?`${lastTs.affordability}×`:'—'}/>
            </div>

            {/* Tabbed results */}
            <div className="bg-white/[0.02] border border-white/[0.08] rounded-3xl overflow-hidden mb-5">
              {/* Tab bar */}
              <div className="flex border-b border-white/[0.06] bg-white/[0.01]">
                {TABS.map(tab=>{
                  const Icon=tab.icon;
                  const active=activeTab===tab.id;
                  return (
                    <button key={tab.id} onClick={()=>setActiveTab(tab.id)}
                      className={`flex items-center gap-2.5 px-6 py-4 text-xs font-semibold whitespace-nowrap border-b-2 transition-all ${
                        active ? 'text-white border-[#FF6B35]' : 'text-gray-600 border-transparent hover:text-gray-400'
                      }`}>
                      <Icon size={13}/>{tab.label}
                    </button>
                  );
                })}
              </div>

              <div className="p-6">

                {/* ── Overview ── */}
                {activeTab==='overview' && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
                      {/* Price chart */}
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-widest mb-4">Average Property Price (TND)</p>
                        {tsData.length>0 ? (
                          <ResponsiveContainer width="100%" height={260}>
                            <AreaChart data={tsData} margin={{top:4,right:4,bottom:0,left:-10}}>
                              <defs>
                                <linearGradient id="pg" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%"  stopColor="#FF6B35" stopOpacity={0.22}/>
                                  <stop offset="95%" stopColor="#FF6B35" stopOpacity={0}/>
                                </linearGradient>
                              </defs>
                              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)"/>
                              <XAxis dataKey="label" tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false} interval="preserveStartEnd"/>
                              <YAxis tickFormatter={v=>`${Math.round(v/1000)}k`} tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false}/>
                              <Tooltip content={<ChartTip/>}/>
                              <Area type="monotone" dataKey="price" name="Price (TND)" stroke="#FF6B35" strokeWidth={2} fill="url(#pg)" dot={false}/>
                            </AreaChart>
                          </ResponsiveContainer>
                        ) : (
                          <div className="h-64 flex items-center justify-center text-gray-700 text-sm">
                            Data appears as the simulation runs…
                          </div>
                        )}
                      </div>

                      {/* Tunisia map */}
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-widest mb-4">Price Map — TND/m²</p>
                        <div className="h-64">
                          <TunisiaMap zoneData={zoneMap} hoveredGov={hoveredGov} onHover={setHoveredGov}/>
                        </div>
                        <div className="mt-3 h-8">
                          {hoveredGov ? (
                            <div className="flex items-center justify-between px-3 py-1.5 bg-white/[0.04] rounded-xl">
                              <span className="text-xs font-semibold text-white">{hoveredGov.name}</span>
                              <span className="text-xs font-mono text-[#FF6B35]">
                                {hoveredGov.price?`${hoveredGov.price.toLocaleString()} TND/m²`:'No data'}
                              </span>
                            </div>
                          ) : (
                            <p className="text-xs text-gray-700 px-1">Hover a governorate to inspect price</p>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Transactions overview chart */}
                    {tsData.length>0 && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-widest mb-4">Monthly Transactions</p>
                        <ResponsiveContainer width="100%" height={160}>
                          <BarChart data={tsData} margin={{top:4,right:4,bottom:0,left:-10}}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)"/>
                            <XAxis dataKey="label" tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false} interval="preserveStartEnd"/>
                            <YAxis tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false}/>
                            <Tooltip content={<ChartTip/>}/>
                            <Bar dataKey="transactions" name="Transactions" fill="#FF6B35" radius={[3,3,0,0]}/>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                )}

                {/* ── Charts ── */}
                {activeTab==='charts' && (
                  tsData.length>0 ? (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {/* Affordability */}
                      <div>
                        <p className="text-sm font-semibold text-white mb-1">Housing Affordability</p>
                        <p className="text-xs text-gray-600 mb-4">Price ÷ annual income ratio</p>
                        <ResponsiveContainer width="100%" height={180}>
                          <AreaChart data={tsData} margin={{top:4,right:4,bottom:0,left:-10}}>
                            <defs>
                              <linearGradient id="afg" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%"  stopColor="#8b5cf6" stopOpacity={0.22}/>
                                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)"/>
                            <XAxis dataKey="label" tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false} interval="preserveStartEnd"/>
                            <YAxis tickFormatter={v=>`${v}×`} tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false}/>
                            <Tooltip content={<ChartTip/>}/>
                            <Area type="monotone" dataKey="affordability" name="Ratio" stroke="#8b5cf6" strokeWidth={2} fill="url(#afg)" dot={false}/>
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Market depth */}
                      <div>
                        <p className="text-sm font-semibold text-white mb-1">Market Depth & Price Growth</p>
                        <p className="text-xs text-gray-600 mb-4">Liquidity vs monthly price change %</p>
                        <ResponsiveContainer width="100%" height={180}>
                          <LineChart data={tsData} margin={{top:4,right:4,bottom:0,left:-10}}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)"/>
                            <XAxis dataKey="label" tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false} interval="preserveStartEnd"/>
                            <YAxis tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false}/>
                            <Tooltip content={<ChartTip/>}/>
                            <Legend iconType="circle" iconSize={7} wrapperStyle={{fontSize:10,color:'#6b7280'}}/>
                            <Line type="monotone" dataKey="depth"  name="Market Depth %" stroke="#3b82f6" strokeWidth={2} dot={false}/>
                            <Line type="monotone" dataKey="growth" name="Price Δ %"       stroke="#22c55e" strokeWidth={1.5} dot={false} strokeDasharray="4 2"/>
                          </LineChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Monetary */}
                      <div>
                        <p className="text-sm font-semibold text-white mb-1">Monetary Conditions</p>
                        <p className="text-xs text-gray-600 mb-4">BCT rate vs credit approval rate</p>
                        <ResponsiveContainer width="100%" height={180}>
                          <LineChart data={tsData} margin={{top:4,right:4,bottom:0,left:-10}}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)"/>
                            <XAxis dataKey="label" tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false} interval="preserveStartEnd"/>
                            <YAxis tickFormatter={v=>`${v}%`} tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false}/>
                            <Tooltip content={<ChartTip/>}/>
                            <Legend iconType="circle" iconSize={7} wrapperStyle={{fontSize:10,color:'#6b7280'}}/>
                            <Line type="monotone" dataKey="bct"    name="BCT Rate %"   stroke="#f59e0b" strokeWidth={2} dot={false}/>
                            <Line type="monotone" dataKey="credit" name="Credit Rate %" stroke="#22c55e" strokeWidth={2} dot={false} strokeDasharray="4 2"/>
                          </LineChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Transactions bar */}
                      <div>
                        <p className="text-sm font-semibold text-white mb-1">Monthly Transactions</p>
                        <p className="text-xs text-gray-600 mb-4">Deal volume per simulation month</p>
                        <ResponsiveContainer width="100%" height={180}>
                          <BarChart data={tsData} margin={{top:4,right:4,bottom:0,left:-10}}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)"/>
                            <XAxis dataKey="label" tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false} interval="preserveStartEnd"/>
                            <YAxis tick={{fill:'#4b5563',fontSize:9}} axisLine={false} tickLine={false}/>
                            <Tooltip content={<ChartTip/>}/>
                            <Bar dataKey="transactions" name="Transactions" fill="#FF6B35" radius={[3,3,0,0]}/>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  ) : (
                    <div className="py-16 text-center text-gray-600">Run a simulation to see charts.</div>
                  )
                )}

                {/* ── Agents ── */}
                {activeTab==='agents' && (
                  agentData.length>0 ? (
                    <div className="space-y-6">
                      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
                        {agentData.map(ag=>(
                          <div key={ag.agent_type}
                            className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 text-center">
                            <div className="w-2.5 h-2.5 rounded-full mx-auto mb-2" style={{background:AGENT_COLORS[ag.agent_type]}}/>
                            <p className="text-[11px] text-gray-500 capitalize mb-1">{ag.agent_type}</p>
                            <p className="text-2xl font-black" style={{color:AGENT_COLORS[ag.agent_type]}}>{ag.count}</p>
                            <p className="text-[10px] text-gray-600 mt-1">{ag.success_rate}% success</p>
                          </div>
                        ))}
                      </div>

                      <div className="rounded-2xl border border-white/[0.07] overflow-hidden">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-white/[0.07] bg-white/[0.02]">
                              {['Agent Type','Count','Total Actions','Success Rate','Avg Utility'].map(h=>(
                                <th key={h} className={`py-3 px-5 text-[10px] text-gray-600 uppercase tracking-wider font-semibold ${h==='Agent Type'?'text-left':'text-right'}`}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/[0.04]">
                            {agentData.map((ag,i)=>(
                              <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                                <td className="py-3.5 px-5">
                                  <div className="flex items-center gap-3">
                                    <div className="w-2.5 h-2.5 rounded-full" style={{background:AGENT_COLORS[ag.agent_type]}}/>
                                    <span className="text-gray-300 capitalize font-semibold">{ag.agent_type}</span>
                                  </div>
                                </td>
                                <td className="py-3.5 px-5 text-right text-gray-500 font-mono text-xs">{ag.count}</td>
                                <td className="py-3.5 px-5 text-right text-gray-500 font-mono text-xs">{ag.total_actions?.toLocaleString()}</td>
                                <td className="py-3.5 px-5 text-right font-mono text-xs font-bold text-[#FF6B35]">{ag.success_rate}%</td>
                                <td className="py-3.5 px-5 text-right text-gray-500 font-mono text-xs">
                                  {ag.avg_utility!=null?(ag.avg_utility>=0?'+':'')+ag.avg_utility.toFixed(0):'—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <div className="py-16 text-center text-gray-600">Complete a simulation to see agent outcomes.</div>
                  )
                )}

                {/* ── Policy Lab ── */}
                {activeTab==='policy' && (
                  <div className="space-y-6">
                    <p className="text-sm text-gray-500">
                      Compare two completed simulations side-by-side to evaluate the effect of different policy configurations on market outcomes.
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {['Run A','Run B'].map((label,idx)=>(
                        <div key={label}>
                          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2 font-semibold">{label}</p>
                          <select value={idx===0?compareA:compareB}
                            onChange={e=>idx===0?setCompareA(e.target.value):setCompareB(e.target.value)}
                            className="w-full bg-white/[0.04] border border-white/[0.1] rounded-xl px-4 py-3 text-sm text-gray-300 focus:outline-none focus:border-[#FF6B35]/40 transition-colors">
                            <option value="">Select run…</option>
                            {runs.filter(r=>r.status==='complete').map(r=>(
                              <option key={r.run_id} value={r.run_id}>
                                {SCENARIOS_MAP[r.scenario_name]?.label||r.scenario_name} · {r.agent_scale} · {r.num_months}mo
                              </option>
                            ))}
                          </select>
                        </div>
                      ))}
                    </div>
                    <button onClick={handleCompare} disabled={!compareA||!compareB}
                      className={`px-6 py-3 rounded-xl text-sm font-bold transition-all ${
                        compareA&&compareB ? 'bg-[#FF6B35] text-white hover:bg-[#e85d2a] shadow-lg shadow-[#FF6B35]/20' : 'bg-white/[0.04] text-gray-600 cursor-not-allowed'
                      }`}>
                      Compare Runs
                    </button>

                    {compareResult && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {[compareResult.run_a,compareResult.run_b].map((run,idx)=>{
                          if (!run) return null;
                          const s=run.summary||{};
                          const pct=s.price_change_pct;
                          const sm=SCENARIOS_MAP[run.scenario_name]||{};
                          return (
                            <div key={idx} className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-5">
                              <div className="flex items-center gap-2.5 mb-5">
                                <div className="w-2.5 h-2.5 rounded-full" style={{background:sm.color||'#FF6B35'}}/>
                                <span className="font-bold text-white">{sm.label||run.scenario_name}</span>
                                <span className="text-xs text-gray-600 ml-auto">{run.agent_scale} · {run.num_months}mo</span>
                              </div>
                              {[
                                {label:'Price Change',   value:`${pct>=0?'+':''}${pct}%`, color:pct>=0?'#22c55e':'#ef4444'},
                                {label:'Initial Price',  value:`${fmt(s.initial_avg_price)} TND`},
                                {label:'Final Price',    value:`${fmt(s.final_avg_price)} TND`},
                                {label:'Transactions',   value:fmt(run.total_transactions)},
                                {label:'Affordability',  value:`${s.avg_affordability}×`},
                                {label:'Liquidity',      value:`${(s.avg_liquidity*100).toFixed(1)}%`},
                              ].map(row=>(
                                <div key={row.label} className="flex justify-between items-center py-2.5 border-b border-white/[0.05]">
                                  <span className="text-xs text-gray-600">{row.label}</span>
                                  <span className="text-xs font-bold font-mono" style={{color:row.color||'#d1d5db'}}>{row.value}</span>
                                </div>
                              ))}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Feed + summary row */}
            <div className="grid grid-cols-1 md:grid-cols-[1fr_260px] gap-4 mb-5">
              <div className="bg-white/[0.02] border border-white/[0.07] rounded-3xl overflow-hidden">
                <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-white/[0.06]">
                  <Activity size={12} className="text-[#FF6B35]"/>
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Live Feed</span>
                  {isRunning && <span className="ml-auto w-2 h-2 rounded-full bg-emerald-400 animate-pulse"/>}
                </div>
                <div className="h-44 overflow-y-auto p-4 space-y-1 sim-scroll">
                  {feed.length===0 && <p className="text-xs text-gray-700 text-center mt-5">Events will appear here…</p>}
                  {feed.map(ev=>(
                    <p key={ev.id} className={`text-[11px] font-mono leading-5 ${
                      ev.type==='success'?'text-emerald-500':ev.type==='up'?'text-[#FF6B35]':ev.type==='down'?'text-red-400':ev.type==='error'?'text-red-400':'text-gray-600'
                    }`}>{ev.msg}</p>
                  ))}
                </div>
              </div>

              {isDone && metrics && (
                <div className="bg-white/[0.02] border border-white/[0.07] rounded-3xl p-5">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">Final Summary</p>
                  {[
                    {label:'Transactions',   value:fmt(metrics.total_transactions), color:'text-[#FF6B35]'},
                    {label:'Price Δ',        value:`${metrics.price_change_pct>=0?'+':''}${metrics.price_change_pct}%`, color:metrics.price_change_pct>=0?'text-emerald-400':'text-red-400'},
                    {label:'Peak Txns/Mo',   value:metrics.peak_monthly_transactions, color:'text-white'},
                    {label:'Avg Affordability', value:`${metrics.avg_affordability}×`, color:'text-white'},
                    {label:'Avg Liquidity',  value:`${(metrics.avg_liquidity*100).toFixed(1)}%`, color:'text-white'},
                  ].map(row=>(
                    <div key={row.label} className="flex justify-between items-center py-2.5 border-b border-white/[0.05]">
                      <span className="text-xs text-gray-600">{row.label}</span>
                      <span className={`text-xs font-bold font-mono ${row.color}`}>{row.value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {/* ── Run history ──────────────────────────────────────────────────── */}
        <div className="bg-white/[0.02] border border-white/[0.07] rounded-3xl overflow-hidden">
          <button onClick={()=>setHistOpen(v=>!v)}
            className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/[0.02] transition-colors">
            <div className="flex items-center gap-3">
              <Clock size={14} className="text-gray-600"/>
              <span className="text-sm font-semibold text-gray-300">Run History</span>
              {runs.length>0 && (
                <span className="px-2 py-0.5 rounded-full bg-white/[0.06] text-[10px] text-gray-500">{runs.length}</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={e=>{e.stopPropagation();loadRuns();}} className="p-1 text-gray-600 hover:text-gray-400 transition-colors">
                <RefreshCw size={11} className={histLoading?'animate-spin':''}/>
              </button>
              {histOpen ? <ChevronUp size={13} className="text-gray-600"/> : <ChevronDown size={13} className="text-gray-600"/>}
            </div>
          </button>

          {histOpen && (
            <div className="border-t border-white/[0.06]">
              {runs.length===0 ? (
                <p className="px-6 py-8 text-sm text-gray-600 text-center">No simulations yet.</p>
              ) : (
                <div className="divide-y divide-white/[0.04]">
                  {runs.map(r=>{
                    const sm = SCENARIOS_MAP[r.scenario_name]||{};
                    const statusColor = r.status==='complete'?'#22c55e':r.status==='running'?'#f59e0b':r.status==='error'?'#ef4444':'#4b5563';
                    const statusLabel = {complete:'Done',running:'Running',error:'Error',pending:'Queued'}[r.status]||r.status;
                    return (
                      <div key={r.run_id} onClick={()=>loadPastRun(r)}
                        className={`flex items-center gap-4 px-6 py-4 transition-all ${
                          r.status==='complete'?'cursor-pointer hover:bg-white/[0.03]':'cursor-default opacity-50'
                        } ${r.run_id===runId?'bg-white/[0.03]':''}`}>
                        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{background:statusColor}}/>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-gray-300 font-semibold truncate">{sm.label||r.scenario_name}</p>
                          <p className="text-xs text-gray-600">{r.agent_scale} · {r.num_months}mo{r.total_transactions?` · ${fmt(r.total_transactions)} deals`:''}</p>
                        </div>
                        <span className="text-[10px] font-semibold px-2.5 py-1 rounded-lg flex-shrink-0"
                          style={{background:statusColor+'15',color:statusColor}}>
                          {statusLabel}
                        </span>
                        <button onClick={e=>deleteRun(e,r.run_id)} className="text-gray-700 hover:text-red-400 transition-colors p-1 flex-shrink-0">
                          <Trash2 size={12}/>
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

      </div>

      <style>{`
        .sim-scroll::-webkit-scrollbar { width:3px; }
        .sim-scroll::-webkit-scrollbar-track { background:transparent; }
        .sim-scroll::-webkit-scrollbar-thumb { background:#374151; border-radius:2px; }
      `}</style>
    </div>
  );
}
