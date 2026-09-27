# EstateMind API image: one image for web (gunicorn), Celery worker and beat.
# The role is chosen by the command (see docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/var/cache/huggingface

# libgomp: CatBoost/torch OpenMP runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ requirements/
RUN pip install -r requirements/prod.txt

COPY . .

# Static files are collected at build time; SECRET_KEY here is build-only.
RUN SECRET_KEY=build-only USE_SQLITE=True PRELOAD_LEGAL_EMBEDDING_MODEL=False \
    python manage.py collectstatic --no-input \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /app/artifacts "$HF_HOME" \
    && chown -R app:app /app/artifacts "$HF_HOME" /app/staticfiles \
    && chmod +x docker-entrypoint.sh

USER app
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
