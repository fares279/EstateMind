import React from 'react';
import { BarChart3, PieChart, Gauge } from 'lucide-react';

export default function AnalyzeDashboardsPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] pt-24 px-4">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-2">Market Dashboards</h1>
        <p className="text-gray-400 mb-8">Comprehensive market analytics and visualizations</p>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-8 h-80 flex items-center justify-center">
            <div className="text-center">
              <BarChart3 className="mx-auto mb-4 text-[#FF6B35]" size={48} />
              <p className="text-white font-semibold">Regional Distribution</p>
              <p className="text-gray-400 text-sm mt-2">Properties by governorate</p>
            </div>
          </div>

          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-8 h-80 flex items-center justify-center">
            <div className="text-center">
              <PieChart className="mx-auto mb-4 text-[#FF6B35]" size={48} />
              <p className="text-white font-semibold">Property Types</p>
              <p className="text-gray-400 text-sm mt-2">Market segmentation by type</p>
            </div>
          </div>

          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-8 h-80 flex items-center justify-center">
            <div className="text-center">
              <Gauge className="mx-auto mb-4 text-[#FF6B35]" size={48} />
              <p className="text-white font-semibold">Market Health Index</p>
              <p className="text-gray-400 text-sm mt-2">Overall market performance</p>
            </div>
          </div>

          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-8 h-80 flex items-center justify-center">
            <div className="text-center">
              <BarChart3 className="mx-auto mb-4 text-[#FF6B35]" size={48} />
              <p className="text-white font-semibold">Price Distribution</p>
              <p className="text-gray-400 text-sm mt-2">Price ranges and frequency</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
