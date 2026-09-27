jest.mock('axios', () => {
  const instance = {
    get: jest.fn(() => Promise.resolve({ data: {} })),
    post: jest.fn(() => Promise.resolve({ data: {} })),
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
  };
  return { create: jest.fn(() => instance), post: jest.fn(), __instance: instance };
});

const axios = require('axios');
const api = require('../api');

const instance = axios.__instance;
const requestInterceptor = instance.interceptors.request.use.mock.calls[0][0];

describe('legal API client', () => {
  beforeEach(() => instance.post.mockClear());

  it('sends the question with the session id and a long timeout', async () => {
    await api.askLegalQuestion('Quels droits d’enregistrement ?', 'sess-1');
    expect(instance.post).toHaveBeenCalledWith(
      '/legal/ask/',
      { question: 'Quels droits d’enregistrement ?', session_id: 'sess-1' },
      { timeout: 90000 },
    );
  });

  it('omits the session id on the first question', async () => {
    await api.askLegalQuestion('Bonjour');
    expect(instance.post.mock.calls[0][1]).toEqual({ question: 'Bonjour', session_id: undefined });
  });

  it('sends feedback by response log id', async () => {
    await api.sendLegalFeedback(42, 'thumbs_up');
    expect(instance.post).toHaveBeenCalledWith('/legal/feedback/', { response_log_id: 42, feedback: 'thumbs_up' });
  });
});

describe('auth header', () => {
  afterEach(() => localStorage.clear());

  it('adds the bearer token when logged in', () => {
    localStorage.setItem('access_token', 'abc');
    expect(requestInterceptor({ headers: {} }).headers.Authorization).toBe('Bearer abc');
  });

  it('sends no Authorization header when logged out', () => {
    expect(requestInterceptor({ headers: {} }).headers.Authorization).toBeUndefined();
  });
});
