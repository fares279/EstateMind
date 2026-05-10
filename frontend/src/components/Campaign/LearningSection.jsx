import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useInView } from 'react-intersection-observer';

const topics = [
  {
    id: 'market',
    icon: '📊',
    title: 'Market Analysis',
    subtitle: '— Module 01',
    color: 'from-orange-500/30 to-orange-900/10',
    border: 'border-orange-500/30',
    textColor: 'text-orange-400',
    lessons: [
      "How to read real estate market indicators",
      "Supply and demand analysis per governorate",
      "Understanding Tunisia's real estate cycles",
      "Cross-regional price comparison methods",
    ],
    image: '/images/activity-educational-content.png',
    front_text: 'Learn to analyse the Tunisian real estate market from scratch and make data-driven decisions.',
  },
  {
    id: 'regional',
    icon: '🗺️',
    title: 'Regional Discovery',
    subtitle: '— Module 02',
    color: 'from-blue-500/30 to-blue-900/10',
    border: 'border-blue-500/30',
    textColor: 'text-blue-400',
    lessons: [
      'Real estate opportunities in the Northwest',
      'The untapped potential of the South',
      'Emerging and rising investment zones',
      'Urban development mapping across Tunisia',
    ],
    image: '/images/activity-regional-discovery.png',
    front_text: 'Discover hidden investment opportunities in every corner of Tunisia.',
  },
  {
    id: 'legal',
    icon: '⚖️',
    title: 'Legal Framework',
    subtitle: '— Module 03',
    color: 'from-green-500/30 to-green-900/10',
    border: 'border-green-500/30',
    textColor: 'text-green-400',
    lessons: [
      'Urban planning and construction law in Tunisia',
      'Property transfer and ownership procedures',
      'Tenant and landlord rights',
      'Real estate taxes and building permits',
    ],
    image: '/images/community-learning.png',
    front_text: "Understand the legal framework governing Tunisia's real estate market.",
  },
  {
    id: 'investment',
    icon: '💰',
    title: 'Investment Strategy',
    subtitle: '— Module 04',
    color: 'from-purple-500/30 to-purple-900/10',
    border: 'border-purple-500/30',
    textColor: 'text-purple-400',
    lessons: [
      'Calculating real estate return on investment',
      'Buy-to-let strategies across regions',
      'Risk assessment and return evaluation',
      'Mortgage financing and loan options',
    ],
    image: '/images/activity-knowledge-contribution.png',
    front_text: 'Build your investment strategy on real data, not guesswork.',
  },
];

const slideVariants = {
  enter: (d) => ({ x: d > 0 ? '55%' : '-55%', opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (d) => ({ x: d < 0 ? '55%' : '-55%', opacity: 0 }),
};

export default function LearningSection() {
  const [titleRef, titleInView] = useInView({ threshold: 0.2, triggerOnce: true });
  const [active, setActive] = useState(0);
  const [dir, setDir] = useState(1);

  const next = () => { setDir(1);  setActive(p => (p + 1) % 4); };
  const prev = () => { setDir(-1); setActive(p => (p + 3) % 4); };
  const goTo = (p) => {
    if (p === active) return;
    setDir(p > active ? 1 : -1);
    setActive(p);
  };

  const topic = topics[active];

  return (
    <section
      id="learning"
      className="section-full py-24 relative overflow-hidden"
      style={{ background: 'linear-gradient(160deg, #0b1d35 0%, #0d2347 50%, #0b1d35 100%)' }}
    >
      {/* Background subtle texture */}
      <div className="absolute inset-0 pointer-events-none">
        <img src="/images/community-learning.png" alt="" className="w-full h-full object-cover opacity-5" />
        <div className="absolute inset-0" style={{ background: 'rgba(11,29,53,0.88)' }} />
      </div>
      {/* Animated orbs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <motion.div
          className="absolute top-16 -right-24 w-80 h-80 bg-orange-500/8 rounded-full blur-3xl"
          animate={{ scale: [1, 1.25, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 8, repeat: Infinity }}
        />
        <motion.div
          className="absolute -bottom-24 left-16 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl"
          animate={{ scale: [1.1, 1, 1.1], opacity: [0.2, 0.4, 0.2] }}
          transition={{ duration: 10, repeat: Infinity, delay: 3 }}
        />
      </div>

      <div className="max-w-6xl mx-auto px-6 relative z-10">
        {/* Title */}
        <motion.div
          ref={titleRef}
          initial={{ opacity: 0, y: 40 }}
          animate={titleInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.7 }}
          className="text-center mb-10"
        >
          <h2 className="text-4xl md:text-5xl font-black text-white mb-4" style={{ fontFamily: 'Poppins, sans-serif' }}>
            What You Will Learn in{' '}
            <span className="gradient-text">#Aaref_Bledek</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Comprehensive, free educational content covering every aspect of the Tunisian real estate market.
          </p>
        </motion.div>

        {/* Active module label */}
        <AnimatePresence mode="wait">
          <motion.div
            key={`label-${active}`}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={{ duration: 0.3 }}
            className="text-center mb-8"
          >
            <span className={`inline-block text-xs font-mono ${topic.textColor} font-bold uppercase tracking-widest mb-1`}>
              {topic.subtitle}
            </span>
            <h3 className="text-white text-2xl font-black">{topic.title}</h3>
          </motion.div>
        </AnimatePresence>

        {/* Cards pair */}
        <div className="relative px-12">
          <div className="overflow-hidden">
            <AnimatePresence mode="wait" custom={dir}>
              <motion.div
                key={active}
                custom={dir}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.45, ease: 'easeInOut' }}
                className="grid grid-cols-1 md:grid-cols-2 gap-6"
              >
                {/* Front card */}
                <div className="h-80">
                  <div
                    className={`relative w-full h-full border ${topic.border} rounded-2xl overflow-hidden flex flex-col justify-end`}
                  >
                    <img
                      src={topic.image}
                      alt={topic.title}
                      className="absolute inset-0 w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black via-black/70 to-transparent" />
                    <div className={`absolute inset-0 bg-gradient-to-br ${topic.color} opacity-60`} />
                    <div className="relative p-6 flex flex-col gap-2">
                      <div className="flex items-center justify-between">
                        <span className="text-3xl">{topic.icon}</span>
                        <span className={`text-xs font-mono ${topic.textColor} opacity-80`}>{topic.subtitle}</span>
                      </div>
                      <h3 className="text-white text-xl font-black">{topic.title}</h3>
                      <p className="text-gray-300 text-sm leading-relaxed">{topic.front_text}</p>
                    </div>
                  </div>
                </div>

                {/* Back card (curriculum) */}
                <div className="h-80">
                  <div
                    className={`relative w-full h-full bg-gradient-to-br from-gray-950 to-gray-900 border ${topic.border} rounded-2xl p-6 flex flex-col justify-between`}
                  >
                    <div>
                      <div className="flex items-center gap-3 mb-5">
                        <span className="text-3xl">{topic.icon}</span>
                        <div>
                          <div className={`text-xs font-mono ${topic.textColor}`}>{topic.subtitle}</div>
                          <h3 className="text-white font-black text-base">{topic.title}</h3>
                        </div>
                      </div>
                      <div className={`text-xs ${topic.textColor} font-bold mb-3 uppercase tracking-wider`}>Curriculum</div>
                      <ul className="space-y-2.5">
                        {topic.lessons.map((lesson, i) => (
                          <li key={i} className="flex items-start gap-2.5 text-sm text-gray-300">
                            <span className={`${topic.textColor} mt-0.5 text-xs font-bold flex-shrink-0`}>0{i + 1}</span>
                            {lesson}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Prev arrow — always active, wraps */}
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={prev}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 bg-white/5 border border-white/15 rounded-full flex items-center justify-center text-white hover:bg-orange-500/20 hover:border-orange-500/50 transition-all duration-200"
          >
            ←
          </motion.button>

          {/* Next arrow — always active, wraps */}
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={next}
            className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 bg-white/5 border border-white/15 rounded-full flex items-center justify-center text-white hover:bg-orange-500/20 hover:border-orange-500/50 transition-all duration-200"
          >
            →
          </motion.button>
        </div>

        {/* Module dot nav */}
        <div className="flex items-center justify-center gap-3 mt-8">
          {topics.map((t, p) => (
            <motion.button
              key={p}
              onClick={() => goTo(p)}
              whileHover={{ scale: 1.2 }}
              className={`transition-all duration-300 rounded-full ${
                active === p ? 'w-8 h-2 bg-orange-500' : 'w-2 h-2 bg-white/20 hover:bg-white/50'
              }`}
            />
          ))}
          <span className="text-gray-500 text-xs ml-3">{active + 1} / 4</span>
        </div>
      </div>
    </section>
  );
}
