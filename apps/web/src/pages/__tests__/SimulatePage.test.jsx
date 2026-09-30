import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import * as api from '../../services/api';
import SimulatePage from '../SimulatePage';

let mockUser = { email: 'a@b.c' };
jest.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }));
jest.mock('../../services/api', () => ({
  simGetScenarios: jest.fn(), simStart: jest.fn(), simListRuns: jest.fn(), simGetRunDetail: jest.fn(),
  simDeleteRun: jest.fn(), simGetTimeseries: jest.fn(), simGetMetrics: jest.fn(), simGetAgents: jest.fn(),
  simCompare: jest.fn(), simGetZones: jest.fn(),
}));

const BASELINE = { bct_rate: 0.08, credit_approval_rate: 0.55, investor_multiplier: 1.0, demand_multiplier: 1.0,
                   developer_activity: 1.0 };

beforeEach(() => {
  api.simGetScenarios.mockResolvedValue({ data: { scenarios: [{ id: 'baseline', params: BASELINE }] } });
  api.simListRuns.mockResolvedValue({ data: { runs: [] } });
  api.simStart.mockReturnValue(new Promise(() => {}));
});

test("an untouched scenario runs with its own settings (no overrides)", async () => {
  mockUser = { email: 'a@b.c' };
  render(<MemoryRouter><SimulatePage /></MemoryRouter>);
  await waitFor(() => expect(api.simGetScenarios).toHaveBeenCalled());
  await act(async () => { fireEvent.click(await screen.findByRole('button', { name: /Run Simulation/ })); });
  // the page's slider defaults used to be sent every time, overwriting the scenario
  expect(api.simStart.mock.calls[0][0].policy_overrides).toEqual({});
});

test('visitors who are not signed in are asked to sign in before running', () => {
  mockUser = null;
  render(<MemoryRouter><SimulatePage /></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Sign in to run a simulation/ })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('button', { name: /Run Simulation/ })).toBeNull();
});
