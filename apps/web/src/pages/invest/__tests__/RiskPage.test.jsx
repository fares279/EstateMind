import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RiskPage from '../RiskPage';
import { getInvestorRisk } from '../../../services/api';

jest.mock('../../../services/api', () => ({ getInvestorRisk: jest.fn() }));

test('risk dimensions show only measured values', async () => {
  getInvestorRisk.mockResolvedValue({ data: {
    portfolio_risk_score: 42, hhi_index: 55, concentration_risk: 'Medium',
    governorate_exposure: { Tunis: 70, Sousse: 30 }, property_type_exposure: { apartment: 100 },
    assets: [{ name: 'Flat', risk_score: 42, risk_level: 'Medium', yield_pct: 5, irr_pct: 7 }],
  } });
  render(<MemoryRouter><RiskPage /></MemoryRouter>);
  expect(await screen.findByText('Location concentration')).toBeInTheDocument();
  expect(screen.getByText('Market risk')).toBeInTheDocument();
  for (const invented of ['Volatility', 'Liquidity', 'Income Risk', 'Asset Mix']) {
    expect(screen.queryByText(invented)).toBeNull();
  }
});
