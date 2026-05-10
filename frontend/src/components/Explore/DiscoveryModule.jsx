import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useInView } from 'react-intersection-observer';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import DiscoveryCard from './DiscoveryCard';

// User-focused insights
const MOCK_INSIGHTS = [
  {
    id: 1,
    category: 'buyers',
    title: '🏡 Cozy 2BR Apartment in Ariana',
    price: 'TND 320,000',
    purpose: 'For Sale',
    location: 'Quiet Residential Area · Ariana District',
    summary: 'Bright apartment suitable for small families or young professionals. Close to essential services and transport.',
    tags: ['Family Friendly', 'Good Accessibility', 'Safe Area'],
    icon: '🏡',
  },
  {
    id: 2,
    category: 'renters',
    title: '🏢 Studio in Innovation Hub',
    price: 'TND 450/month',
    purpose: 'For Rent',
    location: 'Modern District · Tunis Center',
    summary: 'Perfect for young professionals. Excellent public transport connection. Modern facilities nearby.',
    tags: ['Perfect for Singles', 'Great Location', 'Affordable'],
    icon: '🏢',
  },
  {
    id: 3,
    category: 'buyers',
    title: '🏠 Modern House with Garden',
    price: 'TND 580,000',
    purpose: 'For Sale',
    location: 'Green Neighborhood · Ben Arous',
    summary: 'Spacious house with outdoor space. Perfect for families wanting to expand. Quality neighborhood.',
    tags: ['Outdoor Space', 'Family Focused', 'Growing Area'],
    icon: '🏠',
  },
  {
    id: 4,
    category: 'renters',
    title: '🎯 Furnished Apartment Near University',
    price: 'TND 350/month',
    purpose: 'For Rent',
    location: 'Student Friendly · Sfax',
    summary: 'All utilities included. Walking distance to campus. Secure complex with 24/7 security.',
    tags: ['All-In Price', 'Secure', 'Community'],
    icon: '🎯',
  },
  {
    id: 5,
    category: 'sellers',
    title: '📊 Market Report: May Pricing Trends',
    price: 'Insights',
    purpose: 'Market Data',
    location: 'Across Tunisia',
    summary: 'See how property values are changing in your area. Know the best time to list your home.',
    tags: ['Timing Matters', 'Local Data', 'Smart Pricing'],
    icon: '📊',
  },
  {
    id: 6,
    category: 'buyers',
    title: '💼 Commercial Space in Prime Location',
    price: 'TND 950,000',
    purpose: 'For Sale',
    location: 'Business District · Tunis',
    summary: 'High foot traffic. Perfect for retail or services. Recent renovations. Strong growth area.',
    tags: ['Business Ready', 'High Visibility', 'Investment Worthy'],
    icon: '💼',
  },
];

export default function DiscoveryModule() {
  const [ref, inView] = useInView({ threshold: 0.2, triggerOnce: true });
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [carouselIndex, setCarouselIndex] = useState(0);

  const categories = ['all', 'For Buyers', 'For Renters', 'For Sellers'];
  const categoryMap = {
    'all': 'all',
    'For Buyers': 'buyers',
    'For Renters': 'renters',
    'For Sellers': 'sellers',
  };

  const filteredInsights = useMemo(() => {
    if (selectedCategory === 'all') return MOCK_INSIGHTS;
    const catKey = categoryMap[selectedCategory];
    return MOCK_INSIGHTS.filter(insight => insight.category === catKey);
  }, [selectedCategory]);

  const cardsPerView = 3;
  const totalSets = Math.ceil(filteredInsights.length / cardsPerView);
  const currentSet = filteredInsights.slice(
    carouselIndex * cardsPerView,
    (carouselIndex + 1) * cardsPerView
  );

  const handlePrev = () => {
    setCarouselIndex((prev) => (prev > 0 ? prev - 1 : totalSets - 1));
  };

  const handleNext = () => {
    setCarouselIndex((prev) => (prev < totalSets - 1 ? prev + 1 : 0));
  };

  return (
    <section className="relative bg-gradient-to-b from-black via-slate-950 to-black py-20 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <motion.div 
          ref={ref}
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="mb-16"
        >
          <div className="text-orange-500/60 font-mono text-sm tracking-widest mb-2 uppercase">— Market Intelligence</div>
          <h2 className="text-4xl md:text-5xl font-black text-white mb-3">
            What You Should Know <span className="text-[#FF6B35]">Right Now</span>
          </h2>
          <p className="text-gray-400 max-w-2xl">Real-time insights designed to help buyers, renters, and sellers make better decisions.</p>

          {/* Filter Tabs */}
          <div className="flex items-center justify-center gap-3 mt-8 flex-wrap">
            {categories.map((cat) => (
              <motion.button
                key={cat}
                onClick={() => {
                  setSelectedCategory(cat);
                  setCarouselIndex(0);
                }}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className={`px-6 py-2.5 rounded-lg font-semibold transition-all ${
                  selectedCategory === cat
                    ? 'bg-[#FF6B35] text-white shadow-lg shadow-orange-500/30'
                    : 'bg-white/10 text-gray-300 hover:bg-white/20 border border-white/20'
                }`}
              >
                {cat === 'all' ? '✨ All Insights' : cat}
              </motion.button>
            ))}
          </div>
        </motion.div>

        {/* Carousel Container */}
        <div className="relative w-full flex items-center justify-between gap-4 md:gap-6">
          {/* Left Arrow */}
          {totalSets > 1 && (
            <motion.button
              onClick={handlePrev}
              whileHover={{ scale: 1.15 }}
              whileTap={{ scale: 0.9 }}
              className="flex-shrink-0 w-10 h-10 md:w-12 md:h-12 rounded-full bg-white/15 hover:bg-orange-500/40 transition-colors border border-white/30 flex items-center justify-center text-white hover:text-orange-300"
            >
              <ChevronLeft size={20} />
            </motion.button>
          )}

          {/* Cards Carousel */}
          <div className="flex-1 overflow-hidden">
            <AnimatePresence mode="wait">
              <motion.div
                key={carouselIndex}
                initial={{ opacity: 0, x: 100 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -100 }}
                transition={{ duration: 0.4 }}
                className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-5"
              >
                {currentSet.map((insight, idx) => (
                  <motion.div
                    key={insight.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                  >
                    <DiscoveryCard insight={insight} />
                  </motion.div>
                ))}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Right Arrow */}
          {totalSets > 1 && (
            <motion.button
              onClick={handleNext}
              whileHover={{ scale: 1.15 }}
              whileTap={{ scale: 0.9 }}
              className="flex-shrink-0 w-10 h-10 md:w-12 md:h-12 rounded-full bg-white/15 hover:bg-orange-500/40 transition-colors border border-white/30 flex items-center justify-center text-white hover:text-orange-300"
            >
              <ChevronRight size={20} />
            </motion.button>
          )}
        </div>

        {/* Carousel Indicators */}
        {totalSets > 1 && (
          <div className="flex justify-center gap-2 mt-8">
            {Array.from({ length: totalSets }).map((_, i) => (
              <motion.button
                key={i}
                onClick={() => setCarouselIndex(i)}
                className={`h-2 rounded-full transition-all ${
                  i === carouselIndex
                    ? 'bg-[#FF6B35] w-8'
                    : 'bg-white/20 w-2 hover:bg-white/30'
                }`}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
