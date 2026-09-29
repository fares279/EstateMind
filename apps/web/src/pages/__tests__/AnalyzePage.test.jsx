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
    expect(screen.getByRole('button', { name: /Price Forecast/ })).toBeInTheDocument();
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
});
