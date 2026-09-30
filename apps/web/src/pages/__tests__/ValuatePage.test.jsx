import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MarketContext, Results } from '../ValuatePage';

jest.mock('../../services/api', () => ({}));

describe('MarketContext', () => {
  it('uses readable labels for the forecast and position', () => {
    render(<MarketContext market={{ avg_price_per_m2: 3423, comparable_count: 50, market_trend: 'rising',
                                     price_position: 'at_market' }} />);
    expect(screen.getByText('Rising')).toBeInTheDocument();
    expect(screen.getByText('In line with market')).toBeInTheDocument();
    expect(screen.queryByText(/at_market|at market/)).toBeNull();
  });

  it('claims no trend without a forecast', () => {
    render(<MarketContext market={{ avg_price_per_m2: null, comparable_count: 0, price_position: 'unknown' }} />);
    expect(screen.getByText('No forecast')).toBeInTheDocument();
    expect(screen.queryByText(/stable/i)).toBeNull();
    expect(screen.getAllByText('Not enough listings').length).toBeGreaterThan(0);
  });
});

describe('Results', () => {
  it('shows the model by its readable name, not the internal mode code', () => {
    const result = {
      estimated_price: 394989, price_per_m2: 3292, confidence: 72, confidence_level: 'Medium',
      price_range: { low: 340000, high: 450000 }, prediction_mode: 'catboost_by_type',
      model_display_name: 'CatBoost (Apartment model), trained 2026-09-29',
      market_context: { avg_price_per_m2: 3423, comparable_count: 50, market_trend: 'rising', price_position: 'at_market' },
      comparables: [], features_impact: [],
    };
    render(<MemoryRouter><Results result={result} txType="sale" /></MemoryRouter>);
    expect(screen.getAllByText('CatBoost (Apartment model), trained 2026-09-29').length).toBeGreaterThan(0);
    expect(screen.queryByText('Catboost By Type')).toBeNull();
  });
});
