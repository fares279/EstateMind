import React from 'react';
import ExploreLanding from '../features/explore/components/ExploreLanding';
import ExploreWorkspace from '../features/explore/components/ExploreWorkspace';

export default function ExplorePage() {
  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden">
      {/* Section 1: Landing Explainer */}
      <ExploreLanding />

      {/* Section 2: Workspace with Map & Properties */}
      <ExploreWorkspace />
    </div>
  );
}
