# Frontend

React 18, built with Create React App (`react-scripts` 5) and styled with Tailwind 3.

```
apps/web/src/
  pages/        route components (App.js holds the routes)
  features/     feature modules (components, per-feature API helpers)
  components/   shared UI (common/CommonComponents.jsx)
  context/      AuthContext (JWT storage, login, profile)
  services/     api.js: the axios instance and endpoint functions
  config/       apiBase.js: the one place the API URL is decided
```

## API URL

`src/config/apiBase.js` resolves the URL in this order:

1. `window.__API_BASE__`, from `public/config.js`. This is empty in the repository; the web
   container writes it from `API_BASE_URL`.
2. `REACT_APP_API_URL` at build time.
3. `http://localhost:8000/api`.

Every call must go through `API_BASE` or the `api` instance in `services/api.js`. The old
`index.html` hard-coded localhost, which sent every production build to localhost.

## Tests

`npm test -- --watchAll=false` (Jest + Testing Library). This covers the API client, the auth
header, API URL resolution, error messages and number formatting, the legal answer card, the
property list, the chat widget (focus, feedback), the account menu and alerts page, the Analyze
page's error states, the scanner result, the risk page and the valuation result panels. The
valuation form itself and the simulator page still have no tests.

## Recommendation: move from CRA to Vite (not done)

Create React App is no longer maintained. `react-scripts` 5 pins old webpack, Jest and ESLint
versions, and its dependency tree carries known audit warnings that can't be fixed in place. We
stayed on CRA during this migration so behaviour stays comparable. Moving to Vite is recommended
as a separate project:

- Replace `react-scripts` with `vite` + `@vitejs/plugin-react`, and move `public/index.html` to the
  project root with a module script tag.
- Rename `REACT_APP_*` variables to `VITE_*` (`import.meta.env`), or keep the runtime `config.js`,
  which already covers the API URL.
- Replace Jest with Vitest (the Testing Library APIs stay the same).
- Expect faster dev start-up and builds. The output folder changes from `build/` to `dist/`
  (update the web Dockerfile).
