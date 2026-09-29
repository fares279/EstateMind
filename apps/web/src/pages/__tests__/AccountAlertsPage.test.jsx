import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AccountAlertsPage from '../AccountAlertsPage';

jest.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: { email: 'a@b.c' } }) }));

test('alerts page says the feature is coming and shows no sample alerts', () => {
  render(<MemoryRouter><AccountAlertsPage /></MemoryRouter>);
  expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
  expect(screen.queryByText('Downtown Apartments')).toBeNull();
  expect(screen.queryByRole('button', { name: /create alert/i })).toBeNull();
});
