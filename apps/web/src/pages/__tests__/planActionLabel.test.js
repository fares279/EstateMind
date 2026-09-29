jest.mock('../../context/AuthContext', () => ({ useAuth: () => ({}) }));
jest.mock('react-router-dom', () => ({ useNavigate: () => jest.fn() }), { virtual: true });

const { planActionLabel } = require('../AccountDashboardPage');

describe('planActionLabel', () => {
  it('calls moving to a lower tier a downgrade', () => {
    expect(planActionLabel('pro', 'free')).toBe('Downgrade to Free');
    expect(planActionLabel('investor', 'pro')).toBe('Downgrade to Pro');
  });
  it('calls moving to a higher tier an upgrade', () => {
    expect(planActionLabel('free', 'pro')).toBe('Upgrade to Pro');
    expect(planActionLabel('pro', 'investor')).toBe('Upgrade to Investor');
  });
  it('marks the current plan', () => {
    expect(planActionLabel('pro', 'pro')).toBe('Current plan');
  });
});
