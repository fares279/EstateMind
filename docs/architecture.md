# Architecture

## Layout

The API is one Django project (`apps/api/config`) with apps grouped by domain under
`apps/api/estatemind/`. Each app keeps its original `AppConfig.label`, so database tables,
migrations and content types match the pre-migration backend.

| Group | App (label) | What it does |
| --- | --- | --- |
| platform | users, billing, campaign | Accounts and JWT auth, Stripe payments, the #Aaref_Bledek sign-up campaign |
| market | core, features, scraper | Regions, delegations and market snapshots; map/explore APIs; listing scrapers and the bronze → silver pipeline |
| intelligence | valuation, forecast, investor, climate, simulation | Price estimates, delegation price forecasts, investment scoring, climate risk, the agent-based market simulator |
| assistants | chatbot, legal | Market chatbot (intent classification + SQL-grounded answers) and the Tunisian real-estate law assistant (RAG) |

Shared infrastructure:

- `config/paths.py`: every filesystem location (data, artifacts, vector store). Each one can be
  overridden with an environment variable.
- `estatemind/assistants/shared_models.py`: one loaded copy of the multilingual sentence encoder,
  shared by the chatbot and the legal assistant.
- `ml/`: offline training code, kept apart from the serving code in `estatemind/`.

## Request flow

The browser loads the web app from nginx. `config.js` tells it where the API is. It calls
`/api/...` on the API, which runs under gunicorn. Auth uses JWT bearer tokens (SimpleJWT). The
default permission is authenticated-or-read-only; public endpoints opt in explicitly with
`AllowAny`.

Valuation, as an example of a model-serving path:

1. `valuation_service.estimate` maps the request to the model's features.
2. The model registry (`ValuationModelVersion`) chooses the served model. It picks the champion,
   or a challenger for its share of traffic.
3. The CatBoost bundle predicts the price.
4. Image and description signals are analysed and reported. They only change the price when
   `VALUATION_CV_PRICE_ADJUSTMENT` / `VALUATION_SENTIMENT_PRICE_ADJUSTMENT` are enabled; both are
   off by default. See [ml.md](ml.md).
5. The response carries comparables, price drivers, the confidence and provenance. The request is
   logged to `ValuationPredictionLog`.

## Background work

Celery with Redis as broker and result backend. Tasks come from every app via
`app.autodiscover_tasks()`. Beat runs the schedule in `CELERY_BEAT_SCHEDULE` (settings.py): monthly
calibration monitors, the weekly valuation drift check, the registry sync, daily summaries for
market, forecast and investor data, and legal quality, recall and reward-model jobs.

- Run exactly one beat process, or scheduled tasks run twice.
- Scraping outside sites is **not** scheduled. The only scraper loop is opt-in
  (`ENABLE_AUTO_SCRAPER`), and docker-compose forces it off.
- The simulator's `start` endpoint still runs simulations in a thread inside the web process, not
  in Celery (see [known-issues.md](known-issues.md)).

## Databases

Postgres in production. SQLite (`USE_SQLITE=True`) is for local work only. SQLite does not enforce
`max_length` and supports fewer query features, which has hidden real bugs. CI therefore runs the
whole test suite on both.
