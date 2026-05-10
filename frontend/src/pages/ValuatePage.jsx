/**
 * ValuatePage — AI Property Valuator
 * Integrates: heuristic pricing, SHAP attribution, NLP sentiment,
 * vision quality scoring, comparable listings, 5-signal confidence.
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles, Home, MapPin, TrendingUp, CheckCircle2, AlertCircle,
  BarChart2, FileText, Eye, Info, X, Loader2, Brain, ArrowRight,
  Building2, Layers, Activity, Image as ImageIcon, ChevronDown,
  AlertTriangle, Download, Zap,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList,
} from 'recharts';
import FeatureGate from '../components/access/FeatureGate';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';

// ─────────────────────────────────────────────────────────────────────────────
// Static fallback locations (exact names from DB)
// ─────────────────────────────────────────────────────────────────────────────
const STATIC_REGIONS = [
  { id: 1,  governorate: 'Ariana' },
  { id: 2,  governorate: 'Béja' },
  { id: 3,  governorate: 'Ben Arous' },
  { id: 4,  governorate: 'Bizerte' },
  { id: 5,  governorate: 'Gabès' },
  { id: 6,  governorate: 'Gafsa' },
  { id: 7,  governorate: 'Jendouba' },
  { id: 8,  governorate: 'Kairouan' },
  { id: 9,  governorate: 'Kasserine' },
  { id: 10, governorate: 'Kébili' },
  { id: 11, governorate: 'Le Kef' },
  { id: 12, governorate: 'Mahdia' },
  { id: 13, governorate: 'La Manouba' },
  { id: 14, governorate: 'Médenine' },
  { id: 15, governorate: 'Monastir' },
  { id: 16, governorate: 'Nabeul' },
  { id: 17, governorate: 'Sfax' },
  { id: 18, governorate: 'Sidi Bouzid' },
  { id: 19, governorate: 'Siliana' },
  { id: 20, governorate: 'Sousse' },
  { id: 21, governorate: 'Tataouine' },
  { id: 22, governorate: 'Tozeur' },
  { id: 23, governorate: 'Tunis' },
  { id: 24, governorate: 'Zaghouan' },
];

const STATIC_DELEGATIONS = [
  // Ariana (1)
  {id:1,name:'La Soukra',region__id:1},{id:2,name:'Raoued',region__id:1},{id:3,name:'Mnihla',region__id:1},
  {id:4,name:'Ariana Ville',region__id:1},{id:5,name:'Ettadhamen',region__id:1},{id:6,name:'Kalâat el-Andalous',region__id:1},
  {id:7,name:'Sidi Thabet',region__id:1},
  // Béja (2)
  {id:8,name:'Béja Nord',region__id:2},{id:9,name:'Nefza',region__id:2},{id:10,name:'Medjez el-Bab',region__id:2},
  {id:11,name:'Béja Sud',region__id:2},{id:12,name:'Testour',region__id:2},{id:13,name:'Téboursouk',region__id:2},
  {id:14,name:'Amdoun',region__id:2},{id:15,name:'Goubellat',region__id:2},{id:16,name:'Thibar',region__id:2},
  // Ben Arous (3)
  {id:17,name:'El Mourouj',region__id:3},{id:18,name:'Fouchana',region__id:3},{id:19,name:'Mohamedia',region__id:3},
  {id:20,name:'Mornag',region__id:3},{id:21,name:'Radès',region__id:3},{id:22,name:'Medina Jedida',region__id:3},
  {id:23,name:'Bou Mhel el-Bassatine',region__id:3},{id:24,name:'Hammam Lif',region__id:3},
  {id:25,name:'Ezzahra',region__id:3},{id:26,name:'Hammam Chott',region__id:3},
  {id:27,name:'Ben Arous',region__id:3},{id:28,name:'Mégrine',region__id:3},
  // Bizerte (4)
  {id:29,name:'Bizerte Nord',region__id:4},{id:30,name:'Bizerte Sud',region__id:4},{id:31,name:'Ras Jebel',region__id:4},
  {id:32,name:'Menzel Bourguiba',region__id:4},{id:33,name:'Menzel Jemil',region__id:4},{id:34,name:'Mateur',region__id:4},
  {id:35,name:'Sejnane',region__id:4},{id:36,name:'El Alia',region__id:4},{id:37,name:'Joumine',region__id:4},
  {id:38,name:'Ghezala',region__id:4},{id:39,name:'Zarzouna',region__id:4},{id:40,name:'Utique',region__id:4},
  {id:41,name:'Ghar El Melh',region__id:4},{id:42,name:'Tinja',region__id:4},
  // Gabès (5)
  {id:43,name:'Gabès Sud',region__id:5},{id:44,name:'El Hamma',region__id:5},{id:45,name:'Mareth-Dkhila',region__id:5},
  {id:46,name:'Gabès Médina',region__id:5},{id:47,name:'Gabès Ouest',region__id:5},{id:48,name:'Ghannouch',region__id:5},
  {id:49,name:'El Hamma Ouest',region__id:5},{id:50,name:'Oudhref',region__id:5},{id:51,name:'Nouvelle Matmata',region__id:5},
  {id:52,name:'Métouia',region__id:5},{id:53,name:'Menzel El Habib',region__id:5},{id:54,name:'Toujane',region__id:5},
  {id:55,name:'Matmata',region__id:5},
  // Gafsa (6)
  {id:56,name:'Gafsa Sud',region__id:6},{id:57,name:'Métlaoui',region__id:6},{id:58,name:'El Ksar',region__id:6},
  {id:59,name:'Moulares',region__id:6},{id:60,name:'Redeyef',region__id:6},{id:61,name:'Sened',region__id:6},
  {id:62,name:'El Guettar',region__id:6},{id:63,name:'Mdhilla',region__id:6},{id:64,name:'Zannouch',region__id:6},
  {id:65,name:'Belkhir',region__id:6},{id:66,name:'Sidi Aïch',region__id:6},{id:67,name:'Gafsa Nord',region__id:6},
  {id:68,name:'Sidi Boubaker',region__id:6},
  // Jendouba (7)
  {id:69,name:'Jendouba',region__id:7},{id:70,name:'Ghardimaou',region__id:7},{id:71,name:'Tabarka',region__id:7},
  {id:72,name:'Fernana',region__id:7},{id:73,name:'Jendouba Nord',region__id:7},{id:74,name:'Bou Salem',region__id:7},
  {id:75,name:'Balta-Bou Aouane',region__id:7},{id:76,name:'Aïn Draham',region__id:7},{id:77,name:'Oued Meliz',region__id:7},
  // Kairouan (8)
  {id:78,name:'Kairouan Nord',region__id:8},{id:79,name:'Kairouan Sud',region__id:8},{id:80,name:'Bou Hajla',region__id:8},
  {id:81,name:'Sbikha',region__id:8},{id:82,name:'Haffouz',region__id:8},{id:83,name:'Hajeb El Ayoun',region__id:8},
  {id:84,name:'Chebika',region__id:8},{id:85,name:'El Aléa',region__id:8},{id:86,name:'Echrarda',region__id:8},
  {id:87,name:'Oueslatia',region__id:8},{id:88,name:'Nasrallah',region__id:8},{id:89,name:'Menzel Mehiri',region__id:8},
  {id:90,name:'Aïn Djeloula',region__id:8},
  // Kasserine (9)
  {id:91,name:'Sbeïtla',region__id:9},{id:92,name:'Kasserine Nord',region__id:9},{id:93,name:'Fériana',region__id:9},
  {id:94,name:'Foussana',region__id:9},{id:95,name:'Sbiba',region__id:9},{id:96,name:'Thala',region__id:9},
  {id:97,name:'Majel Bel Abbès',region__id:9},{id:98,name:'Kasserine Sud',region__id:9},
  {id:99,name:'Ezzouhour',region__id:9},{id:100,name:'Hassi El Ferid',region__id:9},
  {id:101,name:'El Ayoun',region__id:9},{id:102,name:'Jedelienne',region__id:9},
  {id:103,name:'Haïdra',region__id:9},
  // Kébili (10)
  {id:104,name:'Kébili Nord',region__id:10},{id:105,name:'Kébili Sud',region__id:10},
  {id:106,name:'Douz Nord',region__id:10},{id:107,name:'Souk Lahad',region__id:10},
  {id:108,name:'Douz Sud',region__id:10},{id:109,name:'Faouar',region__id:10},
  {id:110,name:'Rjim Maatoug',region__id:10},
  // Le Kef (11)
  {id:111,name:'Kef Est',region__id:11},{id:112,name:'Kef Ouest',region__id:11},
  {id:113,name:'Tajerouine',region__id:11},{id:114,name:'Dahmani',region__id:11},
  {id:115,name:'Sers',region__id:11},{id:116,name:'Nebeur',region__id:11},
  {id:117,name:'Sakiet Sidi Youssef',region__id:11},{id:118,name:'El Ksour',region__id:11},
  {id:119,name:'Kalaat Senan',region__id:11},{id:120,name:'Jérissa',region__id:11},
  {id:121,name:'Touiref',region__id:11},{id:122,name:'Kalâat Khasba',region__id:11},
  // Mahdia (12)
  {id:123,name:'Mahdia',region__id:12},{id:124,name:'Essouassi',region__id:12},
  {id:125,name:'El Jem',region__id:12},{id:126,name:'Sidi Alouane',region__id:12},
  {id:127,name:'Ksour Essef',region__id:12},{id:128,name:'Bou Merdes',region__id:12},
  {id:129,name:'Chebba',region__id:12},{id:130,name:'Chorbane',region__id:12},
  {id:131,name:'Ouled Chamekh',region__id:12},{id:132,name:'Melloulèche',region__id:12},
  {id:133,name:'El Bradéa',region__id:12},{id:134,name:'Hebira',region__id:12},
  {id:135,name:'Rejiche',region__id:12},
  // La Manouba (13)
  {id:136,name:'Douar Hicher',region__id:13},{id:137,name:'Oued Ellil',region__id:13},
  {id:138,name:'La Manouba',region__id:13},{id:139,name:'Djedeida',region__id:13},
  {id:140,name:'Tebourba',region__id:13},{id:141,name:'Mornaguia',region__id:13},
  {id:142,name:'Borj El Amri',region__id:13},{id:143,name:'El Batan',region__id:13},
  // Médenine (14)
  {id:144,name:'Ben Gardane',region__id:14},{id:145,name:'Djerba - Houmt Souk',region__id:14},
  {id:146,name:'Zarzis',region__id:14},{id:147,name:'Djerba - Midoun',region__id:14},
  {id:148,name:'Médenine Nord',region__id:14},{id:149,name:'Médenine Sud',region__id:14},
  {id:150,name:'Sidi Makhlouf',region__id:14},{id:151,name:'Beni Khedache',region__id:14},
  {id:152,name:'Djerba - Ajim',region__id:14},
  // Monastir (15)
  {id:153,name:'Monastir',region__id:15},{id:154,name:'Moknine',region__id:15},
  {id:155,name:'Jemmal',region__id:15},{id:156,name:'Ksar Hellal',region__id:15},
  {id:157,name:'Ksibet el-Médiouni',region__id:15},{id:158,name:'Téboulba',region__id:15},
  {id:159,name:'Bembla',region__id:15},{id:160,name:'Sahline',region__id:15},
  {id:161,name:'Zéramdine',region__id:15},{id:162,name:'Sayada-Lamta-Bou Hajar',region__id:15},
  {id:163,name:'Ouerdanine',region__id:15},{id:164,name:'Bekalta',region__id:15},
  {id:165,name:'Beni Hassen',region__id:15},
  // Nabeul (16)
  {id:166,name:'Hammam Ghézèze',region__id:16},{id:167,name:'Grombalia',region__id:16},
  {id:168,name:'Korba',region__id:16},{id:169,name:'Nabeul',region__id:16},
  {id:170,name:'Soliman',region__id:16},{id:171,name:'Menzel Temime',region__id:16},
  {id:172,name:'Kélibia',region__id:16},{id:173,name:'Dar Chaâbane El Fehri',region__id:16},
  {id:174,name:'Béni Khiar',region__id:16},{id:175,name:'El Haouaria',region__id:16},
  {id:176,name:'Béni Khalled',region__id:16},{id:177,name:'Menzel Bouzelfa',region__id:16},
  {id:178,name:'Bou Argoub',region__id:16},{id:179,name:'El Mida',region__id:16},
  {id:180,name:'Takelsa',region__id:16},
  // Sfax (17)
  {id:181,name:'Sfax Sud',region__id:17},{id:182,name:'Sakiet Eddaïer',region__id:17},
  {id:183,name:'Sfax Ouest',region__id:17},{id:184,name:'Sfax Ville',region__id:17},
  {id:185,name:'Sakiet Ezzit',region__id:17},{id:186,name:'Thyna',region__id:17},
  {id:187,name:'Jebiniana',region__id:17},{id:188,name:'El Hencha',region__id:17},
  {id:189,name:'Bir Ali Ben Khalifa',region__id:17},{id:190,name:'Agareb',region__id:17},
  {id:191,name:'Menzel Chaker',region__id:17},{id:192,name:'Skhira',region__id:17},
  {id:193,name:'El Amra',region__id:17},{id:194,name:'Mahres',region__id:17},
  {id:195,name:'Graïba',region__id:17},{id:196,name:'Kerkennah',region__id:17},
  // Sidi Bouzid (18)
  {id:197,name:'Sidi Bouzid Ouest',region__id:18},{id:198,name:'Sidi Bouzid Est',region__id:18},
  {id:199,name:'Regueb',region__id:18},{id:200,name:'Jilma',region__id:18},
  {id:201,name:'Bir El Hafey',region__id:18},{id:202,name:'Sidi Ali Ben Aoun',region__id:18},
  {id:203,name:'Menzel Bouzaiane',region__id:18},{id:204,name:'Essaïda',region__id:18},
  {id:205,name:'Mezzouna',region__id:18},{id:206,name:'Souk Jedid',region__id:18},
  {id:207,name:'Cebbala Ouled Asker',region__id:18},{id:208,name:'Meknassy',region__id:18},
  {id:209,name:'Ouled Haffouz',region__id:18},{id:210,name:'Hichria',region__id:18},
  // Siliana (19)
  {id:211,name:'Siliana Sud',region__id:19},{id:212,name:'Siliana Nord',region__id:19},
  {id:213,name:'Makthar',region__id:19},{id:214,name:'Rouhia',region__id:19},
  {id:215,name:'El Krib',region__id:19},{id:216,name:'Bou Arada',region__id:19},
  {id:217,name:'Gaâfour',region__id:19},{id:218,name:'Kesra',region__id:19},
  {id:219,name:'Sidi Bou Rouis',region__id:19},{id:220,name:'Bargou',region__id:19},
  {id:221,name:'El Aroussa',region__id:19},
  // Sousse (20)
  {id:222,name:'Sousse Jawhara',region__id:20},{id:223,name:"M'saken",region__id:20},
  {id:224,name:'Sousse Riadh',region__id:20},{id:225,name:'Kalâa Kebira',region__id:20},
  {id:226,name:'Enfida',region__id:20},{id:227,name:'Sousse Sidi Abdelhamid',region__id:20},
  {id:228,name:'Zaouiet Ksibet Thrayet',region__id:20},{id:229,name:'Hammam Sousse',region__id:20},
  {id:230,name:'Kalâa Seghira',region__id:20},{id:231,name:'Akouda',region__id:20},
  {id:232,name:'Bouficha',region__id:20},{id:233,name:'Sousse Médina',region__id:20},
  {id:234,name:'Sidi Bou Ali',region__id:20},{id:235,name:'Kondar',region__id:20},
  {id:236,name:'Sidi El Hani',region__id:20},{id:237,name:'Hergla',region__id:20},
  // Tataouine (21)
  {id:238,name:'Tataouine Nord',region__id:21},{id:239,name:'Tataouine Sud',region__id:21},
  {id:240,name:'Ghomrassen',region__id:21},{id:241,name:'Bir Lahmar',region__id:21},
  {id:242,name:'Remada',region__id:21},{id:243,name:'Beni Mhira',region__id:21},
  {id:244,name:'Smâr',region__id:21},{id:245,name:'Dehiba',region__id:21},
  // Tozeur (22)
  {id:246,name:'Tozeur',region__id:22},{id:247,name:'Degache',region__id:22},
  {id:248,name:'Nefta',region__id:22},{id:249,name:'El Hamma du Jérid',region__id:22},
  {id:250,name:'Tameghza',region__id:22},{id:251,name:'Hazoua',region__id:22},
  // Tunis (23)
  {id:252,name:'Sidi Hassine',region__id:23},{id:253,name:'Hrairia',region__id:23},
  {id:254,name:'La Marsa',region__id:23},{id:255,name:'Le Kram',region__id:23},
  {id:256,name:'El Kabaria',region__id:23},{id:257,name:'Le Bardo',region__id:23},
  {id:258,name:'El Omrane supérieur',region__id:23},{id:259,name:'La Goulette',region__id:23},
  {id:260,name:'El Menzah',region__id:23},{id:261,name:'El Omrane',region__id:23},
  {id:262,name:'Ezzouhour',region__id:23},{id:263,name:'Cité El Khadra',region__id:23},
  {id:264,name:'Bab El Bhar',region__id:23},{id:265,name:'El Ouardia',region__id:23},
  {id:266,name:'Séjoumi',region__id:23},{id:267,name:'Bab Souika',region__id:23},
  {id:268,name:'Sidi El Béchir',region__id:23},{id:269,name:'Djebel Jelloud',region__id:23},
  {id:270,name:'Carthage',region__id:23},{id:271,name:'Ettahrir',region__id:23},
  {id:272,name:'Médina',region__id:23},
  // Zaghouan (24)
  {id:273,name:'El Fahs',region__id:24},{id:274,name:'Zaghouan',region__id:24},
  {id:275,name:'Nadhour',region__id:24},{id:276,name:'Zriba',region__id:24},
  {id:277,name:'Bir Mcherga',region__id:24},{id:278,name:'Saouaf',region__id:24},
];

// ── Property type config ──────────────────────────────────────────────────────
const PROPERTY_TYPES = [
  { value: 'apartment',  label: 'Apartment',  icon: '🏢' },
  { value: 'house',      label: 'House',      icon: '🏠' },
  { value: 'commercial', label: 'Commercial', icon: '🏪' },
  { value: 'land',       label: 'Land',       icon: '🏗️' },
];

const CONDITIONS = [
  { value: 'new',              label: '✨ New' },
  { value: 'excellent',        label: '🌟 Excellent' },
  { value: 'good',             label: '✅ Good' },
  { value: 'fair',             label: '⚠️ Fair' },
  { value: 'needs renovation', label: '🔧 Needs Renovation' },
];

const INITIAL_FORM = {
  property_type: 'apartment', transaction_type: 'sale',
  governorate: '', delegation: '',
  size_m2: '', bedrooms: '', bathrooms: '', condition: 'good',
  has_pool: false, has_garden: false, has_parking: false, sea_view: false, elevator: false,
  description: '',
};

// ── CSS helpers ───────────────────────────────────────────────────────────────
const inputCls =
  'w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2.5 text-sm text-white ' +
  'placeholder-gray-600 focus:border-[#FF6B35]/60 focus:outline-none focus:ring-1 ' +
  'focus:ring-[#FF6B35]/30 transition-colors';

// ── UI atoms ──────────────────────────────────────────────────────────────────
function Card({ title, icon: Icon, children, accent, className = '' }) {
  return (
    <div className={`rounded-2xl border p-5 ${
      accent ? 'border-[#FF6B35]/30 bg-[#FF6B35]/5' : 'border-white/10 bg-white/5'
    } ${className}`}>
      {title && (
        <p className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-gray-400">
          {Icon && <Icon size={13} />}{title}
        </p>
      )}
      {children}
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-semibold uppercase tracking-widest text-gray-400">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-600">{hint}</p>}
    </div>
  );
}

function Badge({ label, cls }) {
  return <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

function AmenityBtn({ label, icon, checked, onChange, disabled }) {
  return (
    <button
      type="button" disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition-all
        ${disabled ? 'opacity-30 cursor-not-allowed border-white/5 bg-transparent text-gray-600'
          : checked ? 'border-[#FF6B35]/60 bg-[#FF6B35]/15 text-[#FFB38F]'
          : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20 hover:text-gray-200'}`}
    >
      <span>{icon}</span>{label}
      {checked && !disabled && <CheckCircle2 size={12} className="ml-auto text-[#FF6B35]" />}
    </button>
  );
}

// ── Confidence gauge (SVG arc) ────────────────────────────────────────────────
function ConfidenceGauge({ confidence, level }) {
  const r = 56, sz = 152, cx = sz / 2, cy = sz / 2;
  const circ = 2 * Math.PI * r;
  const prog = (confidence / 100) * circ;
  const color = confidence >= 80 ? '#22c55e' : confidence >= 65 ? '#FF6B35' : '#ef4444';
  const track = confidence >= 80 ? '#14532d' : confidence >= 65 ? '#431407' : '#450a0a';
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative">
        <svg width={sz} height={sz} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={track} strokeWidth="12" />
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="12"
            strokeLinecap="round" strokeDasharray={`${prog} ${circ}`}
            style={{ transition: 'stroke-dasharray 1.2s ease-in-out' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-black text-white">{confidence}</span>
          <span className="text-xs text-gray-500">/ 100</span>
        </div>
      </div>
      <span className="text-sm font-semibold" style={{ color }}>{level} Confidence</span>
    </div>
  );
}

// ── SHAP bar chart ────────────────────────────────────────────────────────────
function ShapChart({ features }) {
  if (!features?.length) return null;
  const data = features.slice(0, 7).map(f => ({
    name: f.feature, value: f.impact, direction: f.direction, percent: f.percent,
  }));
  const Tip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="rounded-lg border border-white/20 bg-[#111827] px-3 py-2 text-xs shadow-xl">
        <p className="font-semibold text-white">{d.name}</p>
        <p style={{ color: d.direction === 'positive' ? '#22c55e' : '#ef4444' }}>
          {d.direction === 'positive' ? '+' : '-'}{d.value.toLocaleString()} TND ({d.percent}%)
        </p>
      </div>
    );
  };
  return (
    <ResponsiveContainer width="100%" height={data.length * 46 + 16}>
      <BarChart layout="vertical" data={data} margin={{ left: 10, right: 64, top: 4, bottom: 4 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="name" width={135}
          tick={{ fill: '#9ca3af', fontSize: 12 }} axisLine={false} tickLine={false} />
        <Tooltip content={<Tip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
        <Bar dataKey="value" radius={[0, 5, 5, 0]} minPointSize={4}>
          {data.map((e, i) => (
            <Cell key={i} fill={e.direction === 'positive' ? '#22c55e' : '#ef4444'} fillOpacity={0.85} />
          ))}
          <LabelList dataKey="percent" position="right" formatter={v => `${v}%`}
            style={{ fill: '#6b7280', fontSize: 11 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Comparables table ─────────────────────────────────────────────────────────
function ComparablesTable({ rows }) {
  if (!rows?.length) return (
    <p className="text-sm text-gray-500 italic">No comparable listings in the database yet. Run the scraper to populate market evidence.</p>
  );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 text-xs uppercase tracking-wider text-gray-500">
            <th className="pb-2 text-left">Property</th>
            <th className="pb-2 text-right">Price</th>
            <th className="pb-2 text-right">m²</th>
            <th className="pb-2 text-right">TND/m²</th>
            <th className="pb-2 text-right">Match</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.map((c, i) => (
            <tr key={i} className="hover:bg-white/5 transition-colors">
              <td className="py-2.5 pr-4">
                <p className="text-white font-medium line-clamp-1">{c.title || '—'}</p>
                <p className="text-xs text-gray-500">{c.city ? `${c.city}, ` : ''}{c.governorate}</p>
                {c.difference && <p className="text-xs text-gray-600 italic">{c.difference}</p>}
              </td>
              <td className="py-2.5 text-right text-white">{(c.price||0).toLocaleString()}</td>
              <td className="py-2.5 text-right text-gray-300">{c.size_m2}</td>
              <td className="py-2.5 text-right text-gray-300">{c.price_per_m2?.toLocaleString() || '—'}</td>
              <td className="py-2.5 text-right">
                <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                  c.similarity >= 70 ? 'bg-green-500/15 text-green-400'
                  : c.similarity >= 50 ? 'bg-orange-500/15 text-orange-400'
                  : 'bg-gray-500/15 text-gray-400'}`}>{c.similarity}%</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Market context ────────────────────────────────────────────────────────────
function MarketContext({ market }) {
  if (!market) return null;
  const posColor = { above_market:'text-orange-400', below_market:'text-green-400', at_market:'text-blue-400', unknown:'text-gray-400' };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { l:'Avg Price/m²', v: market.avg_price_per_m2 ? `${market.avg_price_per_m2.toLocaleString()} TND` : 'N/A' },
          { l:'Comparables',  v: market.comparable_count ?? 0 },
          { l:'Market Trend', v: (market.market_trend||'stable').replace('_',' ') },
          { l:'Position',     v: (market.price_position||'unknown').replace(/_/g,' '), col: posColor[market.price_position] },
        ].map(({ l, v, col }) => (
          <div key={l} className="rounded-xl border border-white/10 bg-white/5 p-3 text-center">
            <p className="text-xs uppercase tracking-wider text-gray-500">{l}</p>
            <p className={`mt-1 text-base font-bold capitalize ${col||'text-white'}`}>{v}</p>
          </div>
        ))}
      </div>
      {market.price_range?.min && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <p className="text-xs uppercase tracking-wider text-gray-500 mb-2">Market Price Range</p>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-300">{market.price_range.min.toLocaleString()} TND</span>
            <div className="flex-1 h-1.5 rounded-full bg-white/10">
              <div className="h-full w-full rounded-full bg-gradient-to-r from-green-500 to-orange-500" />
            </div>
            <span className="text-sm text-gray-300">{market.price_range.max.toLocaleString()} TND</span>
          </div>
        </div>
      )}
      {market.market_direction && (
        <p className="text-xs text-gray-500 italic">{market.market_direction}</p>
      )}
    </div>
  );
}

// ── AI Explanation text ───────────────────────────────────────────────────────
function Explanation({ text }) {
  if (!text) return null;
  const parts = text.split('**').map((s, i) =>
    i % 2 === 1 ? <strong key={i} className="text-white">{s}</strong> : s
  );
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 h-fit flex-shrink-0 rounded-lg bg-[#FF6B35]/20 p-2">
        <Brain size={15} className="text-[#FF6B35]" />
      </div>
      <p className="text-sm leading-relaxed text-gray-300">{parts}</p>
    </div>
  );
}

// ── Signal breakdown bars ─────────────────────────────────────────────────────
function Signals({ breakdown }) {
  if (!breakdown) return null;
  const SIGNALS = [
    { k:'base_quality',     l:'Model Quality',       w:'35%' },
    { k:'completeness',     l:'Input Completeness',  w:'25%' },
    { k:'image_score',      l:'Image Coverage',      w:'15%' },
    { k:'text_score',       l:'Text Quality',        w:'10%' },
    { k:'comparable_score', l:'Market Evidence',     w:'15%' },
  ];
  return (
    <div className="space-y-2.5">
      {SIGNALS.map(({ k, l, w }) => {
        const pct = Math.round((breakdown[k]??0)*100);
        return (
          <div key={k} className="flex items-center gap-3">
            <span className="w-40 flex-shrink-0 text-xs text-gray-400">{l}</span>
            <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-white/10">
              <motion.div initial={{width:0}} animate={{width:`${pct}%`}}
                transition={{duration:0.8}} className="h-full rounded-full bg-[#FF6B35]" />
            </div>
            <span className="w-14 text-right text-xs text-gray-500">{pct}% <span className="text-gray-700">({w})</span></span>
          </div>
        );
      })}
    </div>
  );
}

// ── Text analysis ─────────────────────────────────────────────────────────────
function TextAnalysis({ ta }) {
  if (!ta) return null;
  const sc = { positive:'text-green-400', neutral:'text-gray-400', negative:'text-red-400' };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        {[
          { l:'Description Quality', v: ta.description_quality||'N/A',
            sub: <div className="mt-1 h-1 rounded-full bg-white/10 overflow-hidden"><div className="h-full rounded-full bg-[#FF6B35]" style={{width:`${Math.round((ta.description_score||0)*100)}%`}} /></div> },
          { l:'Sentiment', v: ta.sentiment_label||'neutral', colored: sc[ta.sentiment_label], sub: <p className="text-xs text-gray-500">{ta.token_count||0} words · {ta.sentiment_mode||''}</p> },
          { l:'Marketing', v: ta.marketing_effectiveness||'N/A' },
        ].map(({ l, v, colored, sub }) => (
          <div key={l} className="rounded-xl border border-white/10 bg-white/5 p-3">
            <p className="text-xs uppercase tracking-wider text-gray-500">{l}</p>
            <p className={`mt-1 font-bold capitalize ${colored||'text-white'}`}>{v}</p>
            {sub}
          </div>
        ))}
      </div>
      {ta.key_phrases?.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <p className="text-xs uppercase tracking-wider text-gray-500 mb-2">Detected Key Phrases</p>
          <div className="flex flex-wrap gap-2">
            {ta.key_phrases.map((kw,i) => (
              <span key={i} className="rounded-full border border-[#FF6B35]/30 bg-[#FF6B35]/10 px-2.5 py-0.5 text-xs text-[#FFB38F]">{kw}</span>
            ))}
          </div>
        </div>
      )}
      {ta.location_sentiment && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 flex items-center gap-3">
          <MapPin size={14} className="text-[#FF6B35] flex-shrink-0" />
          <div>
            <p className="text-xs uppercase tracking-wider text-gray-500">Location Sentiment</p>
            <p className={`text-sm font-semibold capitalize ${sc[ta.location_sentiment.label]||'text-white'}`}>
              {ta.location_sentiment.label} ({(ta.location_sentiment.score*100).toFixed(0)}% positive signal)
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Image analysis panel ──────────────────────────────────────────────────────
function ImageAnalysis({ ia }) {
  if (!ia) return null;
  return (
    <div className="space-y-2 text-sm">
      {[
        { k:'Images Submitted', v: ia.image_count ?? 0 },
        { k:'Coverage Score',  v: `${Math.round((ia.coverage_score||0)*100)}%` },
        { k:'Quality Score',   v: `${Math.round((ia.quality_score||0)*100)}%` },
        { k:'CV Mode',         v: ia.cv_mode || 'no_cv' },
        { k:'Status',          v: ia.status || '—' },
      ].map(({ k, v }) => (
        <div key={k} className="flex justify-between border-b border-white/5 pb-1.5">
          <span className="text-gray-500">{k}</span>
          <span className="font-mono text-gray-200">{v}</span>
        </div>
      ))}
      {ia.image_analysis && <p className="text-xs text-gray-500 italic mt-1">{ia.image_analysis}</p>}
    </div>
  );
}

// ── Waterfall ─────────────────────────────────────────────────────────────────
function Waterfall({ shap }) {
  if (!shap?.baseline) return null;
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between rounded-lg bg-white/5 px-3 py-2 text-sm">
        <span className="text-gray-400">Baseline (National Average)</span>
        <span className="font-mono font-semibold text-white">{shap.baseline.toLocaleString()} TND</span>
      </div>
      {(shap.contributions||[]).map((c, i) => (
        <div key={i} className="flex justify-between rounded-lg bg-white/5 px-3 py-2 text-sm">
          <span className="text-gray-400">{c.feature}</span>
          <span className={`font-mono font-semibold ${c.delta>=0?'text-green-400':'text-red-400'}`}>
            {c.delta>=0?'+':''}{c.delta.toLocaleString()} TND
          </span>
        </div>
      ))}
      <div className="flex justify-between rounded-lg border border-[#FF6B35]/30 bg-[#FF6B35]/10 px-3 py-2 text-sm">
        <span className="font-semibold text-[#FFB38F]">Final Estimate</span>
        <span className="font-mono font-black text-white">{shap.predicted?.toLocaleString()} TND</span>
      </div>
    </div>
  );
}

// ── Warnings banner ───────────────────────────────────────────────────────────
function Warnings({ items }) {
  const all = (items||[]).filter(Boolean);
  if (!all.length) return null;
  return (
    <div className="flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3">
      <AlertTriangle size={15} className="mt-0.5 flex-shrink-0 text-amber-400" />
      <div className="space-y-0.5">
        {all.map((w,i) => <p key={i} className="text-xs text-amber-300">{w}</p>)}
      </div>
    </div>
  );
}

// ── Scenario cards ────────────────────────────────────────────────────────────
function ScenariosPanel({ scenarios, currency }) {
  if (!scenarios?.length) return (
    <p className="text-sm text-gray-500 italic">No scenarios available — provide amenities and condition data to generate what-if analysis.</p>
  );
  return (
    <div className="space-y-3">
      {scenarios.map((s, i) => {
        const positive = s.price_delta >= 0;
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.07 }}
            className={`rounded-xl border p-4 ${positive ? 'border-emerald-500/25 bg-emerald-500/5' : 'border-red-500/25 bg-red-500/5'}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-white">{s.scenario_name}</p>
                <p className="text-xs text-gray-400 mt-0.5">{s.scenario_description}</p>
                <p className="text-xs text-gray-500 mt-1.5 italic">{s.why}</p>
              </div>
              <div className="flex-shrink-0 text-right">
                <p className={`text-lg font-black ${positive ? 'text-emerald-400' : 'text-red-400'}`}>
                  {positive ? '+' : ''}{s.price_delta?.toLocaleString()} {currency}
                </p>
                <p className={`text-xs font-semibold ${positive ? 'text-emerald-500' : 'text-red-500'}`}>
                  {positive ? '+' : ''}{s.delta_percentage?.toFixed(1)}%
                </p>
                <p className="text-xs text-gray-600 mt-0.5">→ {s.predicted_price?.toLocaleString()} {currency}</p>
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

// ── Results panel ─────────────────────────────────────────────────────────────
function Results({ result, txType }) {
  const [tab, setTab] = useState('overview');
  const TABS = [
    { id:'overview',      l:'Overview',      I:Home },
    { id:'impact',        l:'Price Drivers', I:BarChart2 },
    { id:'market',        l:'Market',        I:TrendingUp },
    { id:'scenarios',     l:'Scenarios',     I:Zap },
  ];
  const currency   = txType === 'rent' ? 'TND/mo' : 'TND';
  const priceLabel = txType === 'rent' ? 'Monthly Rent Estimate' : 'Estimated Market Value';

  return (
    <motion.div initial={{opacity:0,y:24}} animate={{opacity:1,y:0}} transition={{duration:0.5}}
      className="mt-8 space-y-5">

      {/* Main price card */}
      <div className="rounded-2xl border border-[#FF6B35]/40 bg-gradient-to-br from-[#FF6B35]/10 via-[#FF6B35]/5 to-transparent p-6">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="flex-1">
            <p className="text-xs uppercase tracking-widest text-[#FFB38F]">{priceLabel}</p>
            <p className="mt-1 text-5xl font-black text-white">
              {result.estimated_price?.toLocaleString()}
              <span className="ml-2 text-xl font-semibold text-[#FFB38F]">{currency}</span>
            </p>
            <p className="mt-1.5 text-sm text-gray-400">
              Range: <span className="text-white">{result.lower_bound?.toLocaleString()} – {result.upper_bound?.toLocaleString()} {currency}</span>
              <span className="ml-2 text-gray-600">(±{Math.round((result.uncertainty_ratio??0.14)*100)}%)</span>
            </p>
            {result.price_per_m2 > 0 && (
              <p className="mt-0.5 text-sm text-gray-400">
                ≈ <span className="font-semibold text-white">{result.price_per_m2?.toLocaleString()} TND/m²</span>
              </p>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge label={result.prediction_mode?.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())||'Heuristic'}
                cls="bg-blue-500/20 text-blue-300 border-blue-500/30" />
              <Badge label={`${result.confidence_level} Confidence`}
                cls={result.confidence>=80?'bg-green-500/20 text-green-300 border-green-500/30'
                   :result.confidence>=65?'bg-orange-500/20 text-orange-300 border-orange-500/30'
                   :'bg-red-500/20 text-red-300 border-red-500/30'} />
              <Badge label={`${result.comparables?.length??0} Comparables`}
                cls="bg-purple-500/20 text-purple-300 border-purple-500/30" />
              {result.image_analysis?.image_count > 0 && (
                <Badge label={`${result.image_analysis.image_count} Image(s)`}
                  cls="bg-teal-500/20 text-teal-300 border-teal-500/30" />
              )}
              {result.scenarios?.length > 0 && (
                <Badge label={`${result.scenarios.length} Scenarios`}
                  cls="bg-emerald-500/20 text-emerald-300 border-emerald-500/30" />
              )}
            </div>
          </div>
          <ConfidenceGauge confidence={result.confidence} level={result.confidence_level} />
        </div>
      </div>

      <Warnings items={[...(result.warnings||[]), ...(result.uncertainty_reasons||[])]} />

      {/* Tab bar */}
      <div className="flex gap-1 rounded-xl border border-white/10 bg-white/5 p-1">
        {TABS.map(({ id, l, I }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-semibold transition-all
              ${tab===id ? 'bg-[#FF6B35] text-white shadow' : 'text-gray-400 hover:text-gray-200'}`}>
            <I size={13} /><span className="hidden sm:inline">{l}</span>
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}
          exit={{opacity:0,y:-8}} transition={{duration:0.2}}>

          {tab === 'overview' && (
            <div className="space-y-4">
              <Card title="AI Explanation" icon={Brain}>
                <Explanation text={result.ai_explanation} />
              </Card>
              <Card title="Confidence Signal Breakdown" icon={Activity}>
                <Signals breakdown={result.signal_breakdown} />
              </Card>
              <Card title="Description Analysis" icon={FileText}>
                <TextAnalysis ta={result.text_analysis} />
              </Card>
            </div>
          )}

          {tab === 'impact' && (
            <div className="space-y-4">
              <Card title="What Drives This Price" icon={BarChart2}>
                {result.features_impact?.length ? (
                  <>
                    <p className="mb-4 text-xs text-gray-500">
                      Each bar shows how a feature shifts the estimate from the national baseline.
                      Green = price driver, Red = price reducer.
                    </p>
                    <ShapChart features={result.features_impact} />
                  </>
                ) : (
                  <p className="text-sm text-gray-500 italic">No attribution data.</p>
                )}
              </Card>
              <Card title="Price Waterfall" icon={Layers}>
                <Waterfall shap={result.shap} />
              </Card>
            </div>
          )}

          {tab === 'market' && (
            <div className="space-y-4">
              <Card title="Market Context" icon={TrendingUp}>
                <MarketContext market={result.market_context} />
              </Card>
              <Card title="Comparable Listings" icon={Building2}>
                <ComparablesTable rows={result.comparables} />
              </Card>
            </div>
          )}

          {tab === 'scenarios' && (
            <div className="space-y-4">
              <Card title="What-If Scenarios" icon={Zap} accent>
                <p className="mb-4 text-xs text-gray-500">
                  Simulated upgrades ranked by potential price impact. These are estimates based on
                  current market data — actual gains depend on execution quality and local demand.
                </p>
                <ScenariosPanel scenarios={result.scenarios} currency={currency} />
              </Card>
            </div>
          )}

        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Functional mode (Pro users)
// ─────────────────────────────────────────────────────────────────────────────
function FunctionalMode() {
  const [form, setForm] = useState(INITIAL_FORM);
  const [images, setImages] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [regions, setRegions] = useState(STATIC_REGIONS);
  const [delegations, setDelegations] = useState(STATIC_DELEGATIONS);
  const resultsRef = useRef(null);
  const fileRef = useRef(null);

  // Try to load locations from API, fallback to static
  useEffect(() => {
    api.get('/valuations/locations/').then(r => {
      if (r.data?.regions?.length)      setRegions(r.data.regions);
      if (r.data?.delegations?.length)  setDelegations(r.data.delegations);
    }).catch(() => {});
  }, []);

  const set = useCallback((k, v) => setForm(p => ({ ...p, [k]: v })), []);

  const isLand = form.property_type === 'land';

  // Delegations for selected governorate
  const selectedRegion = regions.find(r => r.governorate === form.governorate);
  const filteredDelegations = selectedRegion
    ? delegations.filter(d => d.region__id === selectedRegion.id)
    : [];

  // Image handling
  const handleImages = (files) => {
    const arr = Array.from(files).slice(0, 5);
    setImages(arr);
    setPreviews(arr.map(f => URL.createObjectURL(f)));
  };
  const removeImage = (idx) => {
    const newImgs = images.filter((_, i) => i !== idx);
    const newPrev = previews.filter((_, i) => i !== idx);
    URL.revokeObjectURL(previews[idx]);
    setImages(newImgs);
    setPreviews(newPrev);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setResult(null); setLoading(true);
    try {
      const fd = new FormData();
      const fields = {
        ...form,
        size_m2:   form.size_m2   ? parseFloat(form.size_m2)  : undefined,
        bedrooms:  form.bedrooms  ? parseInt(form.bedrooms)   : undefined,
        bathrooms: form.bathrooms ? parseInt(form.bathrooms)  : undefined,
        image_count: images.length,
        city: form.delegation || form.city || '',
      };
      Object.entries(fields).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          fd.append(k, typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v));
        }
      });
      images.forEach(img => fd.append('images', img));

      const res = await api.post('/valuations/predict/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
    } catch (err) {
      const d = err.response?.data;
      setError(
        d?.detail || d?.error ||
        (typeof d === 'object' ? Object.values(d).flat().join(' ') : null) ||
        'Valuation failed. Please check your inputs.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setForm(INITIAL_FORM);
    previews.forEach(p => URL.revokeObjectURL(p));
    setImages([]); setPreviews([]); setResult(null); setError('');
  };

  return (
    <section className="max-w-5xl space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-[#FF6B35]/30 bg-[#FF6B35]/10 px-4 py-2 text-sm font-mono text-[#FFB38F]">
          <Sparkles size={16} /> AI Price Predictor · EstateMind
        </div>
        <h1 className="mt-4 text-4xl font-black tracking-tight text-white">
          Property Valuation
        </h1>
        <p className="mt-2 max-w-2xl text-gray-400">
          Fill in your property details and get an accurate price estimate based on real Tunisian market data,
          comparable listings, and photo quality analysis.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* 1 — Property type */}
        <Card title="Property Type" icon={Home}>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {PROPERTY_TYPES.map(pt => (
              <button key={pt.value} type="button"
                onClick={() => { set('property_type', pt.value); if (pt.value==='land') { set('has_pool',false); set('has_garden',false); set('has_parking',false); set('sea_view',false); set('elevator',false); }}}
                className={`flex flex-col items-center gap-2 rounded-xl border py-5 text-sm font-semibold transition-all ${
                  form.property_type===pt.value
                    ? 'border-[#FF6B35] bg-[#FF6B35]/15 text-white shadow-lg shadow-[#FF6B35]/10'
                    : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/25 hover:text-gray-200 hover:bg-white/8'
                }`}>
                <span className="text-3xl">{pt.icon}</span>
                {pt.label}
              </button>
            ))}
          </div>
          <Field label="Transaction Type">
            <div className="flex gap-2">
              {[{v:'sale',l:'💰 Sale'},{v:'rent',l:'📅 Rent'}].map(({v,l}) => (
                <button key={v} type="button" onClick={() => set('transaction_type', v)}
                  className={`flex-1 rounded-xl border py-2.5 text-sm font-semibold transition-all ${
                    form.transaction_type===v
                      ? 'border-[#FF6B35] bg-[#FF6B35]/20 text-white'
                      : 'border-white/15 bg-black/20 text-gray-400 hover:border-white/25'
                  }`}>{l}</button>
              ))}
            </div>
          </Field>
        </Card>

        {/* 2 — Location */}
        <Card title="Location" icon={MapPin}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Governorate">
              <select className={inputCls + ' cursor-pointer'}
                value={form.governorate}
                onChange={e => { set('governorate', e.target.value); set('delegation', ''); }}>
                <option value="">— Select a governorate —</option>
                {regions.map(r => (
                  <option key={r.id} value={r.governorate}>{r.governorate}</option>
                ))}
              </select>
            </Field>
            <Field label="Delegation">
              <select className={inputCls + ' cursor-pointer'}
                value={form.delegation}
                onChange={e => set('delegation', e.target.value)}
                disabled={!form.governorate}>
                <option value="">— Select a delegation —</option>
                {filteredDelegations.map(d => (
                  <option key={d.id} value={d.name}>{d.name}</option>
                ))}
              </select>
            </Field>
          </div>
        </Card>

        {/* 3 — Property details */}
        <Card title="Property Details" icon={Building2}>
          <div className={`grid gap-4 ${isLand ? 'sm:grid-cols-2' : 'sm:grid-cols-4'}`}>
            <Field label="Area (m²)">
              <input className={inputCls} type="number" min="1" placeholder="e.g. 120"
                value={form.size_m2} onChange={e => set('size_m2', e.target.value)} />
            </Field>
            {!isLand && (
              <>
                <Field label="Bedrooms" hint="Optional">
                  <input className={inputCls} type="number" min="0" max="20" placeholder="—"
                    value={form.bedrooms} onChange={e => set('bedrooms', e.target.value)} />
                </Field>
                <Field label="Bathrooms" hint="Optional">
                  <input className={inputCls} type="number" min="0" max="10" placeholder="—"
                    value={form.bathrooms} onChange={e => set('bathrooms', e.target.value)} />
                </Field>
              </>
            )}
            <Field label="Condition">
              <select className={inputCls + ' cursor-pointer'}
                value={form.condition} onChange={e => set('condition', e.target.value)}>
                {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </Field>
          </div>
        </Card>

        {/* 4 — Amenities */}
        <Card title="Amenities" icon={Sparkles}>
          {isLand && (
            <p className="mb-3 flex items-center gap-2 text-xs text-amber-400">
              <AlertCircle size={13} /> Amenities are not applicable for Land listings.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <AmenityBtn label="Pool"      icon="🏊" checked={form.has_pool}    onChange={v=>set('has_pool',v)}    disabled={isLand} />
            <AmenityBtn label="Garden"    icon="🌿" checked={form.has_garden}  onChange={v=>set('has_garden',v)}  disabled={isLand} />
            <AmenityBtn label="Parking"   icon="🚗" checked={form.has_parking} onChange={v=>set('has_parking',v)} disabled={isLand} />
            <AmenityBtn label="Sea View"  icon="🌊" checked={form.sea_view}    onChange={v=>set('sea_view',v)}    disabled={isLand} />
            <AmenityBtn label="Elevator"  icon="🛗" checked={form.elevator}    onChange={v=>set('elevator',v)}    disabled={isLand} />
          </div>
        </Card>

        {/* 5 — Images */}
        <Card title="Property Photos" icon={ImageIcon}>
          <div
            className="relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-white/20 bg-white/5 p-6 text-center transition-colors hover:border-[#FF6B35]/40 cursor-pointer"
            onClick={() => fileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); }}
            onDrop={e => { e.preventDefault(); handleImages(e.dataTransfer.files); }}
          >
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden
              onChange={e => handleImages(e.target.files)} />
            <ImageIcon size={28} className="text-gray-500 mb-2" />
            <p className="text-sm text-gray-400">Drag & drop or click to upload (max 5)</p>
            <p className="text-xs text-gray-600 mt-1">JPG, PNG, WEBP · Max 200 MB each</p>
            <p className="mt-2 text-xs text-[#FFB38F]">
              Images improve confidence scoring and vision analysis.
            </p>
          </div>
          {previews.length > 0 && (
            <div className="mt-3 grid grid-cols-5 gap-2">
              {previews.map((src, i) => (
                <div key={i} className="relative group">
                  <img src={src} alt={`upload-${i}`}
                    className="h-20 w-full rounded-lg object-cover border border-white/10" />
                  <button type="button" onClick={() => removeImage(i)}
                    className="absolute top-1 right-1 hidden group-hover:flex items-center justify-center rounded-full bg-black/70 p-1 transition-all">
                    <X size={10} className="text-white" />
                  </button>
                  <p className="mt-0.5 text-center text-xs text-gray-600 truncate">
                    {images[i]?.name?.split('.')[0].slice(0, 10)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* 6 — Description */}
        <Card title="Property Description" icon={FileText}>
          <Field label="Description"
            hint="A detailed description helps the AI better understand the property and refines the estimate.">
            <textarea className={inputCls + ' resize-none'} rows={5}
              placeholder="Describe your property — renovations, finishes, views, amenities, surroundings…"
              value={form.description} onChange={e => set('description', e.target.value)} />
          </Field>
          {form.description.length > 0 && (
            <p className="mt-1 text-right text-xs text-gray-600">{form.description.length} / 10 000</p>
          )}
        </Card>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <AlertCircle size={15} className="flex-shrink-0" />{error}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button type="submit" disabled={loading}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#FF6B35] px-6 py-3.5 text-sm font-bold text-white shadow-lg shadow-[#FF6B35]/20 transition-all hover:bg-[#e55a24] disabled:cursor-not-allowed disabled:opacity-60">
            {loading
              ? <><Loader2 size={16} className="animate-spin" /> Analysing…</>
              : <><Sparkles size={16} /> Estimate Value <ArrowRight size={16} /></>}
          </button>
          {(result || error) && (
            <button type="button" onClick={handleReset}
              className="flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-3.5 text-sm font-semibold text-gray-300 transition-all hover:border-white/25">
              <X size={15} /> Reset
            </button>
          )}
        </div>
      </form>

      {/* Results */}
      <div ref={resultsRef}>
        <AnimatePresence>
          {result && <Results result={result} txType={form.transaction_type} />}
        </AnimatePresence>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Informational mode (free users)
// ─────────────────────────────────────────────────────────────────────────────
function InformationalMode() {
  return (
    <section className="max-w-4xl space-y-8">
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-[#FF6B35]/30 bg-[#FF6B35]/10 px-4 py-2 text-sm font-mono text-[#FFB38F]">
          <Sparkles size={16} /> AI Price Predictor — Pro Feature
        </div>
        <h1 className="mt-5 text-4xl font-black tracking-tight text-white md:text-5xl">
          How the AI Valuator Works
        </h1>
        <p className="mt-3 max-w-2xl text-lg text-gray-400">
          EstateMind analyses market data, property photos, description quality, and
          comparable listings to give you an accurate price range — and explains every factor that drives it.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { icon:'🏠', title:'Property Profiling',      desc:'Type, size, condition, and features are analysed to build a complete picture of your property.' },
          { icon:'📍', title:'Neighbourhood Intelligence', desc:'Prices are calibrated at the neighbourhood level across all 278 areas in Tunisia using real market data.' },
          { icon:'🧠', title:'AI Estimation',           desc:'Our AI model delivers estimates with up to 94% accuracy. Listing descriptions are also analysed to refine the result.' },
          { icon:'📊', title:'Confidence Score',        desc:'A 0–100 score reflects how much data backs the estimate — photos, description, and comparable listings all count.' },
        ].map(s => (
          <div key={s.title} className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <span className="text-2xl">{s.icon}</span>
            <p className="mt-2 font-bold text-white">{s.title}</p>
            <p className="mt-1 text-sm text-gray-400">{s.desc}</p>
          </div>
        ))}
      </div>

      {/* Model accuracy */}
      <Card title="Valuation Accuracy by Property Type" icon={Activity}>
        {[
          { t:'Land',      r2:94, c:'#22c55e' },
          { t:'House',     r2:72, c:'#FF6B35' },
          { t:'Apartment', r2:64, c:'#FF6B35' },
        ].map(({ t, r2, c }) => (
          <div key={t} className="mb-3 flex items-center gap-3">
            <span className="w-36 text-sm text-gray-300">{t}</span>
            <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
              <div className="h-full rounded-full" style={{ width:`${r2}%`, backgroundColor:c }} />
            </div>
            <span className="text-sm font-bold text-white">{r2}% accuracy</span>
          </div>
        ))}
      </Card>

      {/* Location coverage */}
      <Card title="Coverage — 24 Wilayas · 278 Delegations" icon={MapPin}>
        <div className="flex flex-wrap gap-1.5">
          {STATIC_REGIONS.map(r => (
            <span key={r.id} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-gray-300">
              {r.governorate}
            </span>
          ))}
        </div>
      </Card>

      {/* Locked preview */}
      <div className="pointer-events-none select-none rounded-2xl border border-[#FF6B35]/30 bg-[#FF6B35]/5 p-6 opacity-50">
        <p className="text-xs uppercase tracking-widest text-[#FFB38F] mb-3">Live Result Preview — Upgrade to Unlock</p>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-4xl font-black text-white">395,600 TND</p>
            <p className="text-sm text-gray-400">Range: 339,616 – 451,584 TND · ≈ 3,297 TND/m²</p>
          </div>
          <div className="text-center">
            <p className="text-4xl font-black text-white">63</p>
            <p className="text-sm text-gray-400">Low Confidence</p>
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <Badge label="Heuristic Mode"  cls="bg-blue-500/20 text-blue-300 border-blue-500/30" />
          <Badge label="4 Comparables"   cls="bg-purple-500/20 text-purple-300 border-purple-500/30" />
          <Badge label="Price Breakdown"  cls="bg-teal-500/20 text-teal-300 border-teal-500/30" />
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page root
export default function ValuatePage() {
  const { user, upgradePlan, trackActivity } = useAuth();

  useEffect(() => {
    trackActivity?.('valuation', 'valuate_page_view', { plan: user?.plan || 'free' });
  }, [trackActivity, user?.plan]);

  const [upgradeError, setUpgradeError] = useState('');
  const [upgrading, setUpgrading] = useState(false);

  const handleUpgrade = async () => {
    setUpgradeError(''); setUpgrading(true);
    try {
      await trackActivity?.('cta_click', 'valuate_upgrade_click', { page: 'valuate', target_plan: 'pro' });
      await upgradePlan('pro');
    } catch (err) {
      const msg = err?.response?.data?.error || err?.message || 'Upgrade failed. Please try again.';
      setUpgradeError(msg);
    } finally {
      setUpgrading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#111827] to-[#0B0F19] px-4 pt-24 pb-20 text-white overflow-x-hidden">
      <section className="mx-auto max-w-5xl">
        {upgradeError && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <AlertCircle size={15} className="flex-shrink-0" />{upgradeError}
          </div>
        )}
        <FeatureGate
          user={user}
          requiredPlan="pro"
          featureName="Valuate"
          informational={<InformationalMode />}
          onUpgrade={handleUpgrade}
          upgradeDescription={
            upgrading
              ? 'Activating your Pro plan…'
              : 'Pro unlocks the full AI valuation — live predictions, price breakdown, comparable listings, photo analysis, and history.'
          }
        >
          <FunctionalMode />
        </FeatureGate>
      </section>
    </main>
  );
}
