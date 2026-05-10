import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Mail, Lock, Eye, EyeOff, ArrowRight } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.email || !formData.password) {
      setError('Please fill in all fields');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await login(formData.email, formData.password);
      navigate('/explore', { replace: true });
    } catch (err) {
      setError(err?.message || err.response?.data?.detail || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const features = [
    {
      icon: '🔍',
      title: 'Explore Market',
      description: 'Discover properties and real estate trends'
    },
    {
      icon: '💎',
      title: 'AI Valuations',
      description: 'Get accurate valuations powered by AI'
    },
    {
      icon: '📊',
      title: 'Smart Analytics',
      description: 'Data-driven insights for better decisions'
    },
    {
      icon: '👥',
      title: 'Community',
      description: 'Connect with real estate professionals'
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Ambient background glow */}
      <motion.div
        className="absolute top-20 right-10 w-96 h-96 bg-orange-500/12 rounded-full blur-3xl"
        animate={{ scale: [1, 1.2, 1], opacity: [0.12, 0.18, 0.12] }}
        transition={{ duration: 8, repeat: Infinity }}
      />
      <motion.div
        className="absolute bottom-20 left-10 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl"
        animate={{ scale: [1.2, 1, 1.2], opacity: [0.08, 0.14, 0.08] }}
        transition={{ duration: 10, repeat: Infinity, delay: 2 }}
      />

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-5xl bg-white/4 backdrop-blur-lg border border-white/8 rounded-2xl shadow-2xl overflow-hidden relative z-10"
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-0">
          <div className="hidden lg:flex flex-col justify-between bg-gradient-to-b from-[#0B0F19] to-[#1A2332] p-12 text-white border-r border-white/8">
            <Link to="/" className="flex items-center gap-3 mb-8 hover:opacity-80 transition group">
              <img src="/images/logo_without_name.png" alt="EstateMind Logo" className="h-10 w-10 group-hover:scale-110 transition" />
              <div>
                <h2 className="text-4xl font-black mb-0">EstateMind</h2>
                <p className="text-slate-400 text-lg">Real estate intelligence platform</p>
              </div>
            </Link>

            <div className="space-y-6">
              {features.map((feature, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1 + idx * 0.1 }}
                  className="flex gap-4"
                >
                  <div className="text-3xl">{feature.icon}</div>
                  <div>
                    <h3 className="font-bold text-base text-white">{feature.title}</h3>
                    <p className="text-slate-400 text-sm">{feature.description}</p>
                  </div>
                </motion.div>
              ))}
            </div>

            <div className="text-slate-500 text-xs">
              © 2026 EstateMind. All rights reserved.
            </div>
          </div>

          {/* Right Side - Form */}
          <div className="p-8 lg:p-12 flex flex-col justify-center bg-[#0B0F19]/80 backdrop-blur">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <h1 className="text-3xl font-black text-white mb-2">Welcome Back</h1>
              <p className="text-slate-400 mb-8">Sign in to your account and explore opportunities</p>
            </motion.div>

            {/* Error Alert */}
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mb-6 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm"
              >
                {error}
              </motion.div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Email Input */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="group"
              >
                <label className="block text-sm font-semibold text-slate-200 mb-2">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3.5 text-slate-500 group-focus-within:text-orange-500/60 transition" size={18} />
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="you@example.com"
                    className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/40 transition"
                  />
                </div>
              </motion.div>

              {/* Password Input */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.35 }}
                className="group"
              >
                <label className="block text-sm font-semibold text-slate-200 mb-2">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-3.5 text-slate-500 group-focus-within:text-orange-500/60 transition" size={18} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="••••••••"
                    className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-10 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/40 transition"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-3.5 text-slate-500 hover:text-slate-400 transition"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </motion.div>

              {/* Remember Me & Forgot Password */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
                className="flex items-center justify-between text-sm"
              >
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input type="checkbox" className="w-4 h-4 text-orange-500 rounded border-white/20 bg-white/5" />
                  <span className="text-slate-400 group-hover:text-slate-300">Remember me</span>
                </label>
                <Link to="/forgot-password" className="text-orange-500 hover:text-orange-400 font-medium transition">
                  Forgot password?
                </Link>
              </motion.div>

              {/* Sign In Button */}
              <motion.button
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.45 }}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                type="submit"
                disabled={loading}
                className={`w-full py-2.5 px-4 rounded-lg font-semibold transition-all flex items-center justify-center gap-2 ${
                  loading
                    ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                    : 'bg-orange-500 hover:bg-orange-600 text-white shadow-lg hover:shadow-orange-500/25'
                }`}
              >
                {loading ? (
                  <>
                    <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Signing in...
                  </>
                ) : (
                  <>
                    Sign In <ArrowRight size={18} />
                  </>
                )}
              </motion.button>

              {/* Divider */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
                className="relative my-6"
              >
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-white/10"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-[#0B0F19] text-slate-500">New to EstateMind?</span>
                </div>
              </motion.div>

              {/* Sign Up Link */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.55 }}
              >
                <Link
                  to="/register"
                  className="w-full py-2.5 px-4 rounded-lg font-semibold border-2 border-white/20 text-slate-200 hover:border-orange-500/60 hover:text-orange-500 transition-all flex items-center justify-center gap-2"
                >
                  Create Account <ArrowRight size={18} />
                </Link>
              </motion.div>
            </form>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
