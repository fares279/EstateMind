import React from 'react';
import { motion } from 'framer-motion';

export default function Footer() {
  return (
    <footer className="relative bg-gradient-to-b from-[#0B0F19] to-black border-t border-orange-500/20 overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-5">
        <img 
          src="/images/pattern-data-grid.png" 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>
      <div className="max-w-6xl mx-auto px-6 relative z-10 py-16">
        {/* Header: Logo + Brand */}
        <div className="flex items-center justify-between mb-12 pb-8 border-b border-orange-500/10">
          <div className="flex items-center gap-3">
            <img src="/images/logo_without_name.png" alt="EstateMind" className="w-12 h-12" />
            <div>
              <h3 className="text-white font-black text-2xl leading-tight">EstateMind</h3>
              <p className="text-orange-500/70 text-xs font-mono tracking-widest">TRANSFORMING REAL ESTATE</p>
            </div>
          </div>
          {/* Social Icons */}
          <motion.div className="flex gap-3" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6, delay: 0.3 }}>
            <motion.a 
              href="#" 
              className="w-11 h-11 rounded-lg bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/30 flex items-center justify-center hover:bg-orange-500/30 hover:border-orange-500/60 transition-all group"
              whileHover={{ scale: 1.1, y: -3, borderColor: '#FFB366' }}
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-5 h-5 text-orange-400 group-hover:text-orange-300" fill="currentColor" viewBox="0 0 24 24"><path d="M19 3a9 9 0 01-9 9m0-9a9 9 0 019 9m-9-9v9m0 0a9 9 0 009-9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/><path d="M23 19.5c0 .827-.67 1.5-1.5 1.5S20 20.327 20 19.5s.67-1.5 1.5-1.5 1.5.673 1.5 1.5zm-18 0c0 .827-.67 1.5-1.5 1.5S2 20.327 2 19.5s.67-1.5 1.5-1.5 1.5.673 1.5 1.5z" fill="currentColor"/><circle cx="12" cy="5" r="2" fill="currentColor"/></svg>
            </motion.a>
            <motion.a 
              href="#" 
              className="w-11 h-11 rounded-lg bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/30 flex items-center justify-center hover:bg-orange-500/30 hover:border-orange-500/60 transition-all group"
              whileHover={{ scale: 1.1, y: -3, borderColor: '#FFB366' }}
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-5 h-5 text-orange-400 group-hover:text-orange-300" fill="currentColor" viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
            </motion.a>
            <motion.a 
              href="#" 
              className="w-11 h-11 rounded-lg bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/30 flex items-center justify-center hover:bg-orange-500/30 hover:border-orange-500/60 transition-all group"
              whileHover={{ scale: 1.1, y: -3, borderColor: '#FFB366' }}
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-5 h-5 text-orange-400 group-hover:text-orange-300" fill="currentColor" viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="5" ry="5" fill="none" stroke="currentColor" strokeWidth="2"/><circle cx="12" cy="12" r="3.5" fill="currentColor"/><circle cx="18.5" cy="5.5" r="1.5" fill="currentColor"/></svg>
            </motion.a>
          </motion.div>
        </div>

        {/* Main Grid Section */}
        <div className="grid md:grid-cols-4 gap-12 mb-12">
          {/* About Column */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} viewport={{ once: true }}>
            <h4 className="text-white font-bold text-xs uppercase tracking-widest mb-4 text-orange-400">About</h4>
            <p className="text-gray-400 text-sm leading-relaxed">Transforming Tunisia's real estate market with AI-powered intelligence and community-driven insights for better decisions.</p>
          </motion.div>
          {/* Product Column */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }} viewport={{ once: true }}>
            <h4 className="text-white font-bold text-xs uppercase tracking-widest mb-4 text-orange-400">Product</h4>
            <ul className="space-y-2.5 text-gray-400 text-sm">
              <li><motion.a href="/explore" className="hover:text-orange-400 hover:translate-x-1 transition-all inline-block" whileHover={{ x: 4, color: '#FF6B35' }} whileTap={{ scale: 0.95 }}>Explore Market</motion.a></li>
              <li><motion.a href="/valuate" className="hover:text-orange-400 hover:translate-x-1 transition-all inline-block" whileHover={{ x: 4, color: '#FF6B35' }} whileTap={{ scale: 0.95 }}>AI Valuation</motion.a></li>
              <li><motion.a href="/legal" className="hover:text-orange-400 hover:translate-x-1 transition-all inline-block" whileHover={{ x: 4, color: '#FF6B35' }} whileTap={{ scale: 0.95 }}>Legal AI</motion.a></li>
            </ul>
          </motion.div>
          {/* Community Column */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }} viewport={{ once: true }}>
            <h4 className="text-white font-bold text-xs uppercase tracking-widest mb-4 text-orange-400">Community</h4>
            <ul className="space-y-2.5 text-gray-400 text-sm">
              <li><motion.a href="/community" className="hover:text-orange-400 hover:translate-x-1 transition-all inline-block" whileHover={{ x: 4, color: '#FF6B35' }} whileTap={{ scale: 0.95 }}>#Aaref_Bledek</motion.a></li>
            </ul>
          </motion.div>
          {/* Support Column */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.3 }} viewport={{ once: true }}>
            <h4 className="text-white font-bold text-xs uppercase tracking-widest mb-4 text-orange-400">Support</h4>
            <ul className="space-y-2.5 text-gray-400 text-sm">
              <li><motion.a href="/community" className="hover:text-orange-400 hover:translate-x-1 transition-all inline-block" whileHover={{ x: 4, color: '#FF6B35' }} whileTap={{ scale: 0.95 }}>Campaign</motion.a></li>
              <li><motion.a href="#" className="hover:text-orange-400 hover:translate-x-1 transition-all inline-block" whileHover={{ x: 4, color: '#FF6B35' }} whileTap={{ scale: 0.95 }}>Privacy Policy</motion.a></li>
              <li><motion.a href="/community" className="hover:text-orange-400 hover:translate-x-1 transition-all inline-block" whileHover={{ x: 4, color: '#FF6B35' }} whileTap={{ scale: 0.95 }}>Join #Aaref_Bledek</motion.a></li>
            </ul>
          </motion.div>
        </div>
        
        {/* Divider */}
        <div className="h-px bg-gradient-to-r from-transparent via-orange-500/20 via-50% to-transparent mb-6" />
        
        {/* Bottom Footer */}
        <div className="text-center">
          <p className="text-gray-500 text-xs">&copy; 2026 EstateMind. All rights reserved. Building Tunisia's real estate future together.</p>
        </div>
      </div>
    </footer>
  );
}
