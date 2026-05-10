import React from 'react';
import { motion } from 'framer-motion';
import { useInView } from 'react-intersection-observer';

const pillars = [
  { icon: '🎓', title: 'Free Education', desc: 'Open learning content accessible to every Tunisian' },
  { icon: '🗺️', title: 'Local Data', desc: '24 governorates, 264 municipalities fully documented' },
  { icon: '🤝', title: 'Active Community', desc: 'Learners, contributors, volunteers, and ambassadors' },
  { icon: '📊', title: 'AI Analysis', desc: 'Machine learning models for real estate market insights' },
];

const nodes = [
  { x: 50, y: 18, label: 'Education', color: '#FF6B35' },
  { x: 82, y: 50, label: 'Data', color: '#FF8C5A' },
  { x: 66, y: 82, label: 'Community', color: '#FFA07A' },
  { x: 34, y: 82, label: 'Analysis', color: '#FF6B35' },
  { x: 18, y: 50, label: 'Vision', color: '#FF4500' },
  { x: 50, y: 50, label: '#Aaref_Bledek', color: '#FF6B35', isCenter: true },
];

export default function VisionSection() {
  const [ref, inView] = useInView({ threshold: 0.2, triggerOnce: true });
  const [netRef, netInView] = useInView({ threshold: 0.1, triggerOnce: true });

  return (
    <section
      id="vision"
      className="section-full py-24 relative overflow-hidden"
      style={{ background: 'linear-gradient(180deg, #000000 0%, #1A2332 50%, #000000 100%)' }}
    >
      {/* Glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-orange-500/5 rounded-full blur-3xl" />
      </div>

      <div className="max-w-6xl mx-auto px-6 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

          {/* LEFT: Text + pillars */}
          <motion.div
            ref={ref}
            initial={{ opacity: 0, x: -60 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.8 }}
          >
            <h2
              className="text-4xl md:text-5xl font-black text-white mb-6 leading-tight"
              style={{ fontFamily: 'Poppins, sans-serif' }}
            >
              Building a{' '}
              <span className="gradient-text">Knowledge Map</span>
              <br />
              of Tunisian Real Estate
            </h2>
            <p className="text-gray-300 text-lg leading-relaxed mb-8">
              Our vision is to transform Tunisia into an Arab model of real estate transparency —
              where every citizen can discover the value of any property in any municipality
              and understand the investment opportunities in their region.
            </p>

            {/* Pillars */}
            <div className="grid grid-cols-2 gap-4">
              {pillars.map((p, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 20 }}
                  animate={inView ? { opacity: 1, y: 0 } : {}}
                  transition={{ duration: 0.5, delay: 0.3 + i * 0.1 }}
                  className="glass-card rounded-xl p-4 hover:border-orange-500/30 transition-all duration-300"
                >
                  <div className="text-2xl mb-2">{p.icon}</div>
                  <div className="text-white font-semibold text-sm mb-1">{p.title}</div>
                  <div className="text-gray-400 text-xs">{p.desc}</div>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* RIGHT: Image collage + network */}
          <motion.div
            ref={netRef}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={netInView ? { opacity: 1, scale: 1 } : {}}
            transition={{ duration: 0.9, delay: 0.2 }}
            className="relative"
          >
            {/* Network SVG */}
            <div className="relative h-80 lg:h-[420px]">
              <svg viewBox="0 0 100 100" className="w-full h-full">
                {nodes.slice(0, 5).map((node, i) => (
                  <motion.line
                    key={i}
                    x1={nodes[5].x} y1={nodes[5].y}
                    x2={node.x} y2={node.y}
                    stroke="rgba(255,107,53,0.4)"
                    strokeWidth="0.5"
                    initial={{ pathLength: 0, opacity: 0 }}
                    animate={netInView ? { pathLength: 1, opacity: 1 } : {}}
                    transition={{ duration: 1, delay: 0.5 + i * 0.15 }}
                  />
                ))}
                {[[0,1],[1,2],[2,3],[3,4],[4,0]].map(([a,b], i) => (
                  <motion.line
                    key={`c-${i}`}
                    x1={nodes[a].x} y1={nodes[a].y}
                    x2={nodes[b].x} y2={nodes[b].y}
                    stroke="rgba(255,107,53,0.15)"
                    strokeWidth="0.3"
                    initial={{ opacity: 0 }}
                    animate={netInView ? { opacity: 1 } : {}}
                    transition={{ duration: 0.5, delay: 1.2 + i * 0.1 }}
                  />
                ))}
                {nodes.map((node, i) => (
                  <g key={i}>
                    <motion.circle
                      cx={node.x} cy={node.y}
                      r={node.isCenter ? 8 : 5}
                      fill={node.color}
                      fillOpacity={node.isCenter ? 0.9 : 0.7}
                      initial={{ scale: 0 }}
                      animate={netInView ? { scale: 1 } : {}}
                      transition={{ duration: 0.4, delay: 0.8 + i * 0.1, type: 'spring' }}
                      style={{ transformOrigin: `${node.x}px ${node.y}px` }}
                    />
                    {node.isCenter && (
                      <motion.circle
                        cx={node.x} cy={node.y} r={12}
                        fill="none"
                        stroke={node.color}
                        strokeWidth="0.5"
                        strokeOpacity="0.4"
                        animate={netInView ? { scale: [1, 1.3, 1] } : {}}
                        transition={{ duration: 2, repeat: Infinity, delay: 1.5 }}
                        style={{ transformOrigin: `${node.x}px ${node.y}px` }}
                      />
                    )}
                    <motion.text
                      x={node.x}
                      y={node.isCenter ? node.y + 16 : node.y + 9}
                      textAnchor="middle"
                      fontSize={node.isCenter ? '3.5' : '3'}
                      fill="white"
                      fillOpacity="0.85"
                      initial={{ opacity: 0 }}
                      animate={netInView ? { opacity: 1 } : {}}
                      transition={{ delay: 1.2 + i * 0.1 }}
                    >
                      {node.label}
                    </motion.text>
                  </g>
                ))}
              </svg>

              {/* Community learning image — bottom left */}
              <motion.div
                className="absolute -bottom-4 -left-4 w-40 rounded-2xl overflow-hidden border-2 border-orange-500/40 shadow-2xl shadow-orange-500/10"
                initial={{ opacity: 0, scale: 0, x: -20 }}
                animate={netInView ? { opacity: 1, scale: 1, x: 0 } : {}}
                transition={{ duration: 0.6, delay: 1.6 }}
              >
                <img
                  src="/images/community-learning.png"
                  alt="Community Learning"
                  className="w-full h-28 object-cover"
                />
                <div className="bg-black/80 px-3 py-2">
                  <div className="text-orange-400 text-xs font-bold">Community Learning</div>
                </div>
              </motion.div>

              {/* Impact image — top right */}
              <motion.div
                className="absolute -top-4 -right-4 w-36 rounded-2xl overflow-hidden border-2 border-white/10 shadow-xl"
                initial={{ opacity: 0, scale: 0, x: 20 }}
                animate={netInView ? { opacity: 1, scale: 1, x: 0 } : {}}
                transition={{ duration: 0.6, delay: 1.8 }}
              >
                <img
                  src="/images/impact-building-future.png"
                  alt="Building the Future"
                  className="w-full h-24 object-cover"
                  style={{ filter: 'brightness(0.8)' }}
                />
                <div className="bg-gray-950/90 px-3 py-2">
                  <div className="text-white text-xs font-semibold">Building the Future</div>
                </div>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
