import React from 'react';
import { TrendingUp, DollarSign, Target } from 'lucide-react';

export default function AnalyzeValuationsPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] pt-24 px-4">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-2">AI Valuations</h1>
        <p className="text-gray-400 mb-8">Accurate property valuations powered by machine learning</p>
        
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-6">
            <DollarSign className="text-[#FF6B35] mb-3" size={32} />
            <h3 className="text-white font-semibold mb-2">Average Market Price</h3>
            <p className="text-3xl font-bold text-[#FF6B35]">250K TND</p>
            <p className="text-gray-400 text-sm mt-2">+2.5% from last month</p>
          </div>
          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-6">
            <Target className="text-[#FF6B35] mb-3" size={32} />
            <h3 className="text-white font-semibold mb-2">Model Accuracy</h3>
            <p className="text-3xl font-bold text-[#FF6B35]">94%</p>
            <p className="text-gray-400 text-sm mt-2">MAPE confidence score</p>
          </div>
          <div className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-6">
            <TrendingUp className="text-[#FF6B35] mb-3" size={32} />
            <h3 className="text-white font-semibold mb-2">Properties Analyzed</h3>
            <p className="text-3xl font-bold text-[#FF6B35]">5,234</p>
            <p className="text-gray-400 text-sm mt-2">With AI predictions</p>
          </div>
        </div>

        <h2 className="text-2xl font-bold text-white mb-4">Recent Valuations</h2>
        <div className="space-y-4">
          {[1, 2, 3].map((item) => (
            <div key={item} className="glass-card bg-white/10 backdrop-blur-lg border border-white/10 rounded-lg p-6">
              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-white font-semibold">Property #{item}</h3>
                  <p className="text-gray-400 text-sm">Location: Tunis Center</p>
                </div>
                <div className="text-right">
                  <p className="text-[#FF6B35] font-bold text-xl">280K TND</p>
                  <p className="text-gray-400 text-sm">94% confidence</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
