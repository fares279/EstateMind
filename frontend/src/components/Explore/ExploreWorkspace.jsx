import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import ExploreMap from './ExploreMap';
import PropertyList from './PropertyList';
import PropertyDetailModal from './PropertyDetailModal';
import { getMapDelegations, getMapListings } from '../../services/api';

const TN_LAT_MIN = 30.0, TN_LAT_MAX = 37.5, TN_LNG_MIN = 7.5, TN_LNG_MAX = 11.7;

const PROP_TYPE_LABELS = {
  apartment: 'Apartment', house: 'House', villa: 'Villa',
  land: 'Land Plot', commercial: 'Commercial Space',
};

// Extract English feature keywords from a raw French/Arabic title
function extractFeatures(rawTitle) {
  const t = (rawTitle || '').toLowerCase();
  const f = [];
  // Furnished states (check semi first)
  if (/semi[.\s-]?meublé|semi[.\s-]?meuble|semi[.\s-]?furnished/i.test(t)) f.push('Semi-Furnished');
  else if (/non[.\s-]?meublé|non[.\s-]?meuble|unfurnished/i.test(t))        f.push('Unfurnished');
  else if (/meublé|meuble|meubles|furnished/i.test(t))                       f.push('Furnished');
  // Condition
  if (/tout[.\s-]?neuf|brand[.\s-]?new|neuf|neufs|nouvelle?\s+construction/i.test(t)) f.push('Brand New');
  if (/rénové|renove|renovated|remis à neuf/i.test(t)) f.push('Renovated');
  // Views & outdoor
  if (/vue[.\s-]?mer|sea[.\s-]?view|front[.\s-]?mer/i.test(t)) f.push('Sea View');
  if (/vue[.\s-]?montagne|mountain[.\s-]?view/i.test(t))        f.push('Mountain View');
  if (/jardin|garden/i.test(t))                                  f.push('Garden');
  if (/terrasse|terrace/i.test(t))                               f.push('Terrace');
  if (/balcon|balcony/i.test(t))                                 f.push('Balcony');
  if (/rooftop/i.test(t))                                        f.push('Rooftop');
  if (/piscine|pool/i.test(t))                                   f.push('Pool');
  // Property features
  if (/duplex/i.test(t))                                         f.push('Duplex');
  if (/penthouse/i.test(t))                                      f.push('Penthouse');
  if (/standing|luxe\b|luxueux|luxury/i.test(t))                 f.push('Luxury');
  if (/parking|garage/i.test(t))                                 f.push('Parking');
  if (/climatisé|climatise|air.?cond/i.test(t))                  f.push('A/C');
  return f;
}

// Build a clean English title from structured data + extracted features
function buildEnglishTitle(rawTitle, propertyType, rooms, area, delegationName, governorate) {
  const features = extractFeatures(rawTitle);
  const typeLabel = PROP_TYPE_LABELS[propertyType] || 'Property';
  const loc = delegationName || governorate || 'Tunisia';

  let roomPart = '';
  if (rooms > 0 && propertyType !== 'land' && propertyType !== 'commercial') {
    roomPart = rooms === 1 ? 'Studio ' : `${rooms}-Room `;
  }

  // Include area so listings in the same delegation are always distinguishable
  const areaSuffix = area > 0 ? ` · ${area}m²` : '';
  const featPart   = features.length > 0 ? features.join(' · ') + ' ' : '';
  return `${featPart}${roomPart}${typeLabel}${areaSuffix} in ${loc}`;
}

// Price-per-m² based deal assessment (more logical than total price)
function assessDeal(price, area, propertyType) {
  if (!area || !price) {
    return price < 150000 ? 'good' : price < 400000 ? 'fair' : 'above';
  }
  const ppm2 = price / area;
  switch (propertyType) {
    case 'apartment':  return ppm2 < 1100 ? 'good' : ppm2 < 2400 ? 'fair' : 'above';
    case 'house':
    case 'villa':      return ppm2 < 900  ? 'good' : ppm2 < 1900 ? 'fair' : 'above';
    case 'land':       return ppm2 < 350  ? 'good' : ppm2 < 800  ? 'fair' : 'above';
    case 'commercial': return ppm2 < 1500 ? 'good' : ppm2 < 3000 ? 'fair' : 'above';
    default:           return ppm2 < 1000 ? 'good' : ppm2 < 2200 ? 'fair' : 'above';
  }
}

function inTunisia(lat, lng) {
  return lat >= TN_LAT_MIN && lat <= TN_LAT_MAX && lng >= TN_LNG_MIN && lng <= TN_LNG_MAX;
}

function resolveCoords(raw) {
  const propLat = Number(raw.latitude || 0);
  const propLng = Number(raw.longitude || 0);
  if (propLat && propLng && inTunisia(propLat, propLng)) return { lat: propLat, lng: propLng };

  const delLat = Number(raw.delegation_centroid_lat || 0);
  const delLng = Number(raw.delegation_centroid_lon || 0);
  if (delLat && delLng && inTunisia(delLat, delLng)) return { lat: delLat, lng: delLng };

  const regLat = Number(raw.region_lat || 0);
  const regLng = Number(raw.region_lon || 0);
  if (regLat && regLng && inTunisia(regLat, regLng)) return { lat: regLat, lng: regLng };

  return { lat: null, lng: null };
}

function normalizeProperty(raw) {
  const location = [raw.governorate, raw.delegation_name].filter(Boolean).join(', ');
  const bedrooms = Number(raw.bedrooms || 0);
  const rooms    = bedrooms > 0 ? bedrooms : Math.max(1, Math.round(Number(raw.area_sqm || 0) / 45));
  const { lat, lng } = resolveCoords(raw);
  const price  = Number(raw.price || 0);
  const area   = Number(raw.area_sqm || 0);
  const ptype  = raw.property_type || 'apartment';

  // Build clean English title from structured data + features extracted from raw title
  const title = buildEnglishTitle(raw.title, ptype, rooms, area, raw.delegation_name, raw.governorate);

  // Meaningful feature tags (from raw title extraction)
  const featureTags = extractFeatures(raw.title);
  const tags = featureTags.length > 0 ? featureTags : [PROP_TYPE_LABELS[ptype] || 'Property'];

  return {
    id:            raw.id,
    external_id:   raw.external_id,
    rawTitle:      raw.title,       // keep original for debugging / tooltip
    title,
    price,
    pricePerM2:    area > 0 ? Math.round(price / area) : null,
    type:          PROP_TYPE_LABELS[ptype] || 'Property',
    property_type: ptype,
    area,
    rooms,
    bathrooms:     Number(raw.bathrooms || 0),
    bedrooms,
    location:      location || 'Tunisia',
    lat,
    lng,
    source:        raw.source,
    governorate:   raw.governorate,
    delegationName: raw.delegation_name,
    image:         '/images/property_listing_placeholder.png',
    deal:          assessDeal(price, area, ptype),
    tags,
  };
}

export default function ExploreWorkspace() {
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [detailProperty, setDetailProperty] = useState(null);
  const [properties, setProperties] = useState([]);
  const [delegationKpis, setDelegationKpis] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mapLayer, setMapLayer] = useState('price');
  const [filters, setFilters] = useState({
    governorate: '',
    delegation: '',
    property_type: '',
    price_min: '',
    price_max: '',
  });

  const governorateOptions = useMemo(() => {
    return [...new Set(delegationKpis.map((item) => item.governorate).filter(Boolean))].sort();
  }, [delegationKpis]);

  const delegationOptions = useMemo(() => {
    return delegationKpis
      .filter((item) => !filters.governorate || item.governorate === filters.governorate)
      .map((item) => item.delegation_name)
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b));
  }, [delegationKpis, filters.governorate]);

  useEffect(() => {
    let ignore = false;

    const fetchDelegations = async () => {
      try {
        const params = filters.governorate ? { governorate: filters.governorate } : undefined;
        const { data } = await getMapDelegations(params);
        if (!ignore) {
          setDelegationKpis(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        if (!ignore) {
          setDelegationKpis([]);
        }
      }
    };

    fetchDelegations();
    return () => {
      ignore = true;
    };
  }, [filters.governorate]);

  useEffect(() => {
    let ignore = false;

    const fetchListings = async () => {
      setLoading(true);
      setError('');

      try {
        const params = {};
        if (filters.governorate) params.governorate = filters.governorate;
        if (filters.delegation) params.delegation = filters.delegation;
        if (filters.property_type) params.property_type = filters.property_type;
        if (filters.price_min !== '') params.price_min = filters.price_min;
        if (filters.price_max !== '') params.price_max = filters.price_max;

        const { data } = await getMapListings(params);
        const normalized = (data?.results || []).map(normalizeProperty);

        if (!ignore) {
          setProperties(normalized);
          setSelectedProperty((prev) => {
            if (!prev) return null;
            return normalized.find((p) => p.id === prev.id) || null;
          });
        }
      } catch (err) {
        if (!ignore) {
          setProperties([]);
          setError('Unable to load listings from backend map API.');
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    };

    fetchListings();
    return () => {
      ignore = true;
    };
  }, [filters]);

  const handleFilterChange = (patch) => {
    setFilters((prev) => {
      const next = { ...prev, ...patch };
      if (patch.governorate !== undefined && patch.governorate !== prev.governorate) {
        next.delegation = '';
      }
      return next;
    });
  };

  const handleMapPropertySelect = (property) => {
    setSelectedProperty(property);
    setDetailProperty(property);
  };

  return (
    <section className="relative bg-gradient-to-b from-black via-slate-950 to-black py-12 px-6">
      <div className="max-w-7xl mx-auto">
        {/* Workspace Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true, margin: '-100px' }}
          className="mb-12"
        >
          <div className="text-orange-500/60 font-mono text-sm tracking-widest mb-3 uppercase">
            — Workspace
          </div>
          <h2 className="text-4xl md:text-5xl font-black text-white mb-3">
            Intelligence <span className="text-[#FF6B35]">Workspace</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl">
            Browse properties with structured filters, live map synchronization, and clear decision support.
          </p>
        </motion.div>

        {/* Workspace Content Container */}
        <div className="space-y-8">
          {/* Map Section */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            viewport={{ once: true, margin: '-100px' }}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-1 h-6 bg-gradient-to-b from-[#FF6B35] to-[#FF6B35]/40 rounded" />
              <h3 className="text-lg font-black text-white">Live Market Map</h3>
              <div className="flex-1 h-px bg-gradient-to-r from-slate-700 to-transparent" />
            </div>
            <ExploreMap
              properties={properties}
              selectedProperty={selectedProperty}
              onPropertySelect={handleMapPropertySelect}
              mapLayer={mapLayer}
              onLayerChange={setMapLayer}
              filters={filters}
              onFilterChange={handleFilterChange}
              governorateOptions={governorateOptions}
              delegationOptions={delegationOptions}
              loading={loading}
            />
          </motion.div>

          {/* Properties Section */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            viewport={{ once: true, margin: '-100px' }}
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="w-1 h-6 bg-gradient-to-b from-[#FF6B35] to-[#FF6B35]/40 rounded" />
              <h3 className="text-lg font-black text-white">Discovery List</h3>
              <div className="flex-1 h-px bg-gradient-to-r from-slate-700 to-transparent" />
            </div>
            <PropertyList
              properties={properties}
              selectedProperty={selectedProperty}
              onViewDetails={setDetailProperty}
              onPropertySelect={setSelectedProperty}
              filters={filters}
              onFilterChange={handleFilterChange}
              loading={loading}
              error={error}
            />
          </motion.div>
        </div>

        {/* Bottom Accent */}
        <motion.div
          initial={{ opacity: 0, scaleX: 0 }}
          whileInView={{ opacity: 1, scaleX: 1 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          viewport={{ once: true, margin: '-100px' }}
          className="mt-16 h-1 w-full bg-gradient-to-r from-transparent via-[#FF6B35]/30 to-transparent rounded-full"
        />

        {/* Property Detail Modal */}
        <PropertyDetailModal
          property={detailProperty}
          isOpen={!!detailProperty}
          onClose={() => setDetailProperty(null)}
        />
      </div>
    </section>
  );
}
