// Single source for the API base URL.
// 1. window.__API_BASE__ from public/config.js: empty in the repo, written at
//    container start from API_BASE_URL, so one build serves any environment.
// 2. REACT_APP_API_URL at build time.
// 3. The local Django dev server.
// public/index.html used to hard-code localhost here, which overrode (2) in
// every production build.
const runtime = typeof window !== 'undefined' ? window.__API_BASE__ : '';

export const API_BASE = runtime || process.env.REACT_APP_API_URL || 'http://localhost:8000/api';
