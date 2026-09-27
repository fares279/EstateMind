#!/bin/sh
# Start-up checks shared by the web, worker and beat containers.
set -e

# settings.py falls back to an insecure placeholder key; never run with it.
if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "django-insecure-changeme-in-production" ]; then
  echo "SECRET_KEY is not set. Refusing to start." >&2
  exit 1
fi

# Model artifacts: fetch the bundle when they are missing and a URL is given.
if ! python scripts/artifacts.py verify >/dev/null 2>&1; then
  if [ -n "$ESTATEMIND_ARTIFACTS_URL" ]; then
    python scripts/artifacts.py fetch
  else
    echo "WARNING: model artifacts missing or different from artifacts.lock.json;" \
         "set ESTATEMIND_ARTIFACTS_URL or mount them at /app/artifacts." >&2
  fi
fi

# Only one container should migrate (the web one sets RUN_MIGRATIONS=1).
if [ "$RUN_MIGRATIONS" = "1" ]; then
  python manage.py migrate --no-input
fi

exec "$@"
