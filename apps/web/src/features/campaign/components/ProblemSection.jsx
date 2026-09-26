import React from 'react';
import { motion } from 'framer-motion';
import { useInView } from 'react-intersection-observer';

const problems = [
  {
    icon: '🗺️',
    title: 'No Data Transparency',
    desc: 'No comprehensive database covers real estate prices across Tunisia\'s governorates and municipalities.',
    image: '/images/community-learning.png',
    accentFrom: 'rgba(255,107,53,0.25)',
    accentTo: 'rgba(120,40,10,0.15)',
    borderColor: 'rgba(255,107,53,0.3)',
    back: 'Available information is fragmented and unreliable — forcing decisions to be based on guesswork rather than hard data.',
  },
  {
    icon: '📚',
    title: 'Financial Literacy Gap',
    desc: 'Citizens lack the financial and real estate education needed to understand the market and make sound decisions.',
    image: '/images/activity-educational-content.png',
    accentFrom: 'rgba(59,130,246,0.25)',
    accentTo: 'rgba(29,78,216,0.15)',
    borderColor: 'rgba(59,130,246,0.3)',
    back: '80% of property buyers in Tunisia rely solely on brokers with zero independent research or market analysis.',
  },
  {
    icon: '🏘️',
    title: 'Concentrated Investment',
    desc: 'Most real estate investment clusters in Tunis and Sousse, ignoring enormous opportunities across other regions.',
    image: '/images/activity-regional-discovery.png',
    accentFrom: 'rgba(34,197,94,0.25)',
    accentTo: 'rgba(21,128,61,0.15)',
    borderColor: 'rgba(34,197,94,0.3)',
    back: 'Governorates like Kairouan, Sidi Bouzid, and Thala hold massive undiscovered investment potential.',
  },
  {
    icon: '🤝',
    title: 'No Knowledge Network',
    desc: 'There is no organized community uniting learners, investors, and real estate experts on one platform.',
    image: '/images/activity-community-discussions.png',
    accentFrom: 'rgba(168,85,247,0.25)',
    accentTo: 'rgba(88,28,135,0.15)',
    borderColor: 'rgba(168,85,247,0.3)',
    back: 'Individual knowledge is never shared or documented, depriving everyone of collective experience and insight.',
  },
];

function ProblemCard({ problem, index }) {
  const [ref, inView] = useInView({ threshold: 0.15, triggerOnce: true });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 60 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay: index * 0.15 }}
      className="flip-card h-96"
    >
      <div className="flip-card-inner w-full h-full">
        {/* Front */}
        <div
          className="flip-card-front border overflow-hidden flex flex-col rounded-xl"
          style={{
            background: `linear-gradient(135deg, ${problem.accentFrom}, ${problem.accentTo})`,
            borderColor: problem.borderColor,
          }}
        >
          {/* Image strip */}
          <div className="relative h-36 overflow-hidden flex-shrink-0">
            <img
              src={problem.image}
              alt={problem.title}
              className="w-full h-full object-cover"
              style={{ filter: 'brightness(0.5) saturate(0.8)' }}
            />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent to-black/60" />
            <div className="absolute bottom-2 left-3 text-3xl">{problem.icon}</div>
          </div>
          {/* Text */}
          <div className="p-5 flex flex-col flex-1 justify-between">
            <div>
              <h3 className="text-white text-base font-bold mb-2">{problem.title}</h3>
              <p className="text-gray-300 text-xs leading-relaxed">{problem.desc}</p>
            </div>
            <div className="text-xs text-orange-400/60 mt-3">Hover to learn more →</div>
          </div>
        </div>
        {/* Back */}
        <div
          className="flip-card-back border p-6 flex flex-col items-center justify-center text-center rounded-xl"
          style={{
            background: `linear-gradient(135deg, ${problem.accentFrom}, rgba(0,0,0,0.9))`,
            borderColor: problem.borderColor,
          }}
        >
          <div className="text-5xl mb-4">{problem.icon}</div>
          <h3 className="text-white font-bold text-sm mb-3">{problem.title}</h3>
          <p className="text-gray-200 text-sm leading-relaxed">{problem.back}</p>
        </div>
      </div>
    </motion.div>
  );
}

export default function ProblemSection() {
  const [titleRef, titleInView] = useInView({ threshold: 0.2, triggerOnce: true });

  return (
    <section id="problem" className="section-full py-24 bg-black relative overflow-hidden">
      <div className="absolute inset-0 dot-pattern opacity-20 pointer-events-none" />

      <div className="max-w-6xl mx-auto px-6 relative z-10">
        {/* Title */}
        <motion.div
          ref={titleRef}
          initial={{ opacity: 0, y: 40 }}
          animate={titleInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.7 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-black text-white mb-4" style={{ fontFamily: 'Poppins, sans-serif' }}>
            Why Tunisia Needs{' '}
            <span className="gradient-text">#Aaref_Bledek</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Tunisia faces a real real estate information gap — we are here to close it.
          </p>
        </motion.div>

        {/* Problem cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {problems.map((p, i) => (
            <ProblemCard key={i} problem={p} index={i} />
          ))}
        </div>


      </div>
    </section>
  );
}
