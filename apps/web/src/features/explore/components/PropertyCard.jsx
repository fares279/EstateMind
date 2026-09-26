import React from 'react';
import { motion } from 'framer-motion';
import { MapPin, Ruler, Bed, Bath, TrendingUp, ChevronRight } from 'lucide-react';

export default function PropertyCard({ property, isSelected, onViewDetails }) {
  const getDealIcon = (deal) => {
    switch (deal) {
      case 'good':  return '🟢';
      case 'fair':  return '🟡';
      case 'above': return '🔴';
      default:      return '⚪';
    }
  };

  const getDealLabel = (deal) => {
    switch (deal) {
      case 'good':  return 'Good Deal';
      case 'fair':  return 'Fair Value';
      case 'above': return 'Above Market';
      default:      return 'Market Price';
    }
  };

  const handleImageError = (e) => {
    e.target.src = '/images/property_listing_placeholder.png';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.3 }}
      className={`group relative bg-gradient-to-br from-slate-900/60 to-slate-950/60 backdrop-blur-sm rounded-xl overflow-hidden border transition-all duration-300 ${
        isSelected
          ? 'border-[#FF6B35] shadow-lg shadow-[#FF6B35]/20'
          : 'border-slate-800/50 hover:border-slate-700/80 shadow-lg shadow-black/20'
      }`}
    >
      {/* Image Section */}
      <div className="relative h-48 overflow-hidden bg-slate-900">
        <motion.img
          src={property.image}
          alt={property.location || property.title}
          onError={handleImageError}
          className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent" />

        {/* Price Badge */}
        <div className="absolute top-4 right-4 bg-black/80 backdrop-blur-sm border border-[#FF6B35]/40 rounded-lg px-3 py-2">
          <p className="text-2xl font-black text-[#FF6B35]">
            {property.price >= 1_000_000
              ? `${(property.price / 1_000_000).toFixed(1)}M`
              : `${Math.round(property.price / 1000)}K`} TND
          </p>
          <p className="text-xs text-gray-400">List Price</p>
        </div>

        {/* Property Type Badge */}
        <div className="absolute bottom-4 left-4 bg-gradient-to-r from-[#FF6B35]/80 to-[#FF6B35]/60 backdrop-blur-sm rounded-lg px-3 py-1">
          <p className="text-xs font-bold text-white">{property.type}</p>
        </div>
      </div>

      {/* Content Section */}
      <div className="p-5 space-y-4">
        {/* Title + Location */}
        <div className="flex items-start gap-2">
          <MapPin className="w-4 h-4 text-[#FF6B35] flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-white text-sm font-semibold">{property.title}</p>
            <p className="text-gray-300 text-sm font-medium">{property.location}</p>
          </div>
        </div>

        {/* Specs Grid */}
        <div className="grid grid-cols-3 gap-3 py-3 border-y border-slate-800/50">
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Ruler className="w-3.5 h-3.5 text-[#FF6B35]" />
            </div>
            <p className="text-sm font-black text-white">{property.area}</p>
            <p className="text-xs text-gray-500">m²</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Bed className="w-3.5 h-3.5 text-[#FF6B35]" />
            </div>
            <p className="text-sm font-black text-white">{property.rooms}</p>
            <p className="text-xs text-gray-500">Rooms</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Bath className="w-3.5 h-3.5 text-[#FF6B35]" />
            </div>
            <p className="text-sm font-black text-white">{property.bathrooms}</p>
            <p className="text-xs text-gray-500">Bath</p>
          </div>
        </div>

        {/* Deal Assessment */}
        <div className="flex items-center justify-between gap-3 p-3 bg-slate-800/30 rounded-lg border border-slate-700/50">
          <div className="flex items-center gap-2">
            <span className="text-lg">{getDealIcon(property.deal)}</span>
            <span className="text-sm font-medium text-gray-300">{getDealLabel(property.deal)}</span>
          </div>
          <TrendingUp className="w-4 h-4 text-[#FF6B35]" />
        </div>

        {/* Feature Tags */}
        {property.tags && property.tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {property.tags.slice(0, 2).map((tag, idx) => (
              <span
                key={idx}
                className="inline-block text-xs bg-[#FF6B35]/10 border border-[#FF6B35]/30 text-[#FF6B35] px-2 py-1 rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* View Details Button */}
        <motion.button
          whileHover={{ x: 4 }}
          onClick={() => onViewDetails && onViewDetails(property)}
          className="w-full mt-4 group/btn flex items-center justify-between px-4 py-3 bg-gradient-to-r from-[#FF6B35] to-[#FF5520] hover:from-[#FF7545] hover:to-[#FF6535] text-white font-bold rounded-lg transition-all duration-200"
        >
          <span>View Details</span>
          <ChevronRight className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" />
        </motion.button>
      </div>

      {/* Selection Indicator */}
      {isSelected && (
        <motion.div
          layoutId="selectedIndicator"
          className="absolute top-2 left-2 w-2 h-2 bg-[#FF6B35] rounded-full"
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      )}
    </motion.div>
  );
}
