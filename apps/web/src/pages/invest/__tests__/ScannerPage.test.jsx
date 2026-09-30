import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import ScannerPage from '../ScannerPage';
import { getForecastDelegationList, getScanHistory, scanListing } from '../../../services/api';

jest.mock('../../../services/api', () => ({
  scanListing: jest.fn(), getScanHistory: jest.fn(), getForecastDelegationList: jest.fn(),
}));

const RESULT = {
  undervaluation: { label: 'FAIRLY_PRICED' }, buy_signal: { signal: 'WAIT' }, investment_grade: 'C',
  opportunity_score: 48,
  pricing: { listing_price_tnd: 250000, fair_value_est_tnd: 240000, price_gap_pct: 4.2, zone_avg_pm2: 2400, listing_pm2: 2500 },
  yield: { gross_yield_pct: 4.3, net_yield_pct: 3.6, monthly_rent_est: 900, basis: 'market_rent_delegation' },
  forecast: { available: true, source: 'forecast_module', direction: 'DOWN', forecast_6m_pct: -3.4,
              forecast_12m_pct: -7.4, low_12m_pct: -9.7, high_12m_pct: -5.0 },
  zone: { sale_listing_count: 45, rent_listing_count: 12, median_sale_price_per_m2: 2380 },
};

async function scan(result) {
  getScanHistory.mockResolvedValue({ data: [] });
  getForecastDelegationList.mockResolvedValue({ data: [] });
  scanListing.mockResolvedValue({ data: result });
  render(<ScannerPage />);
  fireEvent.change(screen.getByPlaceholderText('280 000'), { target: { value: '250000' } });
  fireEvent.change(screen.getByPlaceholderText('110'), { target: { value: '100' } });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Analyze Investment/ })); });
}

describe('ScannerPage result', () => {
  it('shows a falling forecast with its sign and real listing counts', async () => {
    await scan(RESULT);
    expect(await screen.findByText('−7.4%')).toBeInTheDocument();
    expect(screen.getByText('Falling')).toBeInTheDocument();
    expect(screen.getByText('−9.7% to −5.0%')).toBeInTheDocument();
    expect(screen.getByText('45 listings')).toBeInTheDocument();
    // the constant zone metrics are gone
    expect(screen.queryByText('Buyer Demand')).toBeNull();
    expect(screen.queryByText('Forecast Confidence')).toBeNull();
    expect(screen.queryByText(/\+-/)).toBeNull();
  });

  it('says when there is no forecast instead of showing a number', async () => {
    await scan({ ...RESULT, forecast: { available: false } });
    expect(await screen.findByText('There is no price forecast for this area yet.')).toBeInTheDocument();
  });
});
