import React from 'react';
import UpgradePrompt from './UpgradePrompt';
import { canAccessPlan } from '../../utils/accessControl';

export default function FeatureGate({
  user,
  requiredPlan = 'pro',
  featureName,
  informational,
  children,
  onUpgrade,
  upgradeDescription,
}) {
  const currentPlan = user?.plan || 'free';
  const allowed = canAccessPlan(currentPlan, requiredPlan);

  if (allowed) {
    return children;
  }

  return (
    <div className="space-y-6">
      {informational}
      <UpgradePrompt
        featureName={featureName}
        requiredPlan={requiredPlan}
        description={upgradeDescription}
        onUpgrade={onUpgrade}
      />
    </div>
  );
}
