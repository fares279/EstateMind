# Deployment

## Images

| Image | Built from | Runs |
| --- | --- | --- |
| API | `apps/api/Dockerfile` | `gunicorn` (default), or `celery -A config worker` / `celery -A config beat` |
| Web | `apps/web/Dockerfile` | nginx serving the CRA build |

The API entrypoint (`docker-entrypoint.sh`):

- refuses to start without a real `SECRET_KEY`;
- verifies the model artifacts, and fetches them when `ESTATEMIND_ARTIFACTS_URL` is set;
- runs migrations only where `RUN_MIGRATIONS=1`. Set that on the web container only.

The web container writes `config.js` from `API_BASE_URL` at start, so one build works for every
environment.

`docker-compose.yml` is a complete local stack and a template for production. Run **one** beat
instance.

The older `Procfile` and `build.sh` (gunicorn only, for platform-as-a-service hosts) still work.
The worker and beat are defined only in docker-compose, as agreed during the migration.

## Environment variables

All are listed with placeholders in `apps/api/.env.example`. The ones that matter in production:

| Variable | Notes |
| --- | --- |
| `SECRET_KEY`, `SIMPLE_JWT_SIGNING_KEY` | Required. Long and random |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | The real domains |
| `DB_*` | Postgres. `DB_SSLMODE=require` for managed databases |
| `REDIS_URL` | Celery broker and results |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | OTP and password-reset mail |
| `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Blank by default; billing needs all three |
| `LEGAL_LLM_*`, `LEGAL_LLM_FALLBACK_*` | Legal assistant LLM endpoints (see ml.md) |
| `ESTATEMIND_ARTIFACTS_URL` | Bundle to fetch when artifacts are missing |
| `VALUATION_CV_PRICE_ADJUSTMENT`, `VALUATION_SENTIMENT_PRICE_ADJUSTMENT` | Keep `False` (see ml.md) |
| `ENABLE_AUTO_SCRAPER` | Keep `False`. Scraping outside sites needs explicit approval |
| `PRELOAD_LEGAL_EMBEDDING_MODEL` | `True` on web and worker for a faster first answer; `False` on beat |

Web: `API_BASE_URL` (runtime). `REACT_APP_API_URL` (build time) is an optional default.

## Production checklist

- [ ] Rotate the LLM key, the Gmail app password and the Stripe test keys. The Stripe keys were
      hard-coded in the original `settings.py`; they are blank defaults now.
- [ ] Set `SECRET_KEY` and `SIMPLE_JWT_SIGNING_KEY` to new random values.
- [ ] Configure the Stripe webhook endpoint `/api/billing/webhook/stripe/` with its signing secret.
- [ ] Choose where the artifact bundle lives, and set `ESTATEMIND_ARTIFACTS_URL` (artifacts.md).
- [ ] Postgres backups.
- [ ] Rate limiting. DRF throttling is not configured: OTP, password reset, chatbot, legal and
      simulator endpoints are open to repeated calls.
- [ ] Decide who may start and delete simulator runs (known-issues.md).
- [ ] After deploying, run `sync_registry_from_artifacts` once (beat also schedules it), so the
      valuation registry has its rows.
