import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useInView } from 'react-intersection-observer';
import api from '../../services/api';

const ROLES = [
  { value: 'learner',     label: '📚 Learner',     desc: 'Learn and grow my knowledge' },
  { value: 'contributor', label: '✍️ Contributor', desc: 'Contribute data and content' },
  { value: 'volunteer',   label: '🤝 Volunteer',   desc: 'Organise events in my region' },
  { value: 'ambassador',  label: '🌟 Ambassador',  desc: 'Lead the community in my governorate' },
];

const GOVERNORATES = [
  'Tunis', 'Ariana', 'Ben Arous', 'Manouba', 'Nabeul', 'Zaghouan', 'Bizerte',
  'Beja', 'Jendouba', 'El Kef', 'Siliana', 'Sousse', 'Monastir', 'Mahdia',
  'Sfax', 'Kairouan', 'Kasserine', 'Sidi Bouzid', 'Gabes', 'Medenine',
  'Tataouine', 'Gafsa', 'Tozeur', 'Kebili',
];

function ProgressBar({ step }) {
  const labels = ['Personal Info', 'Region & Role', 'Motivation'];
  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        {[1, 2, 3].map((s) => (
          <React.Fragment key={s}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${
              step >= s ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : 'bg-white/10 text-gray-500'
            }`}>
              {step > s ? '✓' : s}
            </div>
            {s < 3 && <div className={`flex-1 h-0.5 transition-all duration-500 ${step > s ? 'bg-orange-500' : 'bg-white/10'}`} />}
          </React.Fragment>
        ))}
      </div>
      <p className="text-xs text-gray-500">Step {step} of 3 — {labels[step - 1]}</p>
    </div>
  );
}

function RegistrationModal({ isOpen, onClose, preselectedRole }) {
  const [step, setStep]       = useState(1);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errors, setErrors]   = useState({});
  const [formData, setFormData] = useState({
    full_name: '', email: '', phone: '', region: '', role: preselectedRole || '', motivation: '',
  });

  useEffect(() => {
    if (preselectedRole) setFormData(prev => ({ ...prev, role: preselectedRole }));
  }, [preselectedRole]);

  const validate = () => {
    const e = {};
    if (step === 1) {
      if (!formData.full_name.trim()) e.full_name = 'Full name is required';
      if (!formData.email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) e.email = 'Please enter a valid email address';
      const phone = formData.phone.replace(/\s/g, '');
      if (!phone.match(/^(\+216)?[0-9]{8}$/)) e.phone = 'Please enter a valid Tunisian phone number (8 digits)';
    }
    if (step === 2) {
      if (!formData.region) e.region = 'Please select your governorate';
      if (!formData.role)   e.role   = 'Please select your role';
    }
    if (step === 3) {
      if (formData.motivation.trim().length < 20) e.motivation = 'Please write at least 20 characters';
    }
    return e;
  };

  const handleNext = () => {
    const e = validate();
    if (Object.keys(e).length > 0) { setErrors(e); return; }
    setErrors({});
    setStep(s => s + 1);
  };

  const handleSubmit = async () => {
    const e = validate();
    if (Object.keys(e).length > 0) { setErrors(e); return; }
    setLoading(true);
    try {
      await api.post('/campaign/participants/', formData);
      setSuccess(true);
    } catch (err) {
      const apiErrors = err?.response?.data?.errors;
      setErrors(apiErrors || { general: 'Something went wrong, please try again' });
      setStep(1);
    } finally {
      setLoading(false);
    }
  };

  const set = (field) => (e) => {
    setFormData(prev => ({ ...prev, [field]: e.target.value }));
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: '' }));
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)' }}
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0, y: 40 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.9, opacity: 0, y: 40 }}
          transition={{ type: 'spring', damping: 20, stiffness: 300 }}
          className="w-full max-w-lg bg-gray-950 border border-white/10 rounded-3xl overflow-hidden shadow-2xl"
        >
          {success ? (
            /* Success screen */
            <div className="p-8 text-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', delay: 0.1, stiffness: 200 }}
                className="mb-6 relative"
              >
                <img
                  src="/images/join-success-celebration.png"
                  alt="Success"
                  className="w-full h-48 object-cover rounded-2xl"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-gray-950 via-transparent to-transparent rounded-2xl" />
                <motion.div
                  className="absolute bottom-4 left-1/2 -translate-x-1/2"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  <span className="text-5xl">🎉</span>
                </motion.div>
              </motion.div>
              <h3 className="text-2xl font-black text-white mb-2">
                Welcome to{' '}
                <span className="gradient-text">#Aaref_Bledek</span>!
              </h3>
              <p className="text-gray-400 mb-6">
                You have been successfully registered. Check your email for confirmation shortly.
              </p>
              <motion.button
                onClick={onClose}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="px-8 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-xl font-semibold transition-all"
              >
                Awesome — Let us get started! 🚀
              </motion.button>
            </div>
          ) : (
            /* Form */
            <div>
              {/* Header */}
              <div className="p-6 border-b border-white/10 flex items-center justify-between">
                <div>
                  <h3 className="text-white font-black text-lg">
                    Join{' '}
                    <span className="gradient-text">#Aaref_Bledek</span>
                  </h3>
                  <p className="text-gray-500 text-sm">Step {step} of 3</p>
                </div>
                <button
                  onClick={onClose}
                  className="text-gray-500 hover:text-white w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 transition-all text-xl"
                >
                  ×
                </button>
              </div>

              <div className="p-6">
                <ProgressBar step={step} />

                {errors.general && (
                  <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
                    {errors.general}
                  </div>
                )}

                <AnimatePresence mode="wait">
                  {step === 1 && (
                    <motion.div
                      key="step1"
                      initial={{ opacity: 0, x: 30 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -30 }}
                      className="space-y-4"
                    >
                      <h4 className="text-white font-semibold text-sm mb-4">Your Personal Information</h4>
                      <div>
                        <input
                          type="text"
                          value={formData.full_name}
                          onChange={set('full_name')}
                          placeholder="Full name"
                          className={`w-full bg-white/5 border ${errors.full_name ? 'border-red-500/50' : 'border-white/10'} rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-orange-500/50 transition-all`}
                        />
                        {errors.full_name && <p className="text-red-400 text-xs mt-1">{errors.full_name}</p>}
                      </div>
                      <div>
                        <input
                          type="email"
                          value={formData.email}
                          onChange={set('email')}
                          placeholder="Email address"
                          className={`w-full bg-white/5 border ${errors.email ? 'border-red-500/50' : 'border-white/10'} rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-orange-500/50 transition-all`}
                        />
                        {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email}</p>}
                      </div>
                      <div>
                        <input
                          type="tel"
                          value={formData.phone}
                          onChange={set('phone')}
                          placeholder="Phone number (e.g. 20123456)"
                          className={`w-full bg-white/5 border ${errors.phone ? 'border-red-500/50' : 'border-white/10'} rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-orange-500/50 transition-all`}
                        />
                        {errors.phone && <p className="text-red-400 text-xs mt-1">{errors.phone}</p>}
                      </div>
                    </motion.div>
                  )}

                  {step === 2 && (
                    <motion.div
                      key="step2"
                      initial={{ opacity: 0, x: 30 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -30 }}
                      className="space-y-4"
                    >
                      <h4 className="text-white font-semibold text-sm mb-4">Your Governorate & Role</h4>
                      <div>
                        <select
                          value={formData.region}
                          onChange={set('region')}
                          className={`w-full bg-gray-900 border ${errors.region ? 'border-red-500/50' : 'border-white/10'} rounded-xl px-4 py-3 text-white focus:outline-none focus:border-orange-500/50 transition-all`}
                        >
                          <option value="">Select your governorate</option>
                          {GOVERNORATES.map(g => <option key={g} value={g}>{g}</option>)}
                        </select>
                        {errors.region && <p className="text-red-400 text-xs mt-1">{errors.region}</p>}
                      </div>
                      <div>
                        <p className="text-gray-400 text-sm mb-3">Choose your role in the campaign:</p>
                        <div className="grid grid-cols-2 gap-3">
                          {ROLES.map(r => (
                            <button
                              key={r.value}
                              type="button"
                              onClick={() => { setFormData(prev => ({ ...prev, role: r.value })); if (errors.role) setErrors(prev => ({ ...prev, role: '' })); }}
                              className={`p-3 rounded-xl border text-left transition-all duration-200 ${
                                formData.role === r.value
                                  ? 'bg-orange-500/20 border-orange-500 text-orange-300'
                                  : 'bg-white/5 border-white/10 text-gray-400 hover:border-white/30'
                              }`}
                            >
                              <div className="font-semibold text-sm">{r.label}</div>
                              <div className="text-xs opacity-70 mt-0.5">{r.desc}</div>
                            </button>
                          ))}
                        </div>
                        {errors.role && <p className="text-red-400 text-xs mt-1">{errors.role}</p>}
                      </div>
                    </motion.div>
                  )}

                  {step === 3 && (
                    <motion.div
                      key="step3"
                      initial={{ opacity: 0, x: 30 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -30 }}
                    >
                      <h4 className="text-white font-semibold text-sm mb-4">Why are you joining the campaign?</h4>
                      <div className="mb-2">
                        <textarea
                          value={formData.motivation}
                          onChange={set('motivation')}
                          rows={5}
                          placeholder="Tell us about your motivation and expected contribution... (at least 20 characters)"
                          className={`w-full bg-white/5 border ${errors.motivation ? 'border-red-500/50' : 'border-white/10'} rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-orange-500/50 transition-all resize-none`}
                        />
                        <div className="flex justify-between mt-1">
                          {errors.motivation && <p className="text-red-400 text-xs">{errors.motivation}</p>}
                          <p className="text-gray-600 text-xs ml-auto">{formData.motivation.length} characters</p>
                        </div>
                      </div>
                      {/* Summary */}
                      <div className="mt-4 glass-card rounded-xl p-4 text-sm space-y-2">
                        <p className="text-gray-500 text-xs mb-2">Your registration summary:</p>
                        <div className="flex justify-between text-gray-300">
                          <span className="text-gray-500">Name:</span>
                          <span>{formData.full_name}</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span className="text-gray-500">Governorate:</span>
                          <span>{formData.region}</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span className="text-gray-500">Role:</span>
                          <span>{ROLES.find(r => r.value === formData.role)?.label || '—'}</span>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Navigation buttons */}
                <div className="flex gap-3 mt-6">
                  {step > 1 && (
                    <button
                      onClick={() => setStep(s => s - 1)}
                      className="px-5 py-3 bg-white/5 border border-white/10 text-gray-400 hover:text-white rounded-xl font-medium transition-all"
                    >
                      ← Back
                    </button>
                  )}
                  {step < 3 ? (
                    <motion.button
                      onClick={handleNext}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      className="flex-1 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-xl font-semibold transition-all shadow-lg shadow-orange-500/20"
                    >
                      Next →
                    </motion.button>
                  ) : (
                    <motion.button
                      onClick={handleSubmit}
                      disabled={loading}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      className={`flex-1 py-3 rounded-xl font-bold transition-all shadow-lg ${
                        loading
                          ? 'bg-orange-500/50 text-white/50 cursor-not-allowed'
                          : 'bg-orange-500 hover:bg-orange-600 text-white shadow-orange-500/20'
                      }`}
                    >
                      {loading ? (
                        <span className="flex items-center justify-center gap-2">
                          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                          Registering...
                        </span>
                      ) : '🚀 Register Now!'}
                    </motion.button>
                  )}
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

export default function JoinSection({ isModalOpen, onOpenModal, onCloseModal, preselectedRole }) {
  const [ref, inView] = useInView({ threshold: 0.2, triggerOnce: true });

  return (
    <>
      <section
        id="join"
        className="section-full py-24 relative overflow-hidden"
        style={{ background: 'linear-gradient(160deg, #0b1d35 0%, #0e2347 50%, #0b1d35 100%)' }}
      >
        {/* Background pattern */}
        <div
          className="absolute inset-0 pointer-events-none opacity-10"
          style={{ backgroundImage: `url('/images/pattern-data-grid.png')`, backgroundSize: '80px 80px' }}
        />
        {/* Animated orbs */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <motion.div
            className="absolute -top-32 -right-32 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl"
            animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.5, 0.3] }}
            transition={{ duration: 6, repeat: Infinity }}
          />
          <motion.div
            className="absolute -bottom-32 -left-32 w-80 h-80 bg-orange-500/8 rounded-full blur-3xl"
            animate={{ scale: [1.2, 1, 1.2], opacity: [0.2, 0.4, 0.2] }}
            transition={{ duration: 8, repeat: Infinity, delay: 2 }}
          />
        </div>

        <div className="max-w-6xl mx-auto px-6 relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            {/* Left: Goal image */}
            <motion.div
              initial={{ opacity: 0, x: -60 }}
              animate={inView ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.8 }}
            >
              <div className="relative rounded-3xl overflow-hidden">
                <img
                  src="/images/impact-building-future.png"
                  alt="1,000 Members Goal"
                  className="w-full h-72 lg:h-[520px] object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/20 to-transparent" />
                <div className="absolute bottom-0 left-0 p-8">
                  <p className="text-orange-400 text-sm font-semibold mb-3 uppercase tracking-widest">Our Goal</p>
                  <h3 className="text-white text-3xl lg:text-4xl font-black leading-tight">
                    1,000 Members<br />in the First 3 Months
                  </h3>
                </div>
              </div>
            </motion.div>

            {/* Right: Join content */}
            <motion.div
              ref={ref}
              initial={{ opacity: 0, x: 60 }}
              animate={inView ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="flex flex-col items-start"
            >
              <h2
                className="text-5xl md:text-6xl font-black text-white mb-6 leading-tight"
                style={{ fontFamily: 'Poppins, sans-serif' }}
              >
                Ready?
                <br />
                <span className="gradient-text">Join Now</span>
              </h2>

              <p className="text-xl text-gray-300 mb-4 leading-relaxed">
                Be part of the community that will change how Tunisia understands its real estate market.
              </p>

              {/* Main CTA */}
              <motion.button
                onClick={onOpenModal}
                whileHover={{ scale: 1.05, boxShadow: '0 30px 80px rgba(255,107,53,0.5)' }}
                whileTap={{ scale: 0.95 }}
                className="px-12 py-5 bg-gradient-to-r from-orange-500 to-orange-600 text-white rounded-2xl text-xl font-black shadow-2xl shadow-orange-500/30 transition-all duration-300 mb-10"
              >
                🚀 Join #Aaref_Bledek
              </motion.button>

              {/* Social links */}
              <div className="flex flex-wrap gap-3">
                {/* Facebook */}
                <div className="glass-card border border-white/10 rounded-xl px-5 py-3 flex items-center gap-3 cursor-pointer hover:border-blue-500/40 hover:bg-blue-500/5 transition-all duration-300">
                  <svg className="w-7 h-7 flex-shrink-0" viewBox="0 0 24 24">
                    <path fill="#1877F2" d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                </div>
                {/* Instagram */}
                <div className="glass-card border border-white/10 rounded-xl px-5 py-3 flex items-center gap-3 cursor-pointer hover:border-pink-500/40 hover:bg-pink-500/5 transition-all duration-300">
                  <svg className="w-7 h-7 flex-shrink-0" viewBox="0 0 24 24">
                    <defs>
                      <linearGradient id="ig-grad" x1="0%" y1="100%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#f09433"/>
                        <stop offset="25%" stopColor="#e6683c"/>
                        <stop offset="50%" stopColor="#dc2743"/>
                        <stop offset="75%" stopColor="#cc2366"/>
                        <stop offset="100%" stopColor="#bc1888"/>
                      </linearGradient>
                    </defs>
                    <path fill="url(#ig-grad)" d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                  </svg>
                </div>
                {/* YouTube */}
                <div className="glass-card border border-white/10 rounded-xl px-5 py-3 flex items-center gap-3 cursor-pointer hover:border-red-500/40 hover:bg-red-500/5 transition-all duration-300">
                  <svg className="w-7 h-7 flex-shrink-0" viewBox="0 0 24 24">
                    <path fill="#FF0000" d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                  </svg>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      <RegistrationModal
        isOpen={isModalOpen}
        onClose={onCloseModal}
        preselectedRole={preselectedRole}
      />
    </>
  );
}
