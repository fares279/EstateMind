import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, Briefcase, ScanSearch, TrendingUp, ShieldCheck,
} from 'lucide-react';

const NAV = [
  { to: '/invest',               label: 'Overview',      icon: LayoutDashboard, end: true },
  { to: '/invest/portfolio',     label: 'Portfolio',     icon: Briefcase },
  { to: '/invest/scanner',       label: 'Deal Scanner',  icon: ScanSearch },
  { to: '/invest/opportunities', label: 'Opportunities', icon: TrendingUp },
  { to: '/invest/risk',          label: 'Risk Monitor',  icon: ShieldCheck },
];

export default function InvestLayout() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] pt-24 px-4 pb-20 text-white">
      <div className="max-w-6xl mx-auto space-y-8">

        {/* Section header */}
        <section>
          <h1 className="text-4xl font-black text-white">Invest</h1>
          <p className="mt-2 text-gray-400 text-lg max-w-2xl">
            AI-powered investment intelligence — portfolio tracking, deal scanning and market opportunities across Tunisia.
          </p>
        </section>

        {/* Tab navigation — same pill style as AnalyzePage */}
        <div className="flex gap-1 rounded-2xl border border-white/10 bg-white/5 p-1.5">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to} to={to} end={end}
              className={({ isActive }) =>
                `flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-3
                 text-sm font-semibold transition-all
                 ${isActive
                   ? 'bg-[#FF6B35] text-white shadow-lg shadow-[#FF6B35]/20'
                   : 'text-gray-400 hover:text-gray-200'}`
              }
            >
              <Icon size={15} />{label}
            </NavLink>
          ))}
        </div>

        {/* Active sub-page */}
        <Outlet />

      </div>
    </main>
  );
}
