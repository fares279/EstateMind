import React, { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { getClimateRiskMap, getMapDemandHeat, getMapOpportunities, getMapPriceHeat } from '../../services/api';

const DEFAULT_CENTER = [34.0, 9.2];
const DEFAULT_ZOOM   = 6;
const TUNISIA_BOUNDS = L.latLngBounds([30.0, 7.2], [37.8, 11.9]);

// Governorate centers with population and coastal flag
const GOV_POINTS = [
  { name: 'Tunis',        lat: 36.8065, lng: 10.1815, pop: 693000, coastal: true  },
  { name: 'Ariana',       lat: 36.8625, lng: 10.1956, pop: 544000, coastal: true  },
  { name: 'Ben Arous',    lat: 36.7453, lng: 10.2347, pop: 714000, coastal: true  },
  { name: 'La Manouba',   lat: 36.8099, lng: 10.0976, pop: 414000, coastal: false },
  { name: 'Nabeul',       lat: 36.4561, lng: 10.7376, pop: 869000, coastal: true  },
  { name: 'Zaghouan',     lat: 36.4012, lng: 10.1429, pop: 181000, coastal: false },
  { name: 'Bizerte',      lat: 37.2746, lng:  9.8739, pop: 589000, coastal: true  },
  { name: 'Béja',         lat: 36.7326, lng:  9.1817, pop: 310000, coastal: false },
  { name: 'Jendouba',     lat: 36.5011, lng:  8.7757, pop: 427000, coastal: false },
  { name: 'Le Kef',       lat: 36.1822, lng:  8.7149, pop: 259000, coastal: false },
  { name: 'Siliana',      lat: 36.0851, lng:  9.3708, pop: 240000, coastal: false },
  { name: 'Sousse',       lat: 35.8245, lng: 10.6346, pop: 723000, coastal: true  },
  { name: 'Monastir',     lat: 35.7643, lng: 10.8113, pop: 553000, coastal: true  },
  { name: 'Mahdia',       lat: 35.5046, lng: 11.0622, pop: 429000, coastal: true  },
  { name: 'Kairouan',     lat: 35.6773, lng: 10.1008, pop: 628000, coastal: false },
  { name: 'Kasserine',    lat: 35.1677, lng:  8.8311, pop: 469000, coastal: false },
  { name: 'Sidi Bouzid',  lat: 35.0382, lng:  9.4858, pop: 449000, coastal: false },
  { name: 'Sfax',         lat: 34.7406, lng: 10.7603, pop: 993000, coastal: true  },
  { name: 'Gafsa',        lat: 34.4234, lng:  8.7802, pop: 377000, coastal: false },
  { name: 'Tozeur',       lat: 33.9197, lng:  8.1335, pop: 119000, coastal: false },
  { name: 'Kébili',       lat: 33.7045, lng:  8.9687, pop: 167000, coastal: false },
  { name: 'Gabès',        lat: 33.8846, lng: 10.0982, pop: 374000, coastal: true  },
  { name: 'Médenine',     lat: 33.3542, lng: 10.5052, pop: 610000, coastal: true  },
  { name: 'Tataouine',    lat: 32.9211, lng: 10.4514, pop: 166000, coastal: false },
];

/* ─ Color scales ─────────────────────────────────────────────────────────── */
function priceColor(price) {
  if (!price) return { fill: '#94a3b8', alpha: 0.25, radius: 28000 };
  if (price < 800)  return { fill: '#22d3ee', alpha: 0.52, radius: 32000 };
  if (price < 1400) return { fill: '#4ade80', alpha: 0.55, radius: 33000 };
  if (price < 2000) return { fill: '#facc15', alpha: 0.58, radius: 34000 };
  if (price < 3000) return { fill: '#fb923c', alpha: 0.62, radius: 35000 };
  if (price < 4500) return { fill: '#f87171', alpha: 0.65, radius: 36000 };
  return             { fill: '#dc2626', alpha: 0.70, radius: 38000 };
}

function demandColor(intensity) {
  const v = Number(intensity) || 0;
  if (v < 0.15) return { fill: '#3b82f6', alpha: 0.45, radius: 28000 };
  if (v < 0.30) return { fill: '#8b5cf6', alpha: 0.50, radius: 31000 };
  if (v < 0.50) return { fill: '#ec4899', alpha: 0.55, radius: 33000 };
  if (v < 0.70) return { fill: '#f97316', alpha: 0.60, radius: 35000 };
  return         { fill: '#dc2626', alpha: 0.68, radius: 38000 };
}

function opportunityColor(score) {
  const s = Number(score) || 0;
  if (s >= 80) return { fill: '#16a34a', alpha: 0.68, radius: 36000 };
  if (s >= 65) return { fill: '#65a30d', alpha: 0.60, radius: 33000 };
  if (s >= 50) return { fill: '#d97706', alpha: 0.58, radius: 31000 };
  if (s >= 35) return { fill: '#ea580c', alpha: 0.55, radius: 29000 };
  return        { fill: '#dc2626', alpha: 0.50, radius: 27000 };
}

function climateColor(cat) {
  const c = (cat || '').toLowerCase();
  if (c === 'low')                             return { fill: '#4ade80', alpha: 0.52, radius: 34000 };
  if (c === 'moderate' || c === 'medium')      return { fill: '#facc15', alpha: 0.58, radius: 35000 };
  if (c === 'high')                            return { fill: '#fb923c', alpha: 0.62, radius: 36000 };
  if (c.includes('very') || c === 'extreme')   return { fill: '#dc2626', alpha: 0.70, radius: 38000 };
  return                                        { fill: '#94a3b8', alpha: 0.35, radius: 28000 };
}

/* ─ Legend definitions ────────────────────────────────────────────────────── */
const LEGENDS = {
  price: {
    title: 'Price per m²',
    items: [
      { color: '#22d3ee', label: '< 800 TND/m²' },
      { color: '#4ade80', label: '800 – 1,400' },
      { color: '#facc15', label: '1,400 – 2,000' },
      { color: '#fb923c', label: '2,000 – 3,000' },
      { color: '#f87171', label: '3,000 – 4,500' },
      { color: '#dc2626', label: '> 4,500' },
    ],
  },
  demand: {
    title: 'Demand Pressure',
    items: [
      { color: '#3b82f6', label: 'Very Low' },
      { color: '#8b5cf6', label: 'Low' },
      { color: '#ec4899', label: 'Moderate' },
      { color: '#f97316', label: 'High' },
      { color: '#dc2626', label: 'Very High' },
    ],
  },
  opportunities: {
    title: 'Investment Score',
    items: [
      { color: '#16a34a', label: 'Excellent (80+)' },
      { color: '#65a30d', label: 'Good (65–80)' },
      { color: '#d97706', label: 'Fair (50–65)' },
      { color: '#ea580c', label: 'Weak (35–50)' },
      { color: '#dc2626', label: 'Poor (<35)' },
    ],
  },
  climate: {
    title: 'Climate Risk Level',
    items: [
      { color: '#4ade80', label: 'Low' },
      { color: '#facc15', label: 'Moderate' },
      { color: '#fb923c', label: 'High' },
      { color: '#dc2626', label: 'Very High / Extreme' },
    ],
  },
};

/* ─ Rich tooltip HTML per layer ──────────────────────────────────────────── */
function priceTip(item) {
  const p    = item.properties || item;
  const avg  = p.avg_price_tnd || p.avg_price || 0;
  const min  = p.min_price_tnd || p.price_min || 0;
  const max  = p.max_price_tnd || p.price_max || 0;
  const trend = p.annual_trend_pct ?? p.trend_pct ?? null;
  const tArrow = trend == null ? '' : trend >= 0 ? `<span style="color:#22c55e">▲ +${trend.toFixed(1)}%</span>` : `<span style="color:#ef4444">▼ ${trend.toFixed(1)}%</span>`;
  return `
    <div style="font-family:system-ui;min-width:170px">
      <div style="font-weight:700;font-size:13px;margin-bottom:4px">${p.delegation_name || p.governorate || 'Zone'}</div>
      ${p.governorate ? `<div style="font-size:10px;color:#6b7280;margin-bottom:6px">${p.governorate}</div>` : ''}
      <div style="display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:11px">
        <span style="color:#6b7280">Avg price</span><span style="font-weight:600">${avg.toLocaleString('fr-TN')} TND/m²</span>
        ${min ? `<span style="color:#6b7280">Range</span><span>${min.toLocaleString('fr-TN')} – ${max.toLocaleString('fr-TN')}</span>` : ''}
        ${tArrow ? `<span style="color:#6b7280">12M trend</span><span>${tArrow}</span>` : ''}
      </div>
    </div>`;
}

function demandTip(item) {
  const p = item.properties || item;
  const intensity = Number(p.intensity || 0);
  const label = intensity < 0.3 ? 'Low' : intensity < 0.6 ? 'Moderate' : 'High';
  return `
    <div style="font-family:system-ui;min-width:160px">
      <div style="font-weight:700;font-size:13px;margin-bottom:4px">${p.delegation_name || 'Zone'}</div>
      ${p.governorate ? `<div style="font-size:10px;color:#6b7280;margin-bottom:6px">${p.governorate}</div>` : ''}
      <div style="display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:11px">
        <span style="color:#6b7280">Demand</span><span style="font-weight:600">${label}</span>
        <span style="color:#6b7280">Supply pressure</span><span>${p.supply_pressure || 'N/A'}</span>
        <span style="color:#6b7280">Intensity</span><span>${(intensity * 100).toFixed(0)}%</span>
      </div>
    </div>`;
}

function opportunityTip(item) {
  const score = Number(item.opportunity_score || 0);
  const grade = score >= 80 ? 'A' : score >= 65 ? 'B' : score >= 50 ? 'C' : score >= 35 ? 'D' : 'F';
  const gradeColor = score >= 80 ? '#16a34a' : score >= 65 ? '#65a30d' : score >= 50 ? '#d97706' : '#dc2626';
  return `
    <div style="font-family:system-ui;min-width:170px">
      <div style="font-weight:700;font-size:13px;margin-bottom:4px">${item.delegation_name || 'Zone'}</div>
      ${item.governorate ? `<div style="font-size:10px;color:#6b7280;margin-bottom:6px">${item.governorate}</div>` : ''}
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <span style="font-size:22px;font-weight:900;color:${gradeColor}">${grade}</span>
        <div>
          <div style="font-size:11px;color:#6b7280">Score</div>
          <div style="font-weight:700;font-size:15px">${score.toFixed(0)}/100</div>
        </div>
      </div>
      <div style="font-size:10px;color:#6b7280">${item.recommendation || 'See /invest for full analysis'}</div>
    </div>`;
}

function climateTip(item) {
  const riskColor = (r) => {
    const c = (r || '').toLowerCase();
    return c === 'low' ? '#22c55e' : c === 'moderate' || c === 'medium' ? '#eab308' : c === 'high' ? '#f97316' : '#dc2626';
  };
  return `
    <div style="font-family:system-ui;min-width:190px">
      <div style="font-weight:700;font-size:13px;margin-bottom:4px">${item.governorate || 'Zone'}</div>
      <div style="margin-bottom:6px">
        <span style="display:inline-block;background:${riskColor(item.risk_category)};color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px">${item.risk_category || 'Unknown'} Risk</span>
      </div>
      <div style="display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:11px">
        ${item.flood_risk      ? `<span style="color:#6b7280">Flood</span><span style="font-weight:600;color:${riskColor(item.flood_risk)}">${item.flood_risk}</span>` : ''}
        ${item.heat_risk       ? `<span style="color:#6b7280">Heat</span><span style="font-weight:600;color:${riskColor(item.heat_risk)}">${item.heat_risk}</span>` : ''}
        ${item.drought_risk    ? `<span style="color:#6b7280">Drought</span><span style="font-weight:600;color:${riskColor(item.drought_risk)}">${item.drought_risk}</span>` : ''}
        ${item.earthquake_risk ? `<span style="color:#6b7280">Seismic</span><span style="font-weight:600;color:${riskColor(item.earthquake_risk)}">${item.earthquake_risk}</span>` : ''}
        ${item.sea_level_rise_m != null ? `<span style="color:#6b7280">Sea rise</span><span>+${item.sea_level_rise_m}m by 2050</span>` : ''}
        ${item.rain_mm         ? `<span style="color:#6b7280">Annual rain</span><span>${item.rain_mm} mm</span>` : ''}
        ${item.hot_days        ? `<span style="color:#6b7280">Hot days/yr</span><span>${item.hot_days}</span>` : ''}
      </div>
    </div>`;
}

/* ─ Pin icons ─────────────────────────────────────────────────────────────── */
function pinIcon(isSelected) {
  const s = isSelected ? 16 : 9;
  return L.divIcon({
    className: '',
    html: `<div style="width:${s}px;height:${s}px;background:${isSelected ? '#FF6B35' : '#fb923c'};border:2px solid ${isSelected ? '#fff' : 'rgba(255,255,255,0.7)'};border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 2px 8px rgba(255,107,53,0.5);transition:all .15s"></div>`,
    iconSize: [0, 0], iconAnchor: [0, 0],
  });
}

function govLabel(name, isCoastal) {
  return L.divIcon({
    className: '',
    html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);pointer-events:none">
      <div style="width:4px;height:4px;background:${isCoastal ? '#0ea5e9' : '#6b7280'};border:1px solid rgba(255,255,255,0.8);border-radius:50%"></div>
      <div style="background:rgba(255,255,255,0.93);color:#374151;font-size:8.5px;font-weight:700;padding:1px 5px;border-radius:3px;white-space:nowrap;margin-top:1px;border:1px solid rgba(107,114,128,0.2);letter-spacing:0.02em">${name}</div>
    </div>`,
    iconSize: [0, 0], iconAnchor: [0, 0],
  });
}

/* ──────────────────────────────────────────────────────────────────────────
   Main component
─────────────────────────────────────────────────────────────────────────── */
export default function ExploreMap({
  selectedProperty,
  properties = [],
  onPropertySelect,
  mapLayer,
  onLayerChange,
  filters,
  onFilterChange,
  governorateOptions = [],
  delegationOptions  = [],
  loading,
}) {
  const mapRef        = useRef(null);
  const instanceRef   = useRef(null);
  const markerLayer   = useRef(null);
  const heatLayer     = useRef(null);
  const govLabelsLayer= useRef(null);

  const [hoverInfo,  setHoverInfo]  = useState(null);
  const [layerStats, setLayerStats] = useState(null);
  const [dataLoading, setDataLoading] = useState(false);

  /* ── Init Leaflet once ────────────────────────────────────────────────── */
  useEffect(() => {
    if (!mapRef.current || instanceRef.current) return undefined;

    const map = L.map(mapRef.current, {
      center:    DEFAULT_CENTER,
      zoom:      DEFAULT_ZOOM,
      maxBounds: TUNISIA_BOUNDS.pad(0.2),
      minZoom:   5,
      maxZoom:   18,
      zoomControl: false,
    });

    // Dark satellite-style basemap option + clean light fallback
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap © CARTO',
      subdomains: 'abcd',
      maxZoom: 20,
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    govLabelsLayer.current = L.layerGroup().addTo(map);
    markerLayer.current    = L.layerGroup().addTo(map);
    heatLayer.current      = L.layerGroup().addTo(map);

    // Governorate labels (always visible)
    GOV_POINTS.forEach((g) => {
      L.marker([g.lat, g.lng], {
        icon: govLabel(g.name, g.coastal),
        interactive: false,
      }).addTo(govLabelsLayer.current);
    });

    instanceRef.current = map;
    return () => {
      map.remove();
      instanceRef.current    = null;
      markerLayer.current    = null;
      heatLayer.current      = null;
      govLabelsLayer.current = null;
    };
  }, []);

  /* ── Property pins ────────────────────────────────────────────────────── */
  useEffect(() => {
    const map = instanceRef.current;
    const ml  = markerLayer.current;
    if (!map || !ml) return;
    ml.clearLayers();

    properties.forEach((p) => {
      const lat = Number(p.lat);
      const lng = Number(p.lng);
      if (!lat || !lng) return;
      const isSelected = selectedProperty?.id === p.id;
      const marker = L.marker([lat, lng], {
        icon: pinIcon(isSelected),
        zIndexOffset: isSelected ? 1000 : 0,
      });
      marker.bindTooltip(
        `<b>${p.title || 'Property'}</b><br/>${(p.price || 0).toLocaleString('fr-TN')} TND — ${p.location || ''}`,
        { direction: 'top', className: 'em-tip' }
      );
      marker.on('click', () => onPropertySelect?.(p));
      marker.addTo(ml);
    });

    if (selectedProperty?.lat && selectedProperty?.lng) {
      map.setView(
        [selectedProperty.lat, selectedProperty.lng],
        Math.max(instanceRef.current?.getZoom() || 9, 12)
      );
    }
  }, [properties, selectedProperty, onPropertySelect]);

  /* ── Overlay layers ───────────────────────────────────────────────────── */
  useEffect(() => {
    let cancelled = false;
    const hl = heatLayer.current;
    if (!hl) return;
    hl.clearLayers();
    setHoverInfo(null);
    setLayerStats(null);
    setDataLoading(true);

    const addHeatCircle = (lat, lon, colorInfo, tooltip, rawData) => {
      const { fill, alpha, radius } = colorInfo;
      const circle = L.circle([lat, lon], {
        radius,
        color:       fill,
        fillColor:   fill,
        fillOpacity: alpha,
        weight:      0,
        className:   'em-heat-circle',
      });
      circle.bindTooltip(tooltip, {
        direction: 'top',
        className: 'em-tip',
        sticky: true,
      });
      circle.on('mouseover', () => setHoverInfo(rawData));
      circle.on('mouseout',  () => setHoverInfo(null));
      circle.addTo(hl);

      // Outer glow ring
      L.circle([lat, lon], {
        radius:      radius * 1.5,
        color:       fill,
        fillColor:   fill,
        fillOpacity: alpha * 0.18,
        weight:      0,
      }).addTo(hl);
    };

    const draw = async () => {
      try {
        /* ── Climate ── */
        if (mapLayer === 'climate') {
          const { data } = await getClimateRiskMap();
          if (cancelled) return;
          const items = Array.isArray(data) ? data : [];
          const stats = { low: 0, moderate: 0, high: 0, vhigh: 0 };
          items.forEach((item) => {
            const lat = Number(item.lat || item.region_lat || 0);
            const lon = Number(item.lon || item.region_lon || 0);
            if (!lat || !lon) return;
            const cat = (item.risk_category || '').toLowerCase();
            if (cat === 'low') stats.low++;
            else if (cat === 'moderate' || cat === 'medium') stats.moderate++;
            else if (cat === 'high') stats.high++;
            else stats.vhigh++;
            addHeatCircle(lat, lon, climateColor(item.risk_category), climateTip(item), { type: 'climate', ...item });
          });
          setLayerStats({ type: 'climate', ...stats, total: items.length });
          return;
        }

        /* ── Opportunities ── */
        if (mapLayer === 'opportunities') {
          const { data } = await getMapOpportunities({ min_score: 0 });
          if (cancelled) return;
          const items = Array.isArray(data) ? data : [];
          let avgScore = 0;
          let excellent = 0;
          items.forEach((item) => {
            const lat = Number(item.centroid_lat || 0);
            const lon = Number(item.centroid_lon || 0);
            if (!lat || !lon) return;
            const score = Number(item.opportunity_score || 0);
            avgScore += score;
            if (score >= 80) excellent++;
            addHeatCircle(lat, lon, opportunityColor(score), opportunityTip(item), { type: 'opportunity', ...item });
          });
          setLayerStats({ type: 'opportunity', total: items.length, avgScore: items.length ? (avgScore / items.length).toFixed(1) : 0, excellent });
          return;
        }

        /* ── Price / Demand ── */
        const fetchFn = mapLayer === 'demand' ? getMapDemandHeat : getMapPriceHeat;
        const { data: payload } = await fetchFn();
        if (cancelled) return;
        const features = payload?.features || [];

        let priceSum = 0; let priceCount = 0; let maxPrice = 0;
        features.forEach((feature) => {
          const coords = feature?.geometry?.coordinates || [];
          const p      = feature.properties || {};
          const lon    = Number(coords[0] || 0);
          const lat    = Number(coords[1] || 0);
          if (!lat || !lon) return;

          const intensity = Number(p.intensity || 0);
          const avg       = Number(p.avg_price_tnd || 0);
          if (avg) { priceSum += avg; priceCount++; if (avg > maxPrice) maxPrice = avg; }

          const colorInfo = mapLayer === 'demand' ? demandColor(intensity) : priceColor(avg);
          const tooltip   = mapLayer === 'demand' ? demandTip({ properties: p }) : priceTip({ properties: p });
          const rawData   = { type: mapLayer, ...p };
          addHeatCircle(lat, lon, colorInfo, tooltip, rawData);
        });

        if (mapLayer === 'price') {
          setLayerStats({ type: 'price', total: priceCount, avg: priceCount ? Math.round(priceSum / priceCount) : 0, max: Math.round(maxPrice) });
        } else {
          setLayerStats({ type: 'demand', total: features.length });
        }
      } catch {
        hl.clearLayers();
      } finally {
        if (!cancelled) setDataLoading(false);
      }
    };

    draw();
    return () => { cancelled = true; };
  }, [mapLayer]);

  const mappedCount = properties.filter((p) => p.lat && p.lng).length;
  const legend      = LEGENDS[mapLayer] || LEGENDS.price;

  /* ── Stats bar content ────────────────────────────────────────────────── */
  const StatsBar = useCallback(() => {
    if (!layerStats) return null;
    if (layerStats.type === 'price')
      return (
        <>
          <StatChip label="Delegations" value={layerStats.total} />
          <StatChip label="Nat. avg" value={`${(layerStats.avg || 0).toLocaleString('fr-TN')} TND/m²`} />
          <StatChip label="Highest" value={`${(layerStats.max || 0).toLocaleString('fr-TN')} TND/m²`} />
        </>
      );
    if (layerStats.type === 'climate')
      return (
        <>
          <StatChip label="Low risk" value={layerStats.low} color="#22c55e" />
          <StatChip label="Moderate" value={layerStats.moderate} color="#eab308" />
          <StatChip label="High" value={layerStats.high} color="#f97316" />
          <StatChip label="Very High" value={layerStats.vhigh} color="#dc2626" />
        </>
      );
    if (layerStats.type === 'opportunity')
      return (
        <>
          <StatChip label="Zones" value={layerStats.total} />
          <StatChip label="Avg score" value={layerStats.avgScore} />
          <StatChip label="Excellent" value={layerStats.excellent} color="#16a34a" />
        </>
      );
    return <StatChip label="Zones" value={layerStats.total} />;
  }, [layerStats]);

  return (
    <div className="w-full rounded-xl overflow-hidden border border-slate-200/20 shadow-2xl shadow-black/30 relative"
      style={{ height: 580 }}>

      {/* ── Layer tab bar (top-left) ─────────────────────────────────────── */}
      <div className="absolute top-3 left-3 z-[1001] flex flex-col gap-2">
        <div className="flex items-center gap-1.5 bg-white/95 border border-gray-200 rounded-xl p-1 shadow-md backdrop-blur-sm">
          {[
            { id: 'price',         label: '💰 Price',       active: '#FF6B35' },
            { id: 'demand',        label: '📊 Demand',      active: '#8b5cf6' },
            { id: 'opportunities', label: '🎯 Invest',      active: '#16a34a' },
            { id: 'climate',       label: '🌊 Climate',     active: '#0ea5e9' },
          ].map(({ id, label, active }) => (
            <button
              key={id}
              onClick={() => onLayerChange(id)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap"
              style={mapLayer === id
                ? { background: active, color: '#fff', boxShadow: `0 2px 8px ${active}55` }
                : { color: '#6b7280' }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Filters (top-right) ──────────────────────────────────────────── */}
      <div className="absolute top-3 right-3 z-[1001] flex gap-2">
        <select
          value={filters?.governorate || ''}
          onChange={(e) => onFilterChange?.({ governorate: e.target.value })}
          className="px-3 py-2 rounded-lg bg-white/95 text-gray-700 border border-gray-200 text-xs shadow-md backdrop-blur-sm focus:outline-none focus:border-orange-400 min-w-[140px]"
        >
          <option value="">All Governorates</option>
          {governorateOptions.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
        <select
          value={filters?.delegation || ''}
          onChange={(e) => onFilterChange?.({ delegation: e.target.value })}
          className="px-3 py-2 rounded-lg bg-white/95 text-gray-700 border border-gray-200 text-xs shadow-md backdrop-blur-sm focus:outline-none focus:border-orange-400 min-w-[140px]"
        >
          <option value="">All Delegations</option>
          {delegationOptions.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      {/* ── Map canvas ──────────────────────────────────────────────────── */}
      <div ref={mapRef} className="w-full h-full" />

      {/* ── Loading overlay ─────────────────────────────────────────────── */}
      {dataLoading && (
        <div className="absolute inset-0 bg-black/10 z-[1002] flex items-center justify-center pointer-events-none">
          <div className="bg-white/95 rounded-xl px-5 py-3 shadow-xl border border-gray-100 text-sm font-semibold text-gray-600 flex items-center gap-2">
            <span className="w-4 h-4 border-2 border-orange-400 border-t-transparent rounded-full animate-spin inline-block" />
            Loading map data…
          </div>
        </div>
      )}

      {/* ── Info hover panel (bottom-right) ─────────────────────────────── */}
      {hoverInfo && (
        <div className="absolute bottom-20 right-3 z-[1001] bg-white/97 border border-gray-200 rounded-xl shadow-xl p-3 max-w-[220px] text-[11px] text-gray-700"
          style={{ backdropFilter: 'blur(12px)', animation: 'emFadeIn .15s ease' }}>
          <HoverPanel info={hoverInfo} />
        </div>
      )}

      {/* ── Legend bar (bottom-left) ─────────────────────────────────────── */}
      <div className="absolute bottom-3 left-3 z-[1001] flex flex-col gap-1.5">
        <div className="bg-white/95 border border-gray-200 rounded-xl px-3 py-2.5 shadow-md backdrop-blur-sm">
          <div className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1.5">{legend.title}</div>
          <div className="flex items-center gap-2 flex-wrap">
            {legend.items.map(({ color, label }) => (
              <span key={label} className="flex items-center gap-1">
                <span style={{ background: color }} className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0" />
                <span className="text-[10px] text-gray-600 whitespace-nowrap">{label}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Stats bar */}
        <div className="bg-white/95 border border-gray-200 rounded-xl px-3 py-2 shadow-md backdrop-blur-sm flex items-center gap-3">
          <StatsBar />
          {loading && <span className="text-[10px] text-gray-400 ml-1">· loading…</span>}
        </div>
      </div>

      {/* ── Property count badge ─────────────────────────────────────────── */}
      {properties.length > 0 && (
        <div className="absolute bottom-3 right-3 z-[1001] bg-white/95 border border-gray-200 rounded-xl px-3 py-2 text-xs text-gray-500 shadow-md backdrop-blur-sm">
          <span className="text-[#FF6B35] font-bold">{mappedCount}</span>/{properties.length} listed
        </div>
      )}

      <style>{`
        .em-tip {
          background: rgba(255,255,255,0.97) !important;
          border: 1px solid rgba(203,213,225,0.9) !important;
          color: #1e293b !important;
          border-radius: 10px !important;
          padding: 8px 12px !important;
          box-shadow: 0 6px 20px rgba(0,0,0,0.14) !important;
          max-width: 240px !important;
          pointer-events: none !important;
        }
        .leaflet-tooltip-top.em-tip::before { border-top-color: rgba(203,213,225,0.9) !important; }
        .em-heat-circle { transition: fill-opacity .2s; }
        .em-heat-circle:hover { fill-opacity: 0.85 !important; }
        @keyframes emFadeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
      `}</style>
    </div>
  );
}

/* ── Sub-components ───────────────────────────────────────────────────────── */
function StatChip({ label, value, color }) {
  return (
    <div className="flex flex-col items-center leading-tight">
      <span className="text-[10px] text-gray-400">{label}</span>
      <span className="text-xs font-bold" style={{ color: color || '#374151' }}>{value}</span>
    </div>
  );
}

function HoverPanel({ info }) {
  if (!info) return null;
  if (info.type === 'climate') {
    const rc = (r) => {
      const c = (r || '').toLowerCase();
      return c === 'low' ? '#22c55e' : c === 'moderate' || c === 'medium' ? '#eab308' : c === 'high' ? '#f97316' : '#dc2626';
    };
    return (
      <div>
        <div className="font-bold text-[12px] text-gray-800 mb-1">{info.governorate}</div>
        <div className="mb-2">
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-white" style={{ background: rc(info.risk_category) }}>
            {info.risk_category || 'Unknown'} Risk
          </span>
        </div>
        {info.flood_risk      && <Row k="Flood"     v={info.flood_risk}      c={rc(info.flood_risk)} />}
        {info.heat_risk       && <Row k="Heat"      v={info.heat_risk}       c={rc(info.heat_risk)} />}
        {info.drought_risk    && <Row k="Drought"   v={info.drought_risk}    c={rc(info.drought_risk)} />}
        {info.earthquake_risk && <Row k="Seismic"   v={info.earthquake_risk} c={rc(info.earthquake_risk)} />}
        {info.sea_level_rise_m != null && <Row k="Sea rise 2050" v={`+${info.sea_level_rise_m}m`} />}
        {info.hot_days        && <Row k="Hot days/yr" v={info.hot_days} />}
        {info.rain_mm         && <Row k="Annual rain"  v={`${info.rain_mm} mm`} />}
      </div>
    );
  }
  if (info.type === 'opportunity') {
    const s = Number(info.opportunity_score || 0);
    const grade = s >= 80 ? 'A' : s >= 65 ? 'B' : s >= 50 ? 'C' : s >= 35 ? 'D' : 'F';
    const gc = s >= 80 ? '#16a34a' : s >= 65 ? '#65a30d' : s >= 50 ? '#d97706' : '#dc2626';
    return (
      <div>
        <div className="font-bold text-[12px] text-gray-800 mb-1">{info.delegation_name}</div>
        {info.governorate && <div className="text-[10px] text-gray-400 mb-2">{info.governorate}</div>}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-2xl font-black" style={{ color: gc }}>{grade}</span>
          <div>
            <div className="text-[10px] text-gray-400">Score</div>
            <div className="font-bold text-sm text-gray-800">{s.toFixed(0)}/100</div>
          </div>
        </div>
        {info.recommendation && <div className="text-[10px] text-gray-500">{info.recommendation}</div>}
      </div>
    );
  }
  if (info.type === 'price') {
    return (
      <div>
        <div className="font-bold text-[12px] text-gray-800 mb-1">{info.delegation_name}</div>
        {info.governorate && <div className="text-[10px] text-gray-400 mb-2">{info.governorate}</div>}
        <Row k="Avg price"  v={`${(Number(info.avg_price_tnd || 0)).toLocaleString('fr-TN')} TND/m²`} />
        {info.min_price_tnd && <Row k="Min"  v={`${(Number(info.min_price_tnd)).toLocaleString('fr-TN')} TND/m²`} />}
        {info.max_price_tnd && <Row k="Max"  v={`${(Number(info.max_price_tnd)).toLocaleString('fr-TN')} TND/m²`} />}
        {info.annual_trend_pct != null && (
          <Row k="12M trend" v={`${info.annual_trend_pct >= 0 ? '+' : ''}${Number(info.annual_trend_pct).toFixed(1)}%`}
            c={info.annual_trend_pct >= 0 ? '#22c55e' : '#ef4444'} />
        )}
      </div>
    );
  }
  if (info.type === 'demand') {
    return (
      <div>
        <div className="font-bold text-[12px] text-gray-800 mb-1">{info.delegation_name || 'Zone'}</div>
        {info.governorate && <div className="text-[10px] text-gray-400 mb-1">{info.governorate}</div>}
        <Row k="Supply pressure" v={info.supply_pressure || 'N/A'} />
        {info.intensity != null && <Row k="Intensity" v={`${(Number(info.intensity) * 100).toFixed(0)}%`} />}
      </div>
    );
  }
  return null;
}

function Row({ k, v, c }) {
  return (
    <div className="flex justify-between gap-3 py-0.5">
      <span className="text-gray-400">{k}</span>
      <span className="font-semibold" style={c ? { color: c } : {}}>{v}</span>
    </div>
  );
}
