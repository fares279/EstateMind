import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useInView } from 'react-intersection-observer';
import ExploreLanding from '../components/Explore/ExploreLanding';
import ExploreWorkspace from '../components/Explore/ExploreWorkspace';

export default function ExplorePage() {
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [filters, setFilters] = useState({
    priceMin: 0,
    priceMax: 1000000,
    propertyType: 'all',
    region: 'all',
    sort: 'newest',
  });

  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden">
      {/* Section 1: Landing Explainer */}
      <ExploreLanding />

      {/* Section 2: Workspace with Map & Properties */}
      <ExploreWorkspace />
    </div>
  );
}
