import React from 'react';
import { TrendingUp, Calendar, BarChart3 } from 'lucide-react';

export default function AnalyzeTrendsPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] pt-24 px-4">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-2">Price Trends</h1>
        <p className="text-gray-400 mb-8">Historical data and market trend analysis</p>
        
        <div className="grid md:grid-cols-4 gap-4 mb-8">
          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-4">
            <p className="text-gray-400 text-sm mb-1">3 Month</p>
            <p className="text-2xl font-bold text-[#FF6B35]">+2.3%</p>
            <TrendingUp className="text-green-500 mt-2" size={20} />
          </div>
          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-4">
            <p className="text-gray-400 text-sm mb-1">6 Month</p>
            <p className="text-2xl font-bold text-[#FF6B35]">+5.8%</p>
            <TrendingUp className="text-green-500 mt-2" size={20} />
          </div>
          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-4">
            <p className="text-gray-400 text-sm mb-1">12 Month</p>
            <p className="text-2xl font-bold text-[#FF6B35]">+12.1%</p>
            <TrendingUp className="text-green-500 mt-2" size={20} />
          </div>
          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-4">
            <p className="text-gray-400 text-sm mb-1">Market Forecast</p>
            <p className="text-2xl font-bold text-[#FF6B35]">+8.5%</p>
            <Calendar className="text-blue-500 mt-2" size={20} />
          </div>
        </div>

        <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-8 h-96 flex items-center justify-center">
          <div className="text-center">
            <BarChart3 className="mx-auto mb-4 text-[#FF6B35]" size={48} />
            <p className="text-gray-400 mb-4">Chart visualization loading...</p>
            <p className="text-gray-500 text-sm">Price trend data with historical comparisons</p>
          </div>
        </div>
      </div>
    </div>
  );
}
