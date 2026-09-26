import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Mail, ArrowRight, RefreshCw } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function VerifyOTPPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { verifyOTP, resendOTP } = useAuth();
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resendLoading, setResendLoading] = useState(false);
  const [countdown, setCountdown] = useState(0);
  // Get email from sessionStorage first, then from navigation state
  const email = sessionStorage.getItem('registrationEmail') || location.state?.email || '';

  useEffect(() => {
    if (!email) {
      navigate('/register', { replace: true });
    }
  }, [email, navigate]);

  useEffect(() => {
    let timer;
    if (countdown > 0) {
      timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [countdown]);

  const handleOtpChange = (e) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
    setOtp(value);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (otp.length !== 6) {
      setError('Please enter a 6-digit code');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await verifyOTP(email, otp);
      sessionStorage.removeItem('registrationEmail');
      navigate('/login', { replace: true, state: { message: 'Email verified! Please log in.' } });
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid or expired OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setResendLoading(true);
    setError('');

    try {
      await resendOTP(email);
      setCountdown(60);
      setOtp('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to resend OTP');
    } finally {
      setResendLoading(false);
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
            <Mail className="text-orange-500" size={32} />
          </div>
          <h1 className="text-3xl font-black text-white mb-2">Verify Your Email</h1>
          <p className="text-slate-400">
            We sent a 6-digit code to {email}
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

          {/* OTP Input */}
          <div>
            <label className="block text-slate-200 text-sm font-semibold mb-3">Verification Code</label>
            <input
              type="text"
              value={otp}
              onChange={handleOtpChange}
              placeholder="000000"
              maxLength="6"
              className="w-full text-center text-4xl font-bold bg-white/5 border border-white/10 rounded-lg py-4 text-white placeholder-slate-600 focus:outline-none focus:border-orange-500/40 focus:ring-2 focus:ring-orange-500/20 transition-all tracking-widest"
            />
            <p className="text-xs text-slate-500 mt-2 text-center">
              Enter the code from your email
            </p>
          </div>

          {/* Submit Button */}
          <motion.button
            type="submit"
            disabled={loading || otp.length !== 6}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.99 }}
            className={`w-full py-2.5 rounded-lg font-bold transition-all flex items-center justify-center gap-2 ${
              loading || otp.length !== 6
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
                Verifying...
              </>
            ) : (
              <>
                Verify Email <ArrowRight size={20} />
              </>
            )}
          </motion.button>

          {/* Resend Button */}
          <div>
            <p className="text-center text-slate-400 text-sm mb-3">Didn't receive the code?</p>
            <motion.button
              type="button"
              onClick={handleResendOtp}
              disabled={resendLoading || countdown > 0}
              whileHover={{ scale: countdown === 0 ? 1.02 : 1 }}
              className={`w-full py-2.5 rounded-lg font-semibold transition-all flex items-center justify-center gap-2 ${
                countdown > 0
                  ? 'bg-white/5 text-slate-500 cursor-not-allowed border border-white/10'
                  : 'bg-white/10 hover:bg-white/20 text-slate-300 border border-white/20'
              }`}
            >
              <RefreshCw size={18} />
              {countdown > 0 ? `Resend in ${countdown}s` : 'Resend Code'}
            </motion.button>
          </div>

          {/* Help Text */}
          <div className="text-center pt-4 border-t border-white/10">
            <p className="text-xs text-slate-500">
              OTP expires in 10 minutes. Check your spam folder if you don't see the email.
            </p>
          </div>
        </motion.form>

        {/* Back to Login */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="text-center mt-6"
        >
          <button
            onClick={() => navigate('/login')}
            className="text-slate-400 hover:text-slate-300 text-sm transition"
          >
            ← Back to Log In
          </button>
        </motion.div>
      </motion.div>
    </div>
  );
}
