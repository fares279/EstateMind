import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import * as api from '../../services/api';
import AnalyzePage from '../AnalyzePage';

jest.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: { plan: 'pro' }, trackActivity: () => {} }) }));
jest.mock('../../services/api', () => ({
  getForecastGovernorateList: jest.fn(), getForecastDelegationList: jest.fn(), getForecastDelegation: jest.fn(),
  getForecastNational: jest.fn(), getForecastMarket: jest.fn(), getKpiFreshness: jest.fn(), getMarketDashboard: jest.fn(),
}));

beforeEach(() => {
  const pending = () => new Promise(() => {});
  api.getForecastGovernorateList.mockImplementation(pending);
  api.getForecastDelegationList.mockImplementation(pending);
  api.getForecastNational.mockImplementation(pending);
  api.getKpiFreshness.mockImplementation(pending);
  api.getMarketDashboard.mockImplementation(pending);
});

describe('AnalyzePage', () => {
  it('has the market and forecast tabs only (climate tab removed)', () => {
    api.getForecastMarket.mockImplementation(() => new Promise(() => {}));
    render(<AnalyzePage />);
    expect(screen.getByRole('button', { name: /Market Dashboard/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Price Outlook/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Climate/ })).not.toBeInTheDocument();
  });

  it('explains a failed market load and retries', async () => {
    api.getForecastMarket.mockRejectedValueOnce({ response: { status: 503, data: { error: 'Service busy.' } } });
    api.getForecastMarket.mockImplementation(() => new Promise(() => {}));
    render(<AnalyzePage />);
    expect(await screen.findByText(/Market data could not be loaded\. Service busy\./)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(api.getForecastMarket).toHaveBeenCalledTimes(2));
  });

  it('computes the coastal premium and one set of trend counts', async () => {
    const row = (delegation, price_avg, annual_trend_pct, is_coastal) => ({
      delegation, governorate: is_coastal ? 'Nabeul' : 'Kairouan', price_avg, price_min: price_avg, price_max: price_avg,
      price_12m: price_avg, annual_trend_pct, is_coastal });
    api.getForecastMarket.mockResolvedValue({ data: {
      total_delegations: 4, horizon: { start: 'Sep 2026', end: 'Aug 2027' },
      delegations: [row('Hammamet', 3000, 5, true), row('Korba', 3000, 0.5, true),
                    row('Kairouan Nord', 2000, -3, false), row('Haffouz', 2000, 1, false)] } });
    render(<AnalyzePage />);
    // (3000 / 2000 - 1) = +50%; it read '+-100.0%' when is_coastal was missing
    expect(await screen.findByText('+50.0%')).toBeInTheDocument();
    expect(screen.getByText(/1 declining · 2 stable/)).toBeInTheDocument();
    expect(screen.queryByText(/NaN/)).toBeNull();
  });
});
