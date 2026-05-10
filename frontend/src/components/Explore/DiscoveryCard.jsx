import React from 'react';
import { motion } from 'framer-motion';

export default function DiscoveryCard({ insight }) {
  return (
    <motion.div
      whileHover={{ scale: 1.05, y: -4 }}
      className="bg-gradient-to-br from-slate-900/70 to-slate-950/70 border border-white/20 rounded-xl p-4 hover:border-orange-500/50 hover:bg-slate-900/90 transition-all h-full flex flex-col cursor-pointer group backdrop-blur-sm"
    >
      {/* Title */}
      <h3 className="text-white font-bold text-sm mb-2 line-clamp-2 group-hover:text-orange-400 transition leading-snug">
        {insight.title}
      </h3>

      {/* Price - Prominent */}
      <div className="mb-2.5">
        <p className="text-xl font-black text-[#FF6B35]">
          {insight.price}
        </p>
      </div>

      {/* Purpose Badge */}
      <div className="mb-2.5">
        <span className="inline-block text-xs px-2 py-1 rounded-full bg-orange-500/20 text-orange-300 font-semibold border border-orange-500/30 transition-colors group-hover:bg-orange-500/30">
          {insight.purpose}
        </span>
      </div>

      {/* Location */}
      <p className="text-xs text-gray-400 mb-2.5 font-medium line-clamp-1">
        {insight.location}
      </p>

      {/* Summary */}
      <p className="text-xs text-gray-300 mb-3 flex-1 line-clamp-2 leading-relaxed">
        {insight.summary}
      </p>

      {/* Lifestyle Tags */}
      <div className="flex flex-wrap gap-1 mb-3">
        {insight.tags.slice(0, 2).map((tag, i) => (
          <span key={i} className="text-xs px-1.5 py-0.5 bg-white/8 text-gray-300 rounded-full border border-white/15 hover:bg-white/15 transition">
            {tag}
          </span>
        ))}
      </div>

      {/* View Details Button */}
      <motion.button
        whileHover={{ boxShadow: '0 0 15px rgba(255, 107, 53, 0.25)' }}
        className="w-full py-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-300 text-xs font-semibold rounded-lg border border-orange-500/40 transition-all"
      >
        View Details →
      </motion.button>
    </motion.div>
  );
}
