import React from 'react';
import { motion } from 'framer-motion';
import { useInView } from 'react-intersection-observer';
import { ChevronDown, ArrowRight } from 'lucide-react';

// ===== HERO SECTION =====
function HeroSection() {
  const [ref, inView] = useInView({ threshold: 0.2, triggerOnce: true });
  const canvasRef = React.useRef(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight - 80;

    const particles = Array.from({ length: 60 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      r: Math.random() * 2,
      alpha: Math.random() * 0.3 + 0.1,
    }));

    let animId;
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,107,53,${p.alpha})`;
        ctx.fill();
      });
      animId = requestAnimationFrame(animate);
    };
    animate();
    return () => cancelAnimationFrame(animId);
  }, []);

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
      
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" />

      <div className="absolute inset-0 pointer-events-none">
        <motion.div className="absolute top-1/3 left-1/6 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl" animate={{ scale: [1, 1.3, 1] }} transition={{ duration: 8, repeat: Infinity }} />
        <motion.div className="absolute bottom-1/3 right-1/6 w-80 h-80 bg-orange-600/5 rounded-full blur-3xl" animate={{ scale: [1.2, 1, 1.2] }} transition={{ duration: 10, repeat: Infinity, delay: 3 }} />
      </div>

      <div className="max-w-7xl mx-auto px-6 relative z-10 w-full h-full flex items-center">
        <div className="grid md:grid-cols-2 gap-8 items-center w-full h-full">
          {/* Left Side Text */}
          <div className="w-full">
        <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          <div className="text-orange-500/60 font-mono text-sm tracking-widest mb-3 uppercase">— The Reality</div>
          <h1 className="text-5xl md:text-6xl font-black leading-tight mb-4 text-white">
            Real Estate in Tunisia<br/>
            <span className="text-[#FF6B35]">is Changing</span>
          </h1>
          <p className="text-lg text-gray-300 mb-3">
            But the data is fragmented, opaque, and hard to trust.
          </p>
          <p className="text-gray-400 mb-8 leading-relaxed max-w-lg">
            People make life decisions worth millions based on guesswork. Investors miss opportunities. Entire regions stay invisible.
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            <motion.a 
              href="/explore" 
              className="px-8 py-4 bg-[#FF6B35] text-white font-bold rounded-lg hover:bg-orange-600 transition-all shadow-lg shadow-orange-500/30 flex items-center justify-center gap-2"
              whileHover={{ scale: 1.05, boxShadow: '0 0 30px rgba(255, 107, 53, 0.6)' }}
              whileTap={{ scale: 0.95 }}
            >
              Explore Market <ArrowRight size={20} />
            </motion.a>
            <motion.a 
              href="/community" 
              className="px-8 py-4 border border-[#FF6B35] text-[#FF6B35] font-bold rounded-lg hover:bg-orange-500/10 transition-all flex items-center justify-center gap-2"
              whileHover={{ scale: 1.05, borderColor: '#FFB366' }}
              whileTap={{ scale: 0.95 }}
            >
              Join #Aaref_Bledek
            </motion.a>
          </div>
          </motion.div>
          </div>

          {/* Right Side Image */}
          <motion.div 
            ref={ref}
            initial={{ opacity: 0, x: 100 }} 
            animate={inView ? { opacity: 1, x: 0 } : {}} 
            transition={{ duration: 1, delay: 0.3 }}
            className="w-full pointer-events-none hidden md:flex items-center justify-center"
          >
            <div className="w-full max-w-md h-96 rounded-3xl overflow-hidden shadow-2xl shadow-orange-500/20">
              <img 
                src="/images/hero-tunisia-map.png" 
                alt="Tunisia Map Network" 
                className="w-full h-full object-cover"
              />
            </div>
          </motion.div>
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.2, duration: 0.8 }} className="absolute bottom-10 left-6 lg:bottom-12">
          <motion.div animate={{ y: [0, 10, 0] }} transition={{ duration: 2, repeat: Infinity }}>
            <ChevronDown size={32} className="text-orange-400" />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}

// ===== PROBLEM SECTION =====
function ProblemSection() {
  const [ref, inView] = useInView({ threshold: 0.2, triggerOnce: true });

  const problems = [
    { icon: '🔍', title: 'Price Opacity', desc: 'No reliable price data across regions' },
    { icon: '📊', title: 'Fragmented Data', desc: 'Sources scattered, inconsistent, unreliable' },
    { icon: '⚖️', title: 'Legal Complexity', desc: 'Contracts and compliance unclear' },
    { icon: '🌍', title: 'Regional Invisibility', desc: 'Outside Tunis? Opportunities disappear' },
  ];

  return (
    <section className="relative h-screen flex items-center justify-center py-24 bg-black overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <img 
          src="/images/pattern-tunisia-outline.png" 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>

      <div className="max-w-6xl mx-auto px-6 relative z-10 w-full">
        <motion.div ref={ref} initial={{ opacity: 0, y: 40 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.7 }} className="text-center mb-16">
          <h2 className="text-5xl md:text-6xl font-black text-white mb-4">
            The Market <span className="text-[#FF6B35]">Problem</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">4 critical barriers blocking Tunisia's real estate evolution</p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {problems.map((p, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 50 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.6, delay: i * 0.1 }}
              whileHover={{ scale: 1.03, y: -5, boxShadow: '0 20px 40px rgba(255, 107, 53, 0.2)' }}
              className="bg-gradient-to-br from-red-500/20 to-red-900/5 border border-red-500/30 rounded-xl p-6 hover:border-orange-500/50 transition-all cursor-pointer"
            >
              <motion.div className="text-5xl mb-4" whileHover={{ scale: 1.2, rotate: 5 }}>{p.icon}</motion.div>
              <h3 className="text-white text-xl font-bold mb-2">{p.title}</h3>
              <p className="text-gray-300">{p.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}



// ===== SOLUTION SECTION =====
function SolutionSection() {
  const [ref, inView] = useInView({ threshold: 0.3, triggerOnce: true });

  return (
    <section className="relative min-h-screen flex items-center justify-center py-16 bg-black overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <img 
          src="/images/pattern-data-grid.png" 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>
      <div className="absolute inset-0 pointer-events-none">
        <motion.div className="absolute top-1/3 right-1/4 w-96 h-96 bg-orange-500/8 rounded-full blur-3xl" animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 8, repeat: Infinity }} />
      </div>

      <div className="max-w-6xl mx-auto px-6 relative z-10 w-full">
        <motion.div ref={ref} initial={{ opacity: 0, y: 40 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.8 }}>
          <div className="text-center mb-12">
            <div className="text-orange-500/60 font-mono text-sm tracking-widest mb-3 uppercase">— Solution</div>
            <h2 className="text-5xl md:text-6xl font-black text-white mb-3">
              <span className="text-[#FF6B35]">Introducing</span> EstateMind
            </h2>
            <p className="text-lg text-gray-400 max-w-2xl mx-auto">
              An AI-powered platform turning fragmented data into clear, actionable decisions
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 mb-10">
            <motion.div 
              initial={{ opacity: 0, y: 20 }} 
              animate={inView ? { opacity: 1, y: 0 } : {}} 
              transition={{ delay: 0.1 }} 
              whileHover={{ scale: 1.04, y: -8, borderColor: '#FFB366' }}
              className="bg-gradient-to-br from-orange-500/20 to-orange-900/10 border border-orange-500/30 rounded-xl p-6 cursor-pointer transition-all"
            >
              <motion.div className="text-5xl mb-4" whileHover={{ scale: 1.3, rotate: -5 }}>🗺️</motion.div>
              <h3 className="text-white font-bold text-lg mb-2">Unified Explorer</h3>
              <p className="text-gray-300 text-sm leading-relaxed">Every property, every region, one powerful platform</p>
            </motion.div>
            <motion.div 
              initial={{ opacity: 0, y: 20 }} 
              animate={inView ? { opacity: 1, y: 0 } : {}} 
              transition={{ delay: 0.15 }} 
              whileHover={{ scale: 1.04, y: -8, borderColor: '#FFB366' }}
              className="bg-gradient-to-br from-orange-500/20 to-orange-900/10 border border-orange-500/30 rounded-xl p-6 cursor-pointer transition-all"
            >
              <motion.div className="text-5xl mb-4" whileHover={{ scale: 1.3, rotate: 5 }}>🤖</motion.div>
              <h3 className="text-white font-bold text-lg mb-2">AI Valuation</h3>
              <p className="text-gray-300 text-sm leading-relaxed">Accurate prices powered by machine learning</p>
            </motion.div>
            <motion.div 
              initial={{ opacity: 0, y: 20 }} 
              animate={inView ? { opacity: 1, y: 0 } : {}} 
              transition={{ delay: 0.2 }} 
              whileHover={{ scale: 1.04, y: -8, borderColor: '#FFB366' }}
              className="bg-gradient-to-br from-orange-500/20 to-orange-900/10 border border-orange-500/30 rounded-xl p-6 cursor-pointer transition-all"
            >
              <motion.div className="text-5xl mb-4" whileHover={{ scale: 1.3, rotate: -5 }}>⚖️</motion.div>
              <h3 className="text-white font-bold text-lg mb-2">Legal Assistant</h3>
              <p className="text-gray-300 text-sm leading-relaxed">Contracts and compliance made simple</p>
            </motion.div>
          </div>

          <div className="text-center">
            <motion.a 
              href="/explore" 
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.3 }}
              whileHover={{ scale: 1.05, boxShadow: '0 0 30px rgba(255, 107, 53, 0.6)' }}
              whileTap={{ scale: 0.95 }}
              className="inline-block px-10 py-4 bg-[#FF6B35] text-white font-bold rounded-lg hover:bg-orange-600 transition-all shadow-lg shadow-orange-500/30"
            >
              Start Exploring <ArrowRight size={20} className="inline ml-2" />
            </motion.a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ===== FEATURES SECTION =====
function FeaturesSection() {
  const [ref, inView] = useInView({ threshold: 0.3, triggerOnce: true });
  const bgPatterns = [
    "/images/pattern-tunisia-outline.png"
  ];
  
  const featureModules = [
    {
      icon: "🔍",
      title: "Explore Properties",
      desc: "Interactive map with real-time property data",
      image: "/images/explore_property_module.png"
    },
    {
      icon: "💰",
      title: "AI Price Prediction",
      desc: "Accurate valuations with explainable AI",
      image: "/images/property_valuation_module.png"
    },
    {
      icon: "📊",
      title: "Market Insights",
      desc: "Track trends and investment opportunities",
      image: "/images/market_track_module.png"
    },
    {
      icon: "⚖️",
      title: "Legal Guidance",
      desc: "Tunisian real estate law at your fingertips",
      image: "/images/legal_assistant_module.png"
    }
  ];

  return (
    <section className="relative h-screen flex flex-col items-center justify-center py-16 bg-gradient-to-b from-black via-slate-950 to-black overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <img 
          src={bgPatterns[0]} 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>

      <div className="max-w-7xl mx-auto px-6 relative z-10 w-full h-full flex flex-col">
        {/* Header */}
        <motion.div ref={ref} initial={{ opacity: 0, y: 20 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.6 }} className="text-center mb-2">
          <h2 className="text-4xl md:text-5xl font-black text-white mb-2">
            What You Can <span className="text-[#FF6B35]">Do</span>
          </h2>
          <p className="text-gray-400 text-sm md:text-base max-w-2xl mx-auto">
            Four powerful modules working together to transform your real estate decisions
          </p>
        </motion.div>

        {/* Cards Grid - 4 columns, compact */}
        <div className="flex-grow flex items-center justify-center w-full">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 w-full">
            {featureModules.map((module, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                whileHover={{ scale: 1.04, y: -4, borderColor: '#FFB366', boxShadow: '0 15px 35px rgba(255, 107, 53, 0.15)' }}
                className="group flex flex-col overflow-hidden rounded-xl border border-orange-500/20 bg-gradient-to-br from-slate-900/50 to-slate-950/50 hover:border-orange-500/60 transition-all duration-300 h-full cursor-pointer"
              >
                {/* Image Container - Smaller */}
                <div className="relative h-32 overflow-hidden bg-slate-900 flex-shrink-0">
                  <img 
                    src={module.image} 
                    alt={module.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent" />
                </div>

                {/* Content */}
                <div className="p-3 flex-grow flex flex-col">
                  <div className="text-xl mb-1">{module.icon}</div>
                  <h3 className="text-white font-bold text-sm md:text-sm mb-1 group-hover:text-[#FF6B35] transition-colors line-clamp-2">
                    {module.title}
                  </h3>
                  <p className="text-gray-400 text-xs leading-tight flex-grow line-clamp-2">
                    {module.desc}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="text-center mt-auto pt-1">
          <motion.a 
            href="/explore"
            initial={{ opacity: 0, y: 10 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.4 }}
            className="inline-block px-6 py-3 bg-[#FF6B35] text-white font-bold text-sm md:text-base rounded-lg hover:bg-orange-600 transition-all shadow-lg shadow-orange-500/30"
            whileHover={{ scale: 1.05, boxShadow: '0 0 25px rgba(255, 107, 53, 0.6)' }}
            whileTap={{ scale: 0.95 }}
          >
            Explore All Features <ArrowRight size={18} className="inline ml-2" />
          </motion.a>
        </div>
      </div>
    </section>
  );
}

// ===== HOW IT WORKS SECTION =====
function HowItWorksSection() {
  const [ref, inView] = useInView({ threshold: 0.2, triggerOnce: true });

  const steps = [
    { num: '1', title: 'Explore', desc: 'Browse properties and market trends across Tunisia' },
    { num: '2', title: 'Analyze', desc: 'Get AI-powered insights and accurate valuations' },
    { num: '3', title: 'Decide', desc: 'Make informed decisions with complete data' },
    { num: '4', title: 'Optimize', desc: 'Track and manage your real estate portfolio' },
  ];

  return (
    <section className="relative h-screen flex items-center justify-center py-24 bg-black overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <img 
          src="/images/testimonials-background.png" 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>
      <div className="max-w-6xl mx-auto px-6 relative z-10 w-full">
        <motion.div ref={ref} initial={{ opacity: 0, y: 40 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.7 }} className="text-center mb-16">
          <h2 className="text-5xl md:text-6xl font-black text-white mb-4">
            The <span className="text-[#FF6B35]">Simple Flow</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">4 steps from question to confidence</p>
        </motion.div>

        <div className="grid md:grid-cols-4 gap-6">
          {steps.map((step, i) => (
            <div key={i}>
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={inView ? { opacity: 1, scale: 1 } : {}}
                transition={{ duration: 0.6, delay: i * 0.1 }}
                whileHover={{ scale: 1.2, boxShadow: '0 20px 40px rgba(255, 107, 53, 0.4)' }}
                className="bg-gradient-to-br from-orange-500/30 to-orange-900/10 border border-orange-500/30 rounded-full w-20 h-20 flex items-center justify-center mb-4 cursor-pointer transition-all"
              >
                <span className="text-3xl font-black text-[#FF6B35]">{step.num}</span>
              </motion.div>
              <h3 className="text-white font-bold text-lg mb-2">{step.title}</h3>
              <p className="text-gray-400 text-sm">{step.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ===== USE CASES SECTION =====
function UseCasesSection() {
  const [ref, inView] = useInView({ threshold: 0.2, triggerOnce: true });

  const users = [
    { emoji: '🧑‍💼', title: 'Buyers', desc: 'Find the right property at the right price' },
    { emoji: '💰', title: 'Investors', desc: 'Identify opportunities and track returns' },
    { emoji: '🏢', title: 'Agencies', desc: 'Streamline listings and valuations' },
    { emoji: '🏛️', title: 'Institutions', desc: 'Access market data and insights' },
  ];

  return (
    <section className="relative h-screen flex items-center justify-center py-24 bg-gradient-to-b from-black to-[#0d1520] overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <img 
          src="/images/pattern-data-grid.png" 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>
      <div className="max-w-6xl mx-auto px-6 relative z-10 w-full">
        <motion.div ref={ref} initial={{ opacity: 0, y: 40 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.7 }} className="text-center mb-16">
          <h2 className="text-5xl md:text-6xl font-black text-white mb-4">
            Built for <span className="text-[#FF6B35]">Everyone</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">Different users, one powerful platform</p>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {users.map((u, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.6, delay: i * 0.1 }}
              whileHover={{ scale: 1.05, y: -8, borderColor: '#FF6B35', boxShadow: '0 20px 40px rgba(255, 107, 53, 0.2)' }}
              className="bg-white/5 border border-white/10 rounded-xl p-6 hover:border-orange-500/50 hover:bg-white/10 transition-all text-center cursor-pointer"
            >
              <motion.div className="text-5xl mb-4" whileHover={{ scale: 1.2, rotate: 10 }}>{u.emoji}</motion.div>
              <h3 className="text-white font-bold text-lg mb-2">{u.title}</h3>
              <p className="text-gray-400">{u.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ===== AAREF BLEDEK SECTION =====
function AarefBledekSection() {
  const [ref, inView] = useInView({ threshold: 0.2, triggerOnce: true });

  return (
    <section className="relative h-screen flex items-center justify-center py-24 bg-black overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <img 
          src="/images/pattern-tunisia-outline.png" 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>
      <div className="absolute inset-0 pointer-events-none">
        <motion.div className="absolute top-1/4 right-1/4 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl" animate={{ scale: [1, 1.3, 1] }} transition={{ duration: 8, repeat: Infinity }} />
      </div>

      <div className="max-w-5xl mx-auto px-6 relative z-10 w-full">
        <motion.div ref={ref} initial={{ opacity: 0, y: 40 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.8 }} className="text-center">
          <div className="text-orange-500/60 font-mono text-sm tracking-widest mb-4 uppercase">— Movement</div>
          <h2 className="text-5xl md:text-6xl font-black text-white mb-4">
            Join the <span className="text-[#FF6B35]">#Aaref_Bledek</span> Movement
          </h2>
          <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
            Help build Tunisia's real estate knowledge network.
          </p>

          <div className="grid md:grid-cols-4 gap-4 mb-12">
            {[
              { emoji: '📚', label: 'Learners', count: '200+' },
              { emoji: '✍️', label: 'Contributors', count: '80+' },
              { emoji: '🤝', label: 'Volunteers', count: '40+' },
              { emoji: '🌟', label: 'Ambassadors', count: '24' },
            ].map((role, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={inView ? { opacity: 1, scale: 1 } : {}}
                transition={{ duration: 0.6, delay: i * 0.1 }}
                whileHover={{ scale: 1.05, y: -6, borderColor: '#FFB366', boxShadow: '0 15px 35px rgba(255, 107, 53, 0.25)' }}
                className="bg-gradient-to-br from-orange-500/20 to-orange-900/10 border border-orange-500/30 rounded-xl p-6 cursor-pointer transition-all"
              >
                <motion.div className="text-4xl mb-2" whileHover={{ scale: 1.2, rotate: -5 }}>{role.emoji}</motion.div>
                <div className="text-orange-400 font-bold text-2xl">{role.count}</div>
                <div className="text-white text-sm mt-1">{role.label}</div>
              </motion.div>
            ))}
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <motion.a 
              href="/community" 
              className="px-8 py-4 bg-[#FF6B35] text-white font-bold rounded-lg hover:bg-orange-600 transition-all shadow-lg shadow-orange-500/30 flex items-center justify-center gap-2"
              whileHover={{ scale: 1.05, boxShadow: '0 0 30px rgba(255, 107, 53, 0.6)' }}
              whileTap={{ scale: 0.95 }}
            >
              Join Campaign <ArrowRight size={20} />
            </motion.a>
            <motion.a 
              href="/community" 
              className="px-8 py-4 border border-[#FF6B35] text-[#FF6B35] font-bold rounded-lg hover:bg-orange-500/10 transition-all"
              whileHover={{ scale: 1.05, borderColor: '#FFB366' }}
              whileTap={{ scale: 0.95 }}
            >
              Join Community
            </motion.a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ===== TRUST SECTION =====
function TrustSection() {
  const [ref, inView] = useInView({ threshold: 0.2, triggerOnce: true });

  const stats = [
    { label: '20+ Data Sources', value: '✓' },
    { label: 'AI-Powered Model', value: '94%' },
    { label: 'Explainable AI', value: '✓' },
    { label: 'Local Adaptation', value: '24' },
  ];

  return (
    <section className="relative h-screen flex items-center justify-center py-24 bg-gradient-to-b from-black to-[#0d1520] overflow-hidden">
      {/* Background Image */}
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <img 
          src="/images/pattern-data-grid.png" 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>

      <div className="max-w-6xl mx-auto px-6 relative z-10 w-full">
        <motion.div ref={ref} initial={{ opacity: 0, y: 40 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.7 }} className="text-center mb-16">
          <h2 className="text-5xl md:text-6xl font-black text-white mb-4">
            Built on <span className="text-[#FF6B35]">Trust</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">Credibility through transparency and explainability</p>
        </motion.div>

        <div className="grid md:grid-cols-4 gap-6">
          {stats.map((stat, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.6, delay: i * 0.1 }}
              whileHover={{ scale: 1.05, y: -6, borderColor: '#FF6B35', boxShadow: '0 20px 40px rgba(255, 107, 53, 0.2)' }}
              className="bg-white/5 border border-white/10 rounded-xl p-8 text-center hover:border-orange-500/50 transition-all backdrop-blur-sm cursor-pointer"
            >
              <motion.div className="text-4xl font-black text-[#FF6B35] mb-2" whileHover={{ scale: 1.15, color: '#FFB366' }}>{stat.value}</motion.div>
              <div className="text-white font-semibold">{stat.label}</div>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ duration: 0.8, delay: 0.5 }}
          className="mt-16 text-center max-w-2xl mx-auto"
        >
          <p className="text-gray-300 text-lg leading-relaxed">
            Every valuation is explained. Every data point is sourced. Every recommendation is auditable. 
            We believe in <span className="text-orange-400 font-semibold">transparent AI</span> for real estate.
          </p>
        </motion.div>
      </div>
    </section>
  );
}

// ===== FINAL CTA SECTION =====
function FinalCTASection() {
  const [ref, inView] = useInView({ threshold: 0.3, triggerOnce: true });

  return (
    <section className="relative h-screen flex items-center justify-center py-24 bg-black overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <img 
          src="/images/pattern-tunisia-outline.png" 
          alt="" 
          className="w-full h-full object-cover"
        />
      </div>
      <div className="absolute inset-0 pointer-events-none">
        <motion.div className="absolute inset-0 bg-gradient-to-b from-orange-500/10 via-transparent to-transparent" animate={{ opacity: [0.3, 0.6, 0.3] }} transition={{ duration: 8, repeat: Infinity }} />
      </div>

      <div className="max-w-3xl mx-auto px-6 relative z-10 text-center">
        <motion.div ref={ref} initial={{ opacity: 0, y: 40 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.8 }}>
          <h2 className="text-6xl md:text-7xl font-black text-white mb-6 leading-tight">
            Start Making Smarter<br/>
            <span className="text-[#FF6B35]">Real Estate Decisions</span>
          </h2>
          <p className="text-xl text-gray-300 mb-12 max-w-xl mx-auto">
            Join thousands of buyers, investors, and professionals using EstateMind to transform how they think about real estate.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <motion.a 
              href="/explore" 
              className="px-10 py-4 bg-[#FF6B35] text-white font-bold rounded-lg hover:bg-orange-600 transition-all shadow-2xl shadow-orange-500/40 flex items-center justify-center gap-2"
              whileHover={{ scale: 1.08, boxShadow: '0 0 40px rgba(255, 107, 53, 0.8)' }}
              whileTap={{ scale: 0.95 }}
            >
              Explore Platform <ArrowRight size={20} />
            </motion.a>
            <motion.a 
              href="/community" 
              className="px-10 py-4 border border-[#FF6B35] text-[#FF6B35] font-bold rounded-lg hover:bg-orange-500/10 transition-all"
              whileHover={{ scale: 1.08, borderColor: '#FFB366' }}
              whileTap={{ scale: 0.95 }}
            >
              Join Community
            </motion.a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ===== MAIN COMPONENT =====
export default function HomePage() {
  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden">
      <HeroSection />
      <ProblemSection />
      <SolutionSection />
      <FeaturesSection />
      <HowItWorksSection />
      <UseCasesSection />
      <AarefBledekSection />
      <TrustSection />
      <FinalCTASection />
    </div>
  );
}
