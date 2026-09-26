import React, { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';

export default function HeroSection({ onJoinClick }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const particles = Array.from({ length: 100 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 2.5 + 0.5,
      alpha: Math.random() * 0.4 + 0.1,
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
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 130) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(255,107,53,${0.12 * (1 - dist / 130)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }
      animId = requestAnimationFrame(animate);
    };
    animate();
    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <section
      id="hero"
      className="relative min-h-screen flex items-center overflow-hidden bg-black"
    >
      {/* Particle canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none z-0" />

      {/* Data grid pattern overlay */}
      <div
        className="absolute inset-0 pointer-events-none z-0 opacity-10"
        style={{
          backgroundImage: "url('/images/pattern-data-grid.png')",
          backgroundSize: '80px 80px',
        }}
      />

      {/* Ambient glow orbs */}
      <div className="absolute inset-0 pointer-events-none z-0">
        <motion.div
          className="absolute top-1/4 left-1/6 w-[500px] h-[500px] bg-orange-500/8 rounded-full blur-3xl"
          animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 8, repeat: Infinity }}
        />
        <motion.div
          className="absolute bottom-1/4 right-1/6 w-96 h-96 bg-orange-600/5 rounded-full blur-3xl"
          animate={{ scale: [1.2, 1, 1.2], opacity: [0.2, 0.4, 0.2] }}
          transition={{ duration: 10, repeat: Infinity, delay: 3 }}
        />
      </div>

      {/* Main layout: left text + right images */}
      <div className="relative z-10 w-full max-w-7xl mx-auto px-6 lg:px-10 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center min-h-screen py-24">

        {/* LEFT: Text content */}
        <div className="flex flex-col justify-center">

          {/* Campaign hashtag */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
          >
            <div className="text-orange-500/50 font-mono text-sm tracking-widest mb-2 uppercase">
              — Campaign 2026
            </div>
            <h1
              className="text-5xl md:text-7xl font-black leading-none mb-2"
              style={{ fontFamily: 'Poppins, sans-serif' }}
            >
              <span className="gradient-text">#Aaref_Bledek</span>
            </h1>
          </motion.div>

          {/* Divider */}
          <motion.div
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ duration: 0.8, delay: 0.5 }}
            className="h-px w-24 bg-gradient-to-r from-orange-500 to-transparent my-6"
          />

          {/* Description */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="text-gray-300 text-lg leading-relaxed mb-4 max-w-md"
          >
            The AI-powered real estate intelligence platform mapping
            every property opportunity across Tunisia's{' '}
            <span className="text-orange-400 font-semibold">24 governorates</span>.
          </motion.p>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.7 }}
            className="text-gray-500 text-base leading-relaxed mb-10 max-w-md"
          >
            Join a community of learners, contributors, and ambassadors
            turning open data into real estate intelligence.
          </motion.p>

          {/* CTA buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.85 }}
            className="flex flex-wrap gap-4"
          >
            <motion.button
              onClick={onJoinClick}
              whileHover={{ scale: 1.05, boxShadow: '0 20px 60px rgba(255,107,53,0.45)' }}
              whileTap={{ scale: 0.96 }}
              className="group px-8 py-4 bg-gradient-to-r from-orange-500 to-orange-600 text-white rounded-2xl text-base font-bold shadow-xl shadow-orange-500/25 transition-all duration-300 flex items-center gap-2"
            >
              <span>Join the Campaign</span>
              <motion.span
                animate={{ x: [0, 4, 0] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                →
              </motion.span>
            </motion.button>
            <motion.button
              onClick={() => document.getElementById('problem')?.scrollIntoView({ behavior: 'smooth' })}
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
              className="px-8 py-4 bg-white/5 hover:bg-white/10 border border-white/15 hover:border-orange-500/40 text-white rounded-2xl text-base font-semibold backdrop-blur-sm transition-all duration-300"
            >
              Explore More ↓
            </motion.button>
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.1 }}
            className="mt-12 flex gap-8"
          >
            {[
              { n: '24', label: 'Governorates' },
              { n: '264', label: 'Municipalities' },
              { n: '∞', label: 'Opportunities' },
            ].map(({ n, label }, i) => (
              <div key={label} className="relative">
                {i > 0 && <div className="absolute -left-4 top-1/2 -translate-y-1/2 h-8 w-px bg-white/10" />}
                <div className="text-3xl font-black text-orange-500 tabular-nums">{n}</div>
                <div className="text-xs text-gray-500 mt-1 uppercase tracking-widest">{label}</div>
              </div>
            ))}
          </motion.div>
        </div>

        {/* RIGHT: Image composition */}
        <motion.div
          initial={{ opacity: 0, x: 60 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 1, delay: 0.3 }}
          className="relative hidden lg:flex items-center justify-center h-[600px]"
        >
          {/* Main: Tunisia map — large, glowing */}
          <motion.div
            className="relative w-full h-full flex items-center justify-center"
            animate={{ y: [-12, 12, -12] }}
            transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
          >
            <img
              src="/images/hero-tunisia-map.png"
              alt="Tunisia Real Estate Map"
              className="w-4/5 h-auto object-contain"
              style={{
                filter: 'drop-shadow(0 0 60px rgba(255,107,53,0.6)) drop-shadow(0 0 120px rgba(255,107,53,0.2)) brightness(0.85) saturate(1.2)',
              }}
            />
            {/* Pulsing ring behind map */}
            <motion.div
              className="absolute inset-0 rounded-full border border-orange-500/20"
              animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0, 0.3] }}
              transition={{ duration: 3, repeat: Infinity }}
            />
          </motion.div>

          {/* Community learning card — bottom left */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8, x: -20 }}
            animate={{ opacity: 1, scale: 1, x: 0 }}
            transition={{ duration: 0.7, delay: 1.2 }}
            className="absolute bottom-8 -left-4 w-52 rounded-2xl overflow-hidden border border-orange-500/30 shadow-2xl shadow-orange-500/10"
            style={{ backdropFilter: 'blur(10px)' }}
          >
            <img
              src="/images/community-learning.png"
              alt="Community Learning"
              className="w-full h-36 object-cover"
            />
            <div className="bg-black/80 px-4 py-3">
              <div className="text-orange-400 text-xs font-semibold mb-0.5">Community Learning</div>
              <div className="text-white text-xs">Real knowledge. Real impact.</div>
            </div>
          </motion.div>

          {/* Impact card — top right */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8, x: 20 }}
            animate={{ opacity: 1, scale: 1, x: 0 }}
            transition={{ duration: 0.7, delay: 1.5 }}
            className="absolute top-8 -right-4 w-48 rounded-2xl overflow-hidden border border-white/10 shadow-2xl"
          >
            <img
              src="/images/impact-building-future.png"
              alt="Building the Future"
              className="w-full h-28 object-cover"
            />
            <div className="bg-gray-950/90 px-3 py-2.5">
              <div className="text-white text-xs font-semibold">Building the Future</div>
              <div className="text-orange-400 text-xs mt-0.5">1,000+ members goal</div>
            </div>
          </motion.div>

          {/* Floating data dots */}
          {[
            { top: '20%', left: '15%', delay: 0 },
            { top: '60%', left: '80%', delay: 0.5 },
            { top: '80%', left: '40%', delay: 1 },
          ].map((dot, i) => (
            <motion.div
              key={i}
              className="absolute w-2 h-2 bg-orange-500 rounded-full"
              style={{ top: dot.top, left: dot.left }}
              animate={{ scale: [1, 1.8, 1], opacity: [0.6, 1, 0.6] }}
              transition={{ duration: 2, repeat: Infinity, delay: dot.delay }}
            />
          ))}
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10"
        animate={{ y: [0, 10, 0] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      >
        <div className="w-6 h-10 border-2 border-white/20 rounded-full flex justify-center pt-2">
          <motion.div
            className="w-1 h-3 bg-orange-500 rounded-full"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        </div>
      </motion.div>
    </section>
  );
}
