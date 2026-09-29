import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import UserProfileDropdown from '../UserProfileDropdown';

jest.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({ user: { email: 'a@b.c', full_name: 'A B' }, logout: jest.fn() }),
}));

test('menu has no link to the parked API Keys page', () => {
  render(<MemoryRouter><UserProfileDropdown isOpen onClose={() => {}} /></MemoryRouter>);
  expect(screen.getByText('Settings')).toBeInTheDocument();
  expect(screen.queryByText('API Keys')).toBeNull();
  expect(document.querySelector('a[href="/account/api-keys"]')).toBeNull();
});
