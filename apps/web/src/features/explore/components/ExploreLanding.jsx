import React from 'react';
import { motion } from 'framer-motion';
import { useInView } from 'react-intersection-observer';
import { ChevronDown, ArrowRight } from 'lucide-react';

export default function ExploreLanding() {
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

      {/* Animated Background Glows */}
      <div className="absolute inset-0 pointer-events-none">
        <motion.div 
          className="absolute top-1/3 left-1/4 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl" 
          animate={{ scale: [1, 1.2, 1] }} 
          transition={{ duration: 8, repeat: Infinity }}
        />
        <motion.div 
          className="absolute bottom-1/3 right-1/4 w-80 h-80 bg-blue-500/5 rounded-full blur-3xl" 
          animate={{ scale: [1.2, 1, 1.2] }} 
          transition={{ duration: 10, repeat: Infinity, delay: 2 }}
        />
      </div>

      <div className="max-w-7xl mx-auto px-6 relative z-10 w-full">
        <div className="grid md:grid-cols-2 gap-12 items-center min-h-screen">
          {/* Left: Text Content */}
          <motion.div 
            ref={ref}
            initial={{ opacity: 0, x: -40 }} 
            animate={inView ? { opacity: 1, x: 0 } : {}} 
            transition={{ duration: 0.8 }}
          >
            <div className="text-orange-500/60 font-mono text-sm tracking-widest mb-3 uppercase">— EstateMind Explore</div>
            <h1 className="text-5xl md:text-6xl font-black leading-tight mb-4 text-white">
              Real Estate Search,<br/>
              <span className="text-[#FF6B35]">Simplified</span>
            </h1>
            <p className="text-lg text-gray-300 mb-6 leading-relaxed">
              Discover, compare, and evaluate properties in Tunisia.
            </p>

            {/* Three Key Features */}
            <div className="space-y-4 mb-8">
              <motion.div 
                initial={{ opacity: 0, x: -20 }} 
                animate={inView ? { opacity: 1, x: 0 } : {}} 
                transition={{ delay: 0.2 }}
                className="flex items-start gap-3"
              >
                <span className="text-2xl">🏡</span>
                <div>
                  <h3 className="text-white font-bold">Real Demand Signals</h3>
                  <p className="text-gray-400 text-sm">Understand where people are actively buying and renting.</p>
                </div>
              </motion.div>

              <motion.div 
                initial={{ opacity: 0, x: -20 }} 
                animate={inView ? { opacity: 1, x: 0 } : {}} 
                transition={{ delay: 0.3 }}
                className="flex items-start gap-3"
              >
                <span className="text-2xl">💰</span>
                <div>
                  <h3 className="text-white font-bold">Price Clarity</h3>
                  <p className="text-gray-400 text-sm">See whether a property is fairly priced compared to similar homes.</p>
                </div>
              </motion.div>

              <motion.div 
                initial={{ opacity: 0, x: -20 }} 
                animate={inView ? { opacity: 1, x: 0 } : {}} 
                transition={{ delay: 0.4 }}
                className="flex items-start gap-3"
              >
                <span className="text-2xl">🔍</span>
                <div>
                  <h3 className="text-white font-bold">Smarter Choices</h3>
                  <p className="text-gray-400 text-sm">Compare options based on lifestyle, budget, and location.</p>
                </div>
              </motion.div>
            </div>

            <motion.a 
              href="#workspace"
              initial={{ opacity: 0, y: 10 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.5 }}
              className="inline-block px-8 py-4 bg-[#FF6B35] text-white font-bold rounded-lg hover:bg-orange-600 transition-all shadow-lg shadow-orange-500/30"
              whileHover={{ scale: 1.05, boxShadow: '0 0 30px rgba(255, 107, 53, 0.6)' }}
              whileTap={{ scale: 0.95 }}
            >
              Start Exploring <ArrowRight size={20} className="inline ml-2" />
            </motion.a>
          </motion.div>

          {/* Right: Visual */}
          <motion.div 
            initial={{ opacity: 0, x: 40 }} 
            animate={inView ? { opacity: 1, x: 0 } : {}} 
            transition={{ duration: 0.8, delay: 0.2 }}
            className="hidden md:flex items-center justify-center relative"
          >
            <div className="w-full rounded-3xl overflow-hidden shadow-2xl shadow-orange-500/20 border border-orange-500/30">
              <img 
                src="/images/explore_property_module.png" 
                alt="Property Module" 
                className="w-full h-auto object-contain"
              />
            </div>
          </motion.div>
        </div>

        {/* Scroll Indicator */}
        <motion.div 
          className="absolute bottom-10 left-6 lg:bottom-12"
          animate={{ y: [0, 10, 0] }} 
          transition={{ duration: 2, repeat: Infinity }}
        >
          <ChevronDown size={32} className="text-orange-400" />
        </motion.div>
      </div>
    </section>
  );
}
