import React from 'react';
import { motion } from 'framer-motion';

export default function AuthLayout({ children, title, description, features }) {
  return (
    <div className="min-h-screen flex">
      {/* Left Side - Visual/Branding */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8 }}
        className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-[#0B0F19] via-[#1A2332] to-[#0B0F19] p-12 flex-col justify-between relative overflow-hidden"
      >
        {/* Animated background elements */}
        <div className="absolute top-0 left-0 w-96 h-96 bg-orange-500/5 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2 animate-pulse"></div>
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-orange-500/5 rounded-full blur-3xl translate-x-1/2 translate-y-1/2 animate-pulse" style={{ animationDelay: '2s' }}></div>

        {/* Logo & Branding */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="relative z-10"
        >
          <div className="text-5xl font-black text-orange-500 mb-3">
            🏠 EstateMind
          </div>
          <p className="text-xl text-gray-300 font-light">Real Estate Intelligence</p>
          <p className="text-gray-500 mt-2">Transforming Tunisia's real estate market</p>
        </motion.div>

        {/* Features/Content */}
        {features && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="relative z-10 space-y-4"
          >
            {features.map((feature, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.5 + idx * 0.1 }}
                className="flex items-start gap-4"
              >
                <div className="text-2xl mt-1">{feature.icon}</div>
                <div>
                  <h4 className="text-white font-semibold text-sm">{feature.title}</h4>
                  <p className="text-gray-400 text-xs mt-1">{feature.description}</p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* Footer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="relative z-10 text-xs text-gray-500"
        >
          <p>© 2026 EstateMind. All rights reserved.</p>
          <p className="mt-1">Building Tunisia's real estate future together.</p>
        </motion.div>
      </motion.div>

      {/* Right Side - Form */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6, delay: 0.2 }}
        className="w-full lg:w-1/2 bg-gradient-to-b from-white to-gray-50 lg:bg-white flex flex-col justify-center items-center p-8 lg:p-12"
      >
        {/* Mobile Logo */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          className="lg:hidden text-center mb-8"
        >
          <div className="text-4xl font-black text-orange-500 mb-2">
            🏠 EstateMind
          </div>
          <p className="text-gray-600 text-sm">Real Estate Intelligence</p>
        </motion.div>

        {/* Form Container */}
        <div className="w-full max-w-md">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mb-8"
          >
            <h1 className="text-3xl font-black text-gray-900 mb-2">{title}</h1>
            <p className="text-gray-600 text-sm">{description}</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            {children}
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}
