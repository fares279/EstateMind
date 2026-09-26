import React from 'react';
import { motion } from 'framer-motion';
import { useInView } from 'react-intersection-observer';

export default function DiscoveryIntro() {
  const [ref, inView] = useInView({ threshold: 0.3, triggerOnce: true });

  return (
    <section className="relative h-screen flex items-center justify-center overflow-hidden bg-black">
      {/* Background Pattern */}
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <img 
          src="/images/pattern-data-grid.png" 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>

      {/* Animated Glows */}
      <div className="absolute inset-0 pointer-events-none">
        <motion.div 
          className="absolute top-1/4 right-1/4 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl" 
          animate={{ scale: [1, 1.3, 1] }} 
          transition={{ duration: 8, repeat: Infinity }}
        />
        <motion.div 
          className="absolute bottom-1/4 left-1/4 w-80 h-80 bg-blue-500/5 rounded-full blur-3xl" 
          animate={{ scale: [1.2, 1, 1.2] }} 
          transition={{ duration: 10, repeat: Infinity, delay: 3 }}
        />
      </div>

      <div className="max-w-5xl mx-auto px-6 relative z-10 text-center">
        <motion.div 
          ref={ref}
          initial={{ opacity: 0, y: 40 }} 
          animate={inView ? { opacity: 1, y: 0 } : {}} 
          transition={{ duration: 0.8 }}
        >
          <div className="text-orange-500/60 font-mono text-sm tracking-widest mb-4 uppercase">— How It Works</div>
          <h2 className="text-5xl md:text-6xl font-black text-white mb-4">
            Understand the Market <br/>
            <span className="text-[#FF6B35]">Before You Decide</span>
          </h2>
          <p className="text-xl text-gray-300 mb-12 max-w-2xl mx-auto leading-relaxed">
            EstateMind helps you see beyond listings by highlighting patterns that matter to buyers, renters, and sellers.
          </p>

          {/* Three Core Blocks */}
          <div className="grid md:grid-cols-3 gap-6">
            <motion.div 
              initial={{ opacity: 0, y: 20 }} 
              animate={inView ? { opacity: 1, y: 0 } : {}} 
              transition={{ delay: 0.1 }}
              className="bg-gradient-to-br from-orange-500/20 to-orange-900/10 border border-orange-500/30 rounded-xl p-6 hover:border-orange-500/60 transition-all"
            >
              <div className="text-4xl mb-3">🏡</div>
              <h3 className="text-white font-bold text-lg mb-2">Real Demand Signals</h3>
              <p className="text-gray-300 text-sm">Understand where people are actively buying and renting.</p>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 20 }} 
              animate={inView ? { opacity: 1, y: 0 } : {}} 
              transition={{ delay: 0.2 }}
              className="bg-gradient-to-br from-orange-500/20 to-orange-900/10 border border-orange-500/30 rounded-xl p-6 hover:border-orange-500/60 transition-all"
            >
              <div className="text-4xl mb-3">💰</div>
              <h3 className="text-white font-bold text-lg mb-2">Price Clarity</h3>
              <p className="text-gray-300 text-sm">See whether a property is fairly priced compared to similar homes.</p>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 20 }} 
              animate={inView ? { opacity: 1, y: 0 } : {}} 
              transition={{ delay: 0.3 }}
              className="bg-gradient-to-br from-orange-500/20 to-orange-900/10 border border-orange-500/30 rounded-xl p-6 hover:border-orange-500/60 transition-all"
            >
              <div className="text-4xl mb-3">🔍</div>
              <h3 className="text-white font-bold text-lg mb-2">Smarter Choices</h3>
              <p className="text-gray-300 text-sm">Compare options based on lifestyle, budget, and location.</p>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
