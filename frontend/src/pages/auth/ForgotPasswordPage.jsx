import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Mail, ArrowRight, CheckCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const { forgotPassword } = useAuth();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleChange = (e) => {
    setEmail(e.target.value);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
      setError('Please enter a valid email address');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await forgotPassword(email);
      setSuccess(true);
      sessionStorage.setItem('resetEmail', email);
      
      // Auto redirect after 3 seconds or let user click button
      setTimeout(() => {
        navigate('/reset-password', { replace: true });
      }, 3000);
    } catch (err) {
      // Don't reveal if email exists for security
      setSuccess(true);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
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
          className="w-full max-w-md bg-white/4 backdrop-blur-lg border border-white/8 rounded-2xl shadow-2xl overflow-hidden relative z-10 p-8"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6 }}
            className="text-center"
          >
            <div className="w-20 h-20 bg-green-500/10 border border-green-500/30 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="text-green-500 animate-pulse" size={40} />
            </div>

            <h1 className="text-3xl font-black text-white mb-2">Check Your Email</h1>
            <p className="text-slate-400 mb-6">
              We've sent password reset instructions to <strong>{email}</strong>
            </p>

            <div className="bg-white/5 border border-white/10 rounded-xl p-6 mb-6">
              <h3 className="text-white font-semibold mb-3">What's next?</h3>
              <ul className="text-slate-400 text-sm space-y-2">
                <li>✓ Open the email from EstateMind</li>
                <li>✓ Click the reset link (valid for 24 hours)</li>
                <li>✓ Enter your new password</li>
                <li>✓ Log in with new password</li>
              </ul>
            </div>

            <motion.button
              onClick={() => navigate('/reset-password')}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.99 }}
              className="w-full py-2.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-bold transition-all flex items-center justify-center gap-2 mb-4 shadow-lg hover:shadow-orange-500/25"
            >
              Enter Reset Code <ArrowRight size={20} />
            </motion.button>

            <p className="text-slate-400 text-sm mb-4">
              Already got your code? Paste it above and create a new password.
            </p>

            <button
              onClick={() => navigate('/login')}
              className="text-slate-400 hover:text-slate-300 text-sm transition"
            >
              ← Back to Log In
            </button>

            <p className="text-xs text-slate-500 mt-6">
              Didn't receive the email? Check your spam folder or{' '}
              <button onClick={() => setSuccess(false)} className="text-orange-500 hover:text-orange-400 transition">
                try again
              </button>
            </p>
          </motion.div>
        </motion.div>
      </div>
    );
  }

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
        className="w-full max-w-md bg-white/4 backdrop-blur-lg border border-white/8 rounded-2xl shadow-2xl overflow-hidden relative z-10 p-8"
      >
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-8 text-center"
        >
          <div className="w-16 h-16 bg-orange-500/10 border border-orange-500/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <Mail className="text-orange-500" size={32} />
          </div>
          <h1 className="text-3xl font-black text-white mb-2">Forgot Password?</h1>
          <p className="text-slate-400">
            No problem! Enter your email and we'll send you a reset link.
          </p>
        </motion.div>

        <motion.form
          onSubmit={handleSubmit}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="space-y-6"
        >
          {/* Error Alert */}
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm"
            >
              {error}
            </motion.div>
          )}

          {/* Email Input */}
          <div>
            <label className="block text-slate-200 text-sm font-semibold mb-2">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 text-slate-500" size={20} />
              <input
                type="email"
                value={email}
                onChange={handleChange}
                placeholder="your@email.com"
                className="w-full bg-white/5 border border-white/8 rounded-lg pl-10 pr-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-orange-500/50 focus:ring-2 focus:ring-orange-500/20 transition-all"
              />
            </div>
            <p className="text-xs text-slate-500 mt-2">
              We'll send a verification code to this email
            </p>
          </div>

          {/* Submit Button */}
          <motion.button
            type="submit"
            disabled={loading || !email}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.99 }}
            className={`w-full py-2.5 rounded-lg font-bold transition-all flex items-center justify-center gap-2 ${
              loading || !email
                ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                : 'bg-orange-500 hover:bg-orange-600 text-white shadow-lg hover:shadow-orange-500/25'
            }`}
          >
            {loading ? (
              <>
                <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Sending...
              </>
            ) : (
              <>
                Send Reset Code <ArrowRight size={20} />
              </>
            )}
          </motion.button>

          {/* Divider */}
          <div className="py-4 border-t border-white/10" />

          {/* Back to Login */}
          <p className="text-center text-slate-400">
            Remember your password?{' '}
            <button
              onClick={() => navigate('/login')}
              className="text-orange-500 hover:text-orange-400 font-semibold transition"
            >
              Sign in here
            </button>
          </p>

          <p className="text-center text-slate-400">
            Don't have an account?{' '}
            <button
              onClick={() => navigate('/register')}
              className="text-orange-500 hover:text-orange-400 font-semibold transition"
            >
              Create one
            </button>
          </p>
        </motion.form>

        {/* Security Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mt-6 bg-white/5 border border-white/10 rounded-lg p-4 text-xs text-slate-500 text-center"
        >
          ⚠️ Reset links expire after 24 hours for security. If your link expires, request a new one.
        </motion.div>

        </motion.div>
    </div>
  );
}
