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
| `SIMULATION_BACKEND` | `celery` (runs on the worker; docker-compose sets it) or `thread` (default, inside the web process) |
| `PRELOAD_LEGAL_EMBEDDING_MODEL` | `True` on web and worker for a faster first answer; `False` on beat |

Web: `API_BASE_URL` (runtime). `REACT_APP_API_URL` (build time) is an optional default.

## Production checklist

- [ ] Rotate the LLM key, the Gmail app password and the Stripe test keys. The Stripe keys were
      hard-coded in the original `settings.py`; they are blank defaults now. Steps below.
- [ ] Set `SECRET_KEY` and `SIMPLE_JWT_SIGNING_KEY` to new random values (done for the local dev
      `.env` on 2026-09-29; do it again for each deployment).
- [ ] Configure the Stripe webhook endpoint `/api/billing/webhook/stripe/` with its signing secret.
- [ ] Publish the artifact bundle as a GitHub Release and set `ESTATEMIND_ARTIFACTS_URL`
      (artifacts.md).
- [ ] Postgres backups.
- [ ] Set `CACHE_URL` to Redis. The rate-limit counters and chatbot memory must be shared by
      all gunicorn workers.
- [ ] Behind a load balancer or proxy, set `NUM_PROXIES`, so rate limits count per client IP and
      not per proxy.
- [ ] After deploying, run `sync_registry_from_artifacts` once (beat also schedules it), so the
      valuation registry has its rows.
- [ ] Serve variant E for apartments (promoted 2026-09-29; see ml/valuation-training-data.md):
      `python -m ml.valuation.train_catboost_bundle --version estate_e_20260929 --register-existing`,
      then `python manage.py promote_model --version-id <id>` with the id of the
      `valuation:appartement` / `estate_e_20260929` row. Rollback: `promote_model` with the id of
      the previous `catboost-artifact` apartment row.

## Rotating keys

The provider keys can only be rotated from each provider's own dashboard. After each one, put the
new value in `apps/api/.env` (and `apps/web/.env` for the Stripe publishable key), restart, and
run:

```bash
cd apps/api
python manage.py check_integrations            # all checks; never prints key values
python manage.py check_integrations --only stripe
```

| Key | Where to rotate it | Variables to update | After rotating |
| --- | --- | --- | --- |
| Stripe test keys | Stripe dashboard → Developers → API keys → "Roll key" on the secret key | `STRIPE_SECRET_KEY`, `STRIPE_PUBLIC_KEY`; web `REACT_APP_STRIPE_PUBLISHABLE_KEY` (rebuild the web app) | `--only stripe` |
| Stripe webhook secret | Developers → Webhooks → the endpoint → "Roll secret" | `STRIPE_WEBHOOK_SECRET` | Send a test event and check the delivery log |
| Gmail app password | Google account → Security → App passwords: create a new one, then delete the old one | `EMAIL_HOST_PASSWORD` | `--only email` |
| LLM key (Token Factory) | The provider's portal | `LEGAL_LLM_API_KEY` | `--only llm` (reachable on the ESPRIT network only) |
| `SECRET_KEY`, `SIMPLE_JWT_SIGNING_KEY` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(64))"` | both | `--only signing`. Existing logins end |

Delete or revoke the old key as the last step, once the check passes. The original `backend/`
folder still holds the old values; that folder is not to be modified before sign-off, so the old
keys stay valid only until they are revoked at the provider.
