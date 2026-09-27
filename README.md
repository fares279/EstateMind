# EstateMind

Real-estate intelligence for Tunisia: property valuation, price forecasts, investor scoring, climate
risk, a market simulator, a market chatbot and a legal assistant.

```
apps/
  api/   Django 5.2 + DRF, Celery (Redis), Postgres in production / SQLite locally
  web/   React 18 (Create React App) + Tailwind
docs/    architecture, ML models, artifacts, deployment, known issues
```

## Quick start (Docker)

```bash
cp apps/api/.env.example apps/api/.env      # then fill in SECRET_KEY and any API keys
docker compose up --build
```

- Web: http://localhost:3000
- API: http://localhost:8000 (OpenAPI docs at `/api/docs/`)

This runs Postgres, Redis, the API, a Celery worker, Celery beat and the web app. Model artifacts are
mounted from `apps/api/artifacts/`; see [docs/artifacts.md](docs/artifacts.md) for how to get them.

## Local development (without Docker)

API (Python 3.12):

```bash
cd apps/api
python -m venv .venv && .venv/Scripts/activate      # Windows; use .venv/bin/activate elsewhere
pip install -r requirements/dev.txt
cp .env.example .env                                # set USE_SQLITE=True for a local database
python manage.py migrate
python manage.py runserver
```

Web (Node 24):

```bash
cd apps/web
npm ci
npm start                                           # http://localhost:3000, calls http://localhost:8000/api
```

## Tests

```bash
cd apps/api && python -m pytest -q          # 224 tests; 7 skip when model artifacts are absent
cd apps/web && npm test -- --watchAll=false # 12 tests
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs the API suite on SQLite and on Postgres,
checks for missing migrations, runs the web tests and build, scans for secrets, and builds both
images.

## Documentation

- [Architecture](docs/architecture.md): apps, request flow, background jobs
- [ML models](docs/ml.md): what each model is, how it was validated, how to retrain it
- [Valuation training data](docs/ml/valuation-training-data.md): cleaning rules and open questions
- [Artifacts](docs/artifacts.md): storing and fetching trained models
- [Deployment](docs/deployment.md): images, environment variables, production checklist
- [Frontend](docs/frontend.md): structure, configuration, the Vite recommendation
- [Known issues](docs/known-issues.md)
