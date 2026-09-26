import React from 'react';
import { ArrowRight, Lock, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PLAN_PRICES_TND } from '../../utils/accessControl';

export default function UpgradePrompt({
  featureName,
  requiredPlan = 'pro',
  description,
  ctaLabel,
  onUpgrade,
}) {
  const price = PLAN_PRICES_TND[requiredPlan] ?? 0;
  const title = ctaLabel || `Upgrade to ${requiredPlan.charAt(0).toUpperCase() + requiredPlan.slice(1)}`;

  return (
    <div className="rounded-2xl border border-[#FF6B35]/35 bg-[#FF6B35]/10 p-5 md:p-6">
      <div className="flex items-start gap-3">
        <div className="mt-1 rounded-lg bg-[#FF6B35]/20 p-2 text-[#FFB38F]">
          <Lock size={18} />
        </div>
        <div className="space-y-2">
          <h3 className="text-lg font-bold text-white">
            {featureName} is available on the {requiredPlan.charAt(0).toUpperCase() + requiredPlan.slice(1)} plan
          </h3>
          <p className="text-sm text-gray-300">
            {description || 'Unlock the interactive experience with full AI capabilities, saved history, and personalized insights.'}
          </p>
          <p className="text-sm font-semibold text-[#FFB38F]">{price} TND</p>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onUpgrade}
          className="inline-flex items-center gap-2 rounded-xl bg-[#FF6B35] px-4 py-2.5 font-semibold text-white transition hover:bg-[#E85C2C]"
        >
          <Sparkles size={16} />
          {title}
          <ArrowRight size={16} />
        </button>
        <Link
          to="/account/dashboard"
          className="rounded-xl border border-white/20 px-4 py-2.5 text-sm font-semibold text-gray-100 transition hover:border-[#FF6B35]/60 hover:text-white"
        >
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}
