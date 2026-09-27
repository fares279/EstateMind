describe('API_BASE', () => {
  const load = () => {
    let value;
    jest.isolateModules(() => { value = require('../apiBase').API_BASE; });
    return value;
  };
  const env = process.env.REACT_APP_API_URL;

  afterEach(() => {
    delete window.__API_BASE__;
    if (env === undefined) delete process.env.REACT_APP_API_URL;
    else process.env.REACT_APP_API_URL = env;
  });

  it('prefers the runtime value from config.js', () => {
    window.__API_BASE__ = 'https://api.example.tn/api';
    process.env.REACT_APP_API_URL = 'https://build.example.tn/api';
    expect(load()).toBe('https://api.example.tn/api');
  });

  it('falls back to the build-time variable when config.js is empty', () => {
    window.__API_BASE__ = '';
    process.env.REACT_APP_API_URL = 'https://build.example.tn/api';
    expect(load()).toBe('https://build.example.tn/api');
  });

  it('defaults to the local dev server', () => {
    delete process.env.REACT_APP_API_URL;
    expect(load()).toBe('http://localhost:8000/api');
  });
});
