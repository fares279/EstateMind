import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Lock, ArrowRight, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { resetPassword } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [formData, setFormData] = useState({
    token: searchParams.get('token') || '',
    password: '',
    password_confirm: '',
  });

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.token) {
      setError('Reset token is missing. Please use the link from your email.');
      return;
    }

    if (!formData.password) {
      setError('Please enter a new password');
      return;
    }

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    if (formData.password !== formData.password_confirm) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await resetPassword(formData.token, formData.password, formData.password_confirm);
      sessionStorage.removeItem('resetEmail');
      navigate('/login', { 
        replace: true,
        state: { message: 'Password reset successful! Please log in with your new password.' }
      });
    } catch (err) {
      setError(
        err.response?.data?.detail || 
        'Reset link is invalid or expired. Please request a new one.'
      );
    } finally {
      setLoading(false);
    }
  };

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
            <Lock className="text-orange-500" size={32} />
          </div>
          <h1 className="text-3xl font-black text-white mb-2">Set New Password</h1>
          <p className="text-slate-400">
            Create a strong password to secure your account
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

          {/* Token Input (if not in URL) */}
          {!formData.token && (
            <div>
              <label className="block text-slate-200 text-sm font-semibold mb-2">Reset Code</label>
              <input
                type="text"
                name="token"
                value={formData.token}
                onChange={handleChange}
                placeholder="Paste your reset token from email"
                className="w-full bg-white/5 border border-white/8 rounded-lg px-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-orange-500/50 focus:ring-2 focus:ring-orange-500/20 transition-all text-sm font-mono"
              />
            </div>
          )}

          {/* New Password */}
          <div>
            <label className="block text-slate-200 text-sm font-semibold mb-2">New Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 text-slate-500" size={20} />
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="••••••••"
                className="w-full bg-white/5 border border-white/8 rounded-lg pl-10 pr-10 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-orange-500/50 focus:ring-2 focus:ring-orange-500/20 transition-all"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Strong password: 8+ characters, mix of uppercase, lowercase, numbers
            </p>
          </div>

          {/* Confirm Password */}
          <div>
            <label className="block text-slate-200 text-sm font-semibold mb-2">Confirm Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 text-slate-500" size={20} />
              <input
                type={showConfirm ? 'text' : 'password'}
                name="password_confirm"
                value={formData.password_confirm}
                onChange={handleChange}
                placeholder="••••••••"
                className="w-full bg-white/5 border border-white/8 rounded-lg pl-10 pr-10 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-orange-500/50 focus:ring-2 focus:ring-orange-500/20 transition-all"
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
              >
                {showConfirm ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
          </div>

          {/* Password Strength Indicator */}
          {formData.password && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="bg-white/5 border border-white/10 rounded-lg p-4"
            >
              <p className="text-xs font-semibold text-white mb-2">Password Strength</p>
              <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{
                    width:
                      formData.password.length >= 12 && /[A-Z]/.test(formData.password) && /[0-9]/.test(formData.password)
                        ? '100%'
                        : formData.password.length >= 8
                        ? '60%'
                        : '30%',
                  }}
                  className={`h-full transition-all ${
                    formData.password.length >= 12 && /[A-Z]/.test(formData.password) && /[0-9]/.test(formData.password)
                      ? 'bg-green-500'
                      : formData.password.length >= 8
                      ? 'bg-yellow-500'
                      : 'bg-red-500'
                  }`}
                />
              </div>
              <p className="text-xs text-slate-400 mt-2">
                {formData.password.length < 8 && 'Too weak'}
                {formData.password.length >= 8 && formData.password.length < 12 && 'Moderate'}
                {formData.password.length >= 12 && /[A-Z]/.test(formData.password) && /[0-9]/.test(formData.password) && 'Strong'}
              </p>
            </motion.div>
          )}

          {/* Submit Button */}
          <motion.button
            type="submit"
            disabled={loading || !formData.password || !formData.password_confirm || !formData.token}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.99 }}
            className={`w-full py-2.5 rounded-lg font-bold transition-all flex items-center justify-center gap-2 ${
              loading || !formData.password || !formData.password_confirm || !formData.token
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
                Resetting Password...
              </>
            ) : (
              <>
                Reset Password <ArrowRight size={20} />
              </>
            )}
          </motion.button>

          {/* Back to Login */}
          <div className="text-center pt-4 border-t border-white/10">
            <p className="text-slate-400 text-sm">
              Remember your password?{' '}
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="text-orange-500 hover:text-orange-400 font-semibold transition"
              >
                Sign in
              </button>
            </p>
          </div>
        </motion.form>

        {/* Info Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mt-6 bg-white/5 border border-white/10 rounded-lg p-4 text-xs text-slate-400"
        >
          <p className="mb-2">🔒 <strong>Security Tips:</strong></p>
          <ul className="space-y-1">
            <li>• Use a unique password you haven't used before</li>
            <li>• Don't share your password with anyone</li>
            <li>• Enable two-factor authentication for extra security</li>
          </ul>
        </motion.div>

      </motion.div>
    </div>
  );
}
