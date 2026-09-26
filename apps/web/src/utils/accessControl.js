export const PLAN_LEVELS = {
  free: 0,
  pro: 1,
  investor: 2,
  premium: 2,
};

export const PLAN_PRICES_TND = {
  free: 0,
  pro: 250,
  investor: 500,
};

export const normalizePlan = (plan) => (plan || 'free').toLowerCase();

export const canAccessPlan = (userPlan, requiredPlan = 'free') => {
  const current = PLAN_LEVELS[normalizePlan(userPlan)] ?? 0;
  const target = PLAN_LEVELS[normalizePlan(requiredPlan)] ?? 0;
  return current >= target;
};

export const nextRecommendedPlan = (plan) => {
  const normalized = normalizePlan(plan);
  if (normalized === 'free') return 'pro';
  if (normalized === 'pro') return 'investor';
  return 'investor';
};

export const isInvestorPlan = (plan) => {
  const normalized = normalizePlan(plan);
  return normalized === 'investor' || normalized === 'premium';
};
