import React from 'react';
import { motion } from 'framer-motion';
import { useInView } from 'react-intersection-observer';

const activities = [
  {
    id: 1,
    icon: '🗺️',
    title: 'Regional Discovery',
    subtitle: 'Activity 01',
    desc: 'Visit real estate markets across different governorates, document prices, and track emerging trends on the ground.',
    image: '/images/activity-regional-discovery.png',
    color: 'orange',
    stats: '24 Governorates',
    tasks: ['Document land prices', 'Compare municipalities', 'Track new projects'],
  },
  {
    id: 2,
    icon: '📖',
    title: 'Educational Content',
    subtitle: 'Activity 02',
    desc: 'Create and share articles, guides, and video content covering every facet of the Tunisian real estate market.',
    image: '/images/activity-educational-content.png',
    color: 'blue',
    stats: '100+ Lessons',
    tasks: ['Write articles', 'Produce videos', 'Build courses'],
  },
  {
    id: 3,
    icon: '💬',
    title: 'Community Discussions',
    subtitle: 'Activity 03',
    desc: 'Live discussion forums on investment trends and opportunities in every region — knowledge shared openly.',
    image: '/images/activity-community-discussions.png',
    color: 'green',
    stats: '1,000+ Members',
    tasks: ['Q&A sessions', 'Share experience', 'Expert panels'],
  },
  {
    id: 4,
    icon: '🔬',
    title: 'Knowledge Contribution',
    subtitle: 'Activity 04',
    desc: 'Contribute to building the largest open real estate database in Tunisia, covering all 264 municipalities.',
    image: '/images/activity-knowledge-contribution.png',
    color: 'purple',
    stats: '264 Municipalities',
    tasks: ['Enter price data', 'Verify records', 'Regular updates'],
  },
];

const colorMap = {
  orange: { bg: 'bg-orange-500/10', border: 'border-orange-500/30', text: 'text-orange-400', dot: 'bg-orange-500' },
  blue:   { bg: 'bg-blue-500/10',   border: 'border-blue-500/30',   text: 'text-blue-400',   dot: 'bg-blue-500'   },
  green:  { bg: 'bg-green-500/10',  border: 'border-green-500/30',  text: 'text-green-400',  dot: 'bg-green-500'  },
  purple: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', dot: 'bg-purple-500' },
};

function ActivityCard({ activity, index }) {
  const colors = colorMap[activity.color];
  const [ref, inView] = useInView({ threshold: 0.15, triggerOnce: true });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 50 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay: index * 0.2 }}
      className={`glass-card ${colors.border} rounded-2xl overflow-hidden group hover:scale-105 transition-transform duration-300`}
    >
      {/* Image header */}
      <div className="relative h-40 overflow-hidden">
        <img
          src={activity.image}
          alt={activity.title}
          className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/50 to-transparent" />
        <div className={`absolute top-3 right-3 ${colors.bg} ${colors.border} border rounded-lg px-2 py-1`}>
          <span className={`text-xs font-bold ${colors.text}`}>{activity.stats}</span>
        </div>
        <div className="absolute bottom-3 left-3 text-3xl">{activity.icon}</div>
      </div>

      {/* Content */}
      <div className="p-5">
        <div className={`text-xs font-mono ${colors.text} mb-1`}>{activity.subtitle}</div>
        <h3 className="text-white text-lg font-bold mb-2">{activity.title}</h3>
        <p className="text-gray-400 text-sm leading-relaxed mb-4">{activity.desc}</p>
      </div>
    </motion.div>
  );
}

export default function ActivitiesSection() {
  const [titleRef, titleInView] = useInView({ threshold: 0.2, triggerOnce: true });

  return (
    <section
      id="activities"
      className="section-full py-24 relative overflow-hidden"
      style={{ background: 'linear-gradient(180deg, #000 0%, #0d1520 100%)' }}
    >
      {/* Background texture */}
      <div
        className="absolute inset-0 pointer-events-none opacity-20"
        style={{ backgroundImage: `url('/images/pattern-data-grid.png')`, backgroundSize: '100px 100px' }}
      />

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
            What We Do in{' '}
            <span className="gradient-text">#Aaref_Bledek</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-xl mx-auto">
            4 core activities forming the pillars of the campaign
          </p>
        </motion.div>

        {/* Timeline header */}
        <motion.div
          initial={{ opacity: 0, scaleX: 0 }}
          animate={titleInView ? { opacity: 1, scaleX: 1 } : {}}
          transition={{ duration: 1, delay: 0.3 }}
          className="relative mb-8 hidden md:flex items-center justify-between px-8"
        >
          <div className="absolute left-8 right-8 top-1/2 h-px bg-gradient-to-r from-orange-500/30 via-orange-500/60 to-orange-500/30" />
          {activities.map((a, i) => {
            const colors = colorMap[a.color];
            return (
              <div key={i} className="relative flex flex-col items-center gap-2">
                <div className={`w-4 h-4 ${colors.dot} rounded-full z-10 ring-4 ring-black`} />
                <span className={`text-xs ${colors.text} font-semibold`}>Activity {i + 1}</span>
              </div>
            );
          })}
        </motion.div>

        {/* Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {activities.map((activity, i) => (
            <ActivityCard key={activity.id} activity={activity} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
