import React, { useMemo } from 'react';
import { BarChart3, Briefcase, TrendingUp } from 'lucide-react';
import FeatureGate from '../components/access/FeatureGate';
import { useAuth } from '../context/AuthContext';
import { getDashboardData } from '../services/api';

function InformationalInvestMode() {
  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-4xl font-black text-white">Investment Intelligence</h1>
        <p className="mt-2 text-gray-400">
          Learn how EstateMind helps investors track ROI, yield, and opportunity signals before committing capital.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {[
          {
            title: 'Portfolio Overview',
            body: 'Visualize total asset value, regional distribution, and performance trends.',
          },
          {
            title: 'ROI & Yield Analysis',
            body: 'Understand return metrics and detect underperforming properties quickly.',
          },
          {
            title: 'Opportunity Detection',
            body: 'Spot undervalued listings and compare buy-now vs wait signals.',
          },
        ].map((item) => (
          <article key={item.title} className="rounded-xl border border-white/10 bg-white/5 p-5">
            <h2 className="font-semibold text-white">{item.title}</h2>
            <p className="mt-2 text-sm text-gray-300">{item.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function FunctionalInvestMode() {
  const portfolio = [
    { name: 'Lac 2 Apartment', roi: 13.2, yield: 7.4, risk: 'medium' },
    { name: 'Sousse Villa', roi: 10.1, yield: 6.2, risk: 'low' },
    { name: 'Ariana Commercial', roi: 16.8, yield: 8.1, risk: 'high' },
  ];

  const summary = useMemo(() => {
    const avgRoi = portfolio.reduce((acc, item) => acc + item.roi, 0) / portfolio.length;
    const avgYield = portfolio.reduce((acc, item) => acc + item.yield, 0) / portfolio.length;
    return { avgRoi: avgRoi.toFixed(1), avgYield: avgYield.toFixed(1) };
  }, [portfolio]);

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-4xl font-black text-white">Investor Portfolio Dashboard</h1>
        <p className="mt-2 text-gray-400">Monitor portfolio performance and prioritize high-impact opportunities.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-white/10 bg-white/5 p-5">
          <p className="text-sm text-gray-400">Average ROI</p>
          <p className="mt-1 text-2xl font-bold text-[#FF6B35]">{summary.avgRoi}%</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-5">
          <p className="text-sm text-gray-400">Average Yield</p>
          <p className="mt-1 text-2xl font-bold text-[#FF6B35]">{summary.avgYield}%</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-5">
          <p className="text-sm text-gray-400">Tracked Assets</p>
          <p className="mt-1 text-2xl font-bold text-[#FF6B35]">{portfolio.length}</p>
        </div>
      </div>

      <div className="rounded-xl border border-white/10 bg-white/5 p-5">
        <h2 className="mb-4 text-lg font-semibold text-white">Portfolio Assets</h2>
        <div className="space-y-3">
          {portfolio.map((item) => (
            <div key={item.name} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 p-3">
              <div>
                <p className="font-medium text-white">{item.name}</p>
                <p className="text-xs text-gray-400">Risk: {item.risk}</p>
              </div>
              <div className="flex items-center gap-4 text-sm text-gray-200">
                <span>ROI {item.roi}%</span>
                <span>Yield {item.yield}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function InvestPage() {
  const { user, upgradePlan, trackActivity } = useAuth();
  const [dashboard, setDashboard] = React.useState(null);
  const savedCount = dashboard?.feature_nudges?.invest?.saved_properties_count || 0;

  const handleUpgrade = async () => {
    await trackActivity('cta_click', 'invest_upgrade_click', {
      page: 'invest',
      saved_properties_count: savedCount,
      target_plan: 'investor',
    });
    await upgradePlan('investor');
  };

  React.useEffect(() => {
    trackActivity('analysis', 'invest_page_view', { plan: user?.plan || 'free' });
  }, [trackActivity, user?.plan]);

  React.useEffect(() => {
    const loadBehavior = async () => {
      try {
        const response = await getDashboardData();
        setDashboard(response.data);
      } catch (err) {
        setDashboard(null);
      }
    };

    loadBehavior();
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] px-4 pb-16 pt-24">
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center gap-3 text-[#FFB38F]">
            <Briefcase size={18} />
            <p className="text-sm uppercase tracking-widest">Investor Feature</p>
          </div>
          <h1 className="mt-2 text-3xl font-black text-white">Invest Module</h1>
          <p className="mt-1 text-gray-400">From education to execution: portfolio analytics, ROI intelligence, and opportunity scanning.</p>
        </div>

        {!['investor'].includes((user?.plan || 'free').toLowerCase()) ? (
          <div className="rounded-2xl border border-[#FF6B35]/35 bg-[#FF6B35]/10 p-4 text-sm text-gray-100">
            {savedCount > 0
              ? 'Turn your saved properties into a portfolio with ROI and yield tracking in Investor plan.'
              : 'Start by saving properties in Explore, then unlock Investor tools to track full performance.'}
          </div>
        ) : null}

        <FeatureGate
          user={user}
          requiredPlan="investor"
          featureName="Invest"
          informational={<InformationalInvestMode />}
          onUpgrade={handleUpgrade}
          upgradeDescription="Investor plan unlocks portfolio tracking, ROI metrics, yield analytics, and advanced opportunity detection."
        >
          <FunctionalInvestMode />
        </FeatureGate>
      </div>
    </main>
  );
}
