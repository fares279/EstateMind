import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { User, Mail, Lock, Eye, EyeOff, ArrowRight } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError('');
  };

  const validateForm = () => {
    // Check empty fields
    if (!formData.first_name) {
      setError('First name is required');
      return false;
    }
    if (!formData.last_name) {
      setError('Last name is required');
      return false;
    }
    if (!formData.email) {
      setError('Email address is required');
      return false;
    }
    if (!formData.password) {
      setError('Password is required');
      return false;
    }

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError('Please enter a valid email address');
      return false;
    }

    // Password length
    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      return false;
    }

    // Password strength requirements
    const hasUppercase = /[A-Z]/.test(formData.password);
    const hasLowercase = /[a-z]/.test(formData.password);
    const hasNumbers = /\d/.test(formData.password);
    const hasSpecialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(formData.password);

    if (!hasUppercase) {
      setError('Password must contain at least one uppercase letter (A-Z)');
      return false;
    }
    if (!hasLowercase) {
      setError('Password must contain at least one lowercase letter (a-z)');
      return false;
    }
    if (!hasNumbers) {
      setError('Password must contain at least one number (0-9)');
      return false;
    }
    if (!hasSpecialChar) {
      setError('Password must contain at least one special character (!@#$%^&*...)');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    setLoading(true);
    setError('');

    try {
      await register(
        formData.email,
        `${formData.first_name} ${formData.last_name}`.trim(),
        formData.password,
        formData.password,  // Send password as confirmation (already validated on frontend)
        ''  // phone (optional)
      );
      // Save email to sessionStorage for VerifyOTPPage
      sessionStorage.setItem('registrationEmail', formData.email);
      navigate('/verify-otp', { state: { email: formData.email } });
    } catch (err) {
      let errorMessage = 'Registration failed. Please try again.';

      // Parse backend errors
      if (err.response?.data) {
        const data = err.response.data;

        // Check for specific field errors (DRF format)
        if (data.password) {
          const pwdErr = Array.isArray(data.password) ? data.password[0] : data.password;
          errorMessage = `Password: ${pwdErr}`;
        } else if (data.email) {
          const emailErr = Array.isArray(data.email) ? data.email[0] : data.email;
          errorMessage = `Email: ${emailErr}`;
        } else if (data.full_name) {
          const nameErr = Array.isArray(data.full_name) ? data.full_name[0] : data.full_name;
          errorMessage = `Name: ${nameErr}`;
        } else if (data.phone) {
          const phoneErr = Array.isArray(data.phone) ? data.phone[0] : data.phone;
          errorMessage = `Phone: ${phoneErr}`;
        } else if (data.password_confirm) {
          const confirmErr = Array.isArray(data.password_confirm) ? data.password_confirm[0] : data.password_confirm;
          errorMessage = `Confirm Password: ${confirmErr}`;
        } else if (data.non_field_errors) {
          const err = Array.isArray(data.non_field_errors) ? data.non_field_errors[0] : data.non_field_errors;
          errorMessage = err;
        } else if (data.detail) {
          errorMessage = data.detail;
        } else if (typeof data === 'object') {
          // Try to extract first error from any field
          const firstError = Object.values(data).find(val => val);
          if (firstError) {
            errorMessage = Array.isArray(firstError) ? firstError[0] : firstError;
          }
        }
      } else if (err.message) {
        errorMessage = err.message;
      }

      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const features = [
    {
      icon: '🚀',
      title: 'Quick Setup',
      description: 'Get started in minutes with our simple registration'
    },
    {
      icon: '🔒',
      title: 'Secure',
      description: 'Bank-level encryption for all your data'
    },
    {
      icon: '⚡',
      title: 'Powerful Tools',
      description: 'Access advanced real estate analytics'
    },
    {
      icon: '🎯',
      title: 'Smart Matching',
      description: 'Find properties that match your criteria'
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
          {/* Left Side - Features */}
          <div className="hidden lg:flex flex-col justify-between bg-gradient-to-b from-[#0B0F19] to-[#1A2332] p-12 text-white border-r border-white/8">
            <div>
              <h2 className="text-4xl font-black mb-2">EstateMind</h2>
              <p className="text-slate-400 text-lg">Real estate intelligence platform</p>
            </div>

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
              <h1 className="text-3xl font-black text-white mb-2">Create Your Account</h1>
              <p className="text-slate-400 mb-8">Join thousands of real estate professionals</p>
            </motion.div>

      {/* Error Alert */}
      {error && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mb-6 bg-red-500/10 border border-red-500/50 rounded-lg px-4 py-3 text-red-300 text-sm flex gap-3"
        >
          <span className="text-red-400 font-bold">⚠️</span>
          <div>
            <p className="font-semibold">Registration Error</p>
            <p className="mt-1">{error}</p>
          </div>
        </motion.div>
      )}

            <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name Row */}
        <div className="grid grid-cols-2 gap-4">
          {/* First Name */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="group"
          >
            <label className="block text-sm font-semibold text-slate-200 mb-2">First Name</label>
            <div className="relative">
              <User className="absolute left-3 top-3.5 text-slate-500 group-focus-within:text-orange-500/60 transition" size={18} />
              <input
                type="text"
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
                placeholder="John"
                className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/40 transition"
              />
            </div>
          </motion.div>

          {/* Last Name */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="group"
          >
            <label className="block text-sm font-semibold text-slate-200 mb-2">Last Name</label>
            <div className="relative">
              <User className="absolute left-3 top-3.5 text-slate-500 group-focus-within:text-orange-500/60 transition" size={18} />
              <input
                type="text"
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
                placeholder="Doe"
                className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/40 transition"
              />
            </div>
          </motion.div>
        </div>

          {/* Email Input */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
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
          transition={{ delay: 0.45 }}
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

          {/* Terms Checkbox */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="flex items-start gap-2 text-sm"
        >
          <input type="checkbox" className="w-4 h-4 mt-0.5 text-orange-500 rounded border-white/20 bg-white/5" required />
          <span className="text-slate-400">
            I agree to the{' '}
            <a href="/terms" className="text-orange-500 hover:text-orange-400 font-medium transition">
              Terms of Service
            </a>
            {' '}and{' '}
            <a href="/privacy" className="text-orange-500 hover:text-orange-400 font-medium transition">
              Privacy Policy
            </a>
          </span>
        </motion.div>

          {/* Sign Up Button */}
        <motion.button
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55 }}
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
              Creating account...
            </>
          ) : (
            <>
              Create Account <ArrowRight size={18} />
            </>
          )}
        </motion.button>

          {/* Divider */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="relative my-6"
        >
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-white/10"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-[#0B0F19] text-slate-500">Already have an account?</span>
          </div>
        </motion.div>

          {/* Sign In Link */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.65 }}
        >
          <Link
            to="/login"
            className="w-full py-2.5 px-4 rounded-lg font-semibold border-2 border-white/20 text-slate-200 hover:border-orange-500/60 hover:text-orange-500 transition-all flex items-center justify-center gap-2"
          >
            Sign In <ArrowRight size={18} />
          </Link>
        </motion.div>
            </form>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
