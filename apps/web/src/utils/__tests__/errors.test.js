import { userErrorMessage } from '../errors';

describe('userErrorMessage', () => {
  it('prefers the server message', () => {
    expect(userErrorMessage({ response: { status: 400, data: { error: 'Enter a price.' } } })).toBe('Enter a price.');
    expect(userErrorMessage({ response: { status: 403, data: { detail: 'Not allowed.' } } })).toBe('Not allowed.');
  });
  it('never shows axios text', () => {
    const err = { message: 'Request failed with status code 500', response: { status: 500, data: '<html>' } };
    expect(userErrorMessage(err, 'Could not save.')).toBe('Could not save.');
    expect(userErrorMessage({ message: 'Network Error', request: {} })).toMatch(/Could not reach the server/);
  });
});
