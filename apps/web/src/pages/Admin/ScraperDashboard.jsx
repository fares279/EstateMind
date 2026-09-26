import React, { useState } from 'react';
import PipelineHealthDashboard from '../../features/scraper/components/PipelineHealthDashboard';
import ScraperJobManagement from '../../features/scraper/components/ScraperJobManagement';
import DataQualityManagement from '../../features/scraper/components/DataQualityManagement';

const TABS = [
  { id: 'health', label: 'Pipeline Health' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'quality', label: 'Data Quality' },
];

export default function ScraperDashboard() {
  const [activeTab, setActiveTab] = useState('health');

  return (
    <div className="min-h-screen bg-[#0b1220] pt-24 text-white">
      <div className="mx-auto max-w-7xl px-4 pb-12">
        <div className="mb-8 rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl backdrop-blur">
          <p className="text-xs uppercase tracking-[0.35em] text-[#FF6B35]">Scraper Control Center</p>
          <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-3xl font-bold md:text-4xl">Unified Real Estate Data</h1>
              <p className="mt-2 max-w-2xl text-sm text-gray-300">
                Monitor Bronze collection, Silver normalization, and Gold analytics from a single admin workspace.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-gray-300">
              Admin-only view
            </div>
          </div>
        </div>

        <div className="mb-6 flex flex-wrap gap-3 rounded-2xl border border-white/10 bg-white/5 p-2">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                activeTab === tab.id
                  ? 'bg-[#FF6B35] text-white shadow-lg shadow-[#FF6B35]/30'
                  : 'text-gray-300 hover:bg-white/10 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 shadow-2xl backdrop-blur">
          {activeTab === 'health' && <PipelineHealthDashboard />}
          {activeTab === 'jobs' && <ScraperJobManagement />}
          {activeTab === 'quality' && <DataQualityManagement />}
        </div>
      </div>
    </div>
  );
}