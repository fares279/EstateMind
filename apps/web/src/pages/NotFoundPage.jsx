import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Home } from 'lucide-react';

export default function NotFoundPage() {
  return (
    <main className="pt-20 min-h-[calc(100vh-200px)] bg-gradient-to-b from-[#0B0F19] via-[#0B0F19] to-[#1a1f2e] flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center max-w-2xl"
      >
        {/* Error Code */}
        <motion.h1
          className="text-9xl font-bold bg-gradient-to-r from-[#FF6B35] to-[#FF8A5B] bg-clip-text text-transparent mb-4"
          animate={{ scale: [1, 1.05, 1] }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          404
        </motion.h1>

        {/* Error Title */}
        <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
          Page Not Found
        </h2>

        {/* Error Description */}
        <p className="text-xl text-gray-400 mb-8 leading-relaxed">
          The page you're looking for doesn't exist or has been removed. 
          Let's get you back on track to exploring Tunisia's real estate market.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            to="/"
            className="inline-flex items-center justify-center gap-2 px-8 py-3 bg-gradient-to-r from-[#FF6B35] to-[#FF8A5B] text-white font-semibold rounded-lg hover:shadow-lg hover:shadow-[#FF6B35]/50 transition-all duration-300"
          >
            <Home size={20} />
            Go Home
          </Link>

          <Link
            to="/explore"
            className="inline-flex items-center justify-center gap-2 px-8 py-3 bg-white/10 text-white font-semibold rounded-lg hover:bg-white/20 transition-all duration-300 border border-white/20"
          >
            Explore Market
            <ArrowRight size={20} />
          </Link>
        </div>

      </motion.div>
    </main>
  );
}
