import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, MapPin, Ruler, Bed, Bath, Check, TrendingUp, Tag } from 'lucide-react';

const DEAL_META = {
  good:  { icon: '🟢', label: 'Good Deal',    desc: 'Below typical market price',    border: 'border-emerald-500/30', bg: 'from-emerald-500/10 to-emerald-500/5' },
  fair:  { icon: '🟡', label: 'Fair Value',   desc: 'In line with market pricing',   border: 'border-yellow-500/30',  bg: 'from-yellow-500/10  to-yellow-500/5'  },
  above: { icon: '🔴', label: 'Above Market', desc: 'Premium or overpriced listing', border: 'border-red-500/30',     bg: 'from-red-500/10     to-red-500/5'     },
};

function fmtSource(source) {
  if (!source) return null;
  const MAP = {
    'tunisie_annonce': 'Tunisie Annonce', 'tunisie annonce': 'Tunisie Annonce',
    'mubawab': 'Mubawab', 'tayara': 'Tayara', 'afariat': 'Afariat',
  };
  return MAP[source.toLowerCase()] || source.split(/[_\s]+/).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

export default function PropertyDetailModal({ property, isOpen, onClose }) {
  if (!property) return null;

  const deal       = DEAL_META[property.deal] || DEAL_META.fair;
  const sourceName = fmtSource(property.source);
  const priceK = property.price >= 1_000_000
    ? `${(property.price / 1_000_000).toFixed(2)}M`
    : `${Math.round(property.price / 1000)}K`;

  const handleImageError = (e) => { e.target.src = '/images/property_listing_placeholder.png'; };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* ── Backdrop ── */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/75 backdrop-blur-sm z-40"
          />

          {/* ── Centering shell (flexbox, no CSS-transform conflict) ── */}
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 20 }}
              animate={{ opacity: 1, scale: 1,    y: 0  }}
              exit={{    opacity: 0, scale: 0.94, y: 20 }}
              transition={{ duration: 0.26, ease: 'easeOut' }}
              className="pointer-events-auto w-full max-w-2xl max-h-[88vh] bg-gradient-to-br from-slate-900 to-slate-950 rounded-2xl border border-slate-800 shadow-2xl shadow-black/60 overflow-y-auto"
            >
              {/* Close */}
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                onClick={onClose}
                className="absolute top-4 right-4 p-2 bg-slate-800/60 hover:bg-slate-700 rounded-lg transition-colors z-10"
              >
                <X className="w-5 h-5 text-gray-300" />
              </motion.button>

              <div className="flex flex-col md:flex-row">
                {/* Left — image */}
                <motion.div
                  initial={{ opacity: 0, x: -14 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.07 }}
                  className="md:w-[44%] flex-shrink-0"
                >
                  <div className="relative h-60 md:h-full min-h-[280px] overflow-hidden rounded-t-2xl md:rounded-l-2xl md:rounded-tr-none">
                    <img
                      src={property.image}
                      alt={property.title}
                      onError={handleImageError}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/30 to-transparent" />

                    {/* Type pill */}
                    <div className="absolute top-4 left-4 bg-gradient-to-r from-[#FF6B35] to-[#FF5520] rounded-lg px-3 py-1.5">
                      <p className="text-xs font-bold text-white tracking-wide uppercase">{property.type}</p>
                    </div>

                    {/* Source badge */}
                    {sourceName && (
                      <div className="absolute top-4 right-10 bg-black/55 border border-slate-700/60 rounded-md px-2 py-1">
                        <p className="text-xs text-gray-400">{sourceName}</p>
                      </div>
                    )}

                    {/* Price overlay */}
                    <div className="absolute bottom-0 left-0 right-0 p-4">
                      <p className="text-3xl font-black text-white drop-shadow-lg">{priceK} TND</p>
                      {property.pricePerM2 && (
                        <p className="text-sm text-[#FF6B35] font-semibold mt-0.5">
                          {property.pricePerM2.toLocaleString('fr-TN')} TND / m²
                        </p>
                      )}
                    </div>
                  </div>
                </motion.div>

                {/* Right — details */}
                <motion.div
                  initial={{ opacity: 0, x: 14 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.11 }}
                  className="md:w-[56%] p-6 space-y-4"
                >
                  {/* Location */}
                  <div>
                    <div className="flex items-start gap-2 mb-1">
                      <MapPin className="w-4 h-4 text-[#FF6B35] flex-shrink-0 mt-0.5" />
                      <div className="text-sm leading-tight">
                        {property.governorate && (
                          <span className="font-semibold text-white">{property.governorate}</span>
                        )}
                        {property.governorate && property.delegationName && (
                          <span className="text-gray-500"> · </span>
                        )}
                        {property.delegationName && (
                          <span className="text-gray-400">{property.delegationName}</span>
                        )}
                      </div>
                    </div>
                    <p className="text-gray-400 text-sm leading-snug pl-6 line-clamp-2">{property.title}</p>
                  </div>

                  {/* Specs */}
                  <div className="grid grid-cols-3 gap-3 p-4 bg-slate-800/40 rounded-xl border border-slate-700/40">
                    <div className="text-center">
                      <Ruler className="w-4 h-4 text-[#FF6B35] mx-auto mb-1.5" />
                      <p className="text-base font-black text-white">{property.area || '—'}</p>
                      <p className="text-xs text-gray-500">m²</p>
                    </div>
                    <div className="text-center">
                      <Bed className="w-4 h-4 text-[#FF6B35] mx-auto mb-1.5" />
                      <p className="text-base font-black text-white">{property.rooms || '—'}</p>
                      <p className="text-xs text-gray-500">Rooms</p>
                    </div>
                    <div className="text-center">
                      <Bath className="w-4 h-4 text-[#FF6B35] mx-auto mb-1.5" />
                      <p className="text-base font-black text-white">{property.bathrooms || '—'}</p>
                      <p className="text-xs text-gray-500">Bath</p>
                    </div>
                  </div>

                  {/* Price / m² */}
                  {property.pricePerM2 && (
                    <div className="flex items-center gap-3 p-3 bg-slate-800/40 rounded-xl border border-slate-700/40">
                      <TrendingUp className="w-4 h-4 text-[#FF6B35] flex-shrink-0" />
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider font-mono">Price per m²</p>
                        <p className="text-sm font-bold text-white">{property.pricePerM2.toLocaleString('fr-TN')} TND</p>
                      </div>
                    </div>
                  )}

                  {/* Deal assessment */}
                  <div className={`p-4 bg-gradient-to-r ${deal.bg} rounded-xl border ${deal.border}`}>
                    <div className="flex items-center gap-3">
                      <span className="text-xl">{deal.icon}</span>
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider font-mono">Market Assessment</p>
                        <p className="text-sm font-bold text-white">{deal.label}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{deal.desc}</p>
                      </div>
                    </div>
                  </div>

                  {/* Tags */}
                  {property.tags?.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-500 mb-2 font-mono uppercase tracking-wider flex items-center gap-1.5">
                        <Tag className="w-3 h-3" /> Details
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {property.tags.map((tag, i) => (
                          <span key={i} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#FF6B35]/10 border border-[#FF6B35]/30 rounded-lg text-xs text-[#FF6B35] font-medium capitalize">
                            <Check className="w-3 h-3" />{tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-3 pt-1">
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="flex-1 bg-gradient-to-r from-[#FF6B35] to-[#FF5520] hover:from-[#FF7545] hover:to-[#FF6535] text-white font-bold py-3 rounded-xl text-sm transition-all duration-200"
                    >
                      Contact Agent
                    </motion.button>
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={onClose}
                      className="px-5 py-3 bg-slate-800 hover:bg-slate-700 text-gray-300 font-bold rounded-xl text-sm border border-slate-700 transition-all duration-200"
                    >
                      Close
                    </motion.button>
                  </div>
                </motion.div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
