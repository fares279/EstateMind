import React from 'react';
import { motion } from 'framer-motion';
import { useInView } from 'react-intersection-observer';

const roles = [
  {
    id: 'learner',
    value: 'learner',
    icon: '📚',
    title: 'Learner',
    desc: 'Learn, explore, and grow your understanding of the Tunisian real estate market from anywhere.',
    perks: ['Full access to all content', 'Join community discussions', 'Participation certificate', 'Weekly market reports'],
    color: 'orange',
    gradient: 'from-orange-500/20 to-orange-900/5',
    border: 'border-orange-500/30',
    glow: 'shadow-orange-500/20',
    badge: '🌱',
  },
  {
    id: 'contributor',
    value: 'contributor',
    icon: '✍️',
    title: 'Contributor',
    desc: 'Help build the largest open real estate database in Tunisia with verified, crowd-sourced data.',
    perks: ['All Learner benefits', 'Advanced analysis tools', 'Contributor badge', 'Points & rewards'],
    color: 'blue',
    gradient: 'from-blue-500/20 to-blue-900/5',
    border: 'border-blue-500/30',
    glow: 'shadow-blue-500/20',
    badge: '⭐',
  },
  {
    id: 'volunteer',
    value: 'volunteer',
    icon: '🤝',
    title: 'Volunteer',
    desc: 'Get deeply involved by organizing workshops and on-ground events in your local region.',
    perks: ['All Contributor benefits', 'Organize workshops', 'Raw data access', 'Professional network'],
    color: 'green',
    gradient: 'from-green-500/20 to-green-900/5',
    border: 'border-green-500/30',
    glow: 'shadow-green-500/20',
    badge: '💎',
  },
  {
    id: 'ambassador',
    value: 'ambassador',
    icon: '🌟',
    title: 'Ambassador',
    desc: 'Become the face of the campaign in your governorate and lead the local learning community.',
    perks: ['All previous benefits', 'Community leadership course', 'EstateMind collaboration', 'Media exposure'],
    color: 'purple',
    gradient: 'from-purple-500/20 to-purple-900/5',
    border: 'border-purple-500/30',
    glow: 'shadow-purple-500/20',
    badge: '👑',
  },
];

const colorTextMap = { orange: 'text-orange-400', blue: 'text-blue-400', green: 'text-green-400', purple: 'text-purple-400' };
const colorBgMap   = { orange: 'bg-orange-500/10', blue: 'bg-blue-500/10', green: 'bg-green-500/10', purple: 'bg-purple-500/10' };
const colorDotMap  = { orange: 'bg-orange-500', blue: 'bg-blue-500', green: 'bg-green-500', purple: 'bg-purple-500' };

function RoleCard({ role, index, onSelect }) {
  const [ref, inView] = useInView({ threshold: 0.15, triggerOnce: true });
  const textColor = colorTextMap[role.color];
  const bgColor   = colorBgMap[role.color];
  const dotColor  = colorDotMap[role.color];

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 60 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay: index * 0.15 }}
      whileHover={{ y: -10, scale: 1.02 }}
      className={`glass-card ${role.border} rounded-2xl p-6 flex flex-col gap-4 cursor-pointer group hover:shadow-2xl ${role.glow} transition-all duration-300`}
      onClick={() => onSelect(role.value)}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-5xl">{role.icon}</div>
        <span className={`text-2xl ${bgColor} rounded-full w-12 h-12 flex items-center justify-center`}>
          {role.badge}
        </span>
      </div>

      {/* Title */}
      <div>
        <h3 className="text-white text-2xl font-black">{role.title}</h3>
      </div>

      {/* Description */}
      <p className="text-gray-400 text-sm leading-relaxed flex-1">{role.desc}</p>

      {/* Perks */}
      <ul className="space-y-2">
        {role.perks.map((perk, i) => (
          <li key={i} className="flex items-center gap-2 text-sm text-gray-300">
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor}`} />
            {perk}
          </li>
        ))}
      </ul>

      {/* CTA */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className={`w-full py-3 ${bgColor} ${role.border} border ${textColor} rounded-xl text-sm font-semibold transition-all duration-300 group-hover:bg-opacity-30`}
      >
        Choose this role →
      </motion.button>
    </motion.div>
  );
}

export default function ParticipationSection({ onRoleSelect }) {
  const [titleRef, titleInView] = useInView({ threshold: 0.2, triggerOnce: true });

  return (
    <section id="participate" className="section-full py-24 bg-black relative overflow-hidden">
      {/* Tunisia outline bg */}
      <div className="absolute right-0 top-0 bottom-0 w-1/3 pointer-events-none opacity-5">
        <img src="/images/pattern-tunisia-outline.png" alt="" className="h-full w-full object-cover object-left" />
      </div>
      <div className="absolute top-1/4 right-1/4 w-64 h-64 bg-orange-500/5 rounded-full blur-3xl pointer-events-none" />

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
            Choose Your{' '}
            <span className="gradient-text">Role</span>
            {' '}in the Campaign
          </h2>
          <p className="text-gray-400 text-lg max-w-xl mx-auto">
            Everyone brings different skills — find the role that fits you best.
          </p>
        </motion.div>

        {/* Roles grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {roles.map((role, i) => (
            <RoleCard key={role.id} role={role} index={i} onSelect={onRoleSelect} />
          ))}
        </div>
      </div>
    </section>
  );
}
