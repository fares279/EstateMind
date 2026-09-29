"""
Django settings for estatemind project.
Features: Full AI-powered real estate intelligence platform for Tunisia.
"""

from pathlib import Path
from decouple import config
from celery.schedules import crontab
import hashlib
import os

BASE_DIR = Path(__file__).resolve().parent.parent

from config.paths import ARTIFACTS_DIR, CHROMA_DIR, DATA_DIR  # noqa: E402,F401

SECRET_KEY = config('SECRET_KEY', default='django-insecure-changeme-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,testserver').split(',')


def _normalized_jwt_signing_key(secret_key: str, signing_key: str | None = None) -> str:
    """Return a signing key that satisfies HS256 key length expectations."""
    candidate = (signing_key or '').strip() or secret_key
    candidate_bytes = candidate.encode('utf-8')
    if len(candidate_bytes) >= 32:
        return candidate
    return hashlib.sha256(candidate_bytes).hexdigest()

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'django_filters',
    'estatemind.market.core',
    'estatemind.market.features',
    'estatemind.platform.campaign',
    'estatemind.platform.users',
    'estatemind.platform.billing',
    'estatemind.market.scraper',
    'estatemind.intelligence.valuation',
    'estatemind.intelligence.forecast',
    'estatemind.assistants.legal',
    'estatemind.intelligence.investor',
    'estatemind.intelligence.simulation',
    'estatemind.assistants.chatbot',
    'estatemind.intelligence.climate',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
_CONN_MAX_AGE = config('DB_CONN_MAX_AGE', default=0, cast=int)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='estatemind_db'),
        'USER': config('DB_USER', default='estatemind_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': _CONN_MAX_AGE,
        # CONN_HEALTH_CHECKS requires CONN_MAX_AGE > 0 (persistent connections)
        'CONN_HEALTH_CHECKS': config('DB_CONN_HEALTH_CHECKS', default=False, cast=bool) and _CONN_MAX_AGE > 0,
        'OPTIONS': {'sslmode': config('DB_SSLMODE', default='disable')},
    }
}

if config('USE_SQLITE', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = config('TIME_ZONE', default='UTC')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# CORS & Security
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://localhost:3001').split(',')
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost:3000,http://localhost:3001').split(',')
CORS_ALLOW_CREDENTIALS = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=not DEBUG, cast=bool)

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    # Unexpected errors reach users as a plain message + reference code, never raw text
    'EXCEPTION_HANDLER': 'estatemind.platform.errors.api_exception_handler',
    # Generous defaults (a page load fires many requests); sensitive or costly
    # endpoints add a tighter scope from estatemind/platform/throttling.py.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '300/min',
        'user': '600/min',
        'login': '10/min',
        'register': '10/hour',
        'otp': '5/min',
        'password_reset': '5/hour',
        'chat': '20/min',
        'legal_ask': '10/min',
        'feedback': '30/min',
    },
    # Behind a load balancer set this to the number of proxies, so throttles see
    # the client IP (X-Forwarded-For) instead of the proxy's.
    'NUM_PROXIES': config('NUM_PROXIES', default=None, cast=lambda v: int(v) if v not in (None, '') else None),
}

# Throttle counters and chatbot conversation memory live in the cache. The
# default in-memory cache is per process: with several gunicorn workers a chat
# loses its memory whenever a request lands on another worker. Set CACHE_URL
# (e.g. redis://redis:6379/1) wherever more than one process serves requests.
if config('CACHE_URL', default=''):
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                          'LOCATION': config('CACHE_URL')}}

SPECTACULAR_SETTINGS = {
    'TITLE': 'EstateMind API',
    'VERSION': '1.0.0',
    'DESCRIPTION': 'AI-powered real estate intelligence platform for Tunisia',
}

# JWT Configuration
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': _normalized_jwt_signing_key(
        SECRET_KEY,
        config('SIMPLE_JWT_SIGNING_KEY', default=''),
    ),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
}

CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'Africa/Tunis'
# Where simulator runs execute: 'celery' (a worker; set in docker-compose) or 'thread'
# (inside the web process; the default, so local development needs no Redis).
SIMULATION_BACKEND = config('SIMULATION_BACKEND', default='thread')

# Celery Beat Schedule — Periodic Tasks
CELERY_BEAT_SCHEDULE = {
    'monthly-market-calibration': {
        'task': 'features.run_monthly_market_calibration',
        'schedule': crontab(day_of_month=1, hour=2, minute=0),  # 1st of month, 2 AM Africa/Tunis
        'options': {'expires': 3600}  # Expires after 1 hour if not run
    },
    'monthly-valuation-calibration': {
        'task': 'valuation.run_monthly_calibration_monitor',
        'schedule': crontab(day_of_month=1, hour=3, minute=0),
        'options': {'expires': 3600},
    },
    'weekly-valuation-drift': {
        'task': 'valuation.run_weekly_drift_monitor',
        'schedule': crontab(day_of_week=1, hour=4, minute=0),
        'options': {'expires': 3600},
    },
    'daily-valuation-registry-sync': {
        'task': 'valuation.sync_registry_from_artifacts',
        'schedule': crontab(hour=1, minute=30),
        'options': {'expires': 3600},
    },
    'nightly-market-analytics-materialization': {
        'task': 'core.materialize_daily_market_analytics',
        'schedule': crontab(hour=23, minute=0),
        'options': {'expires': 3600},
    },
    'nightly-forecast-summary-materialization': {
        'task': 'forecast.materialize_daily_forecast_summary',
        'schedule': crontab(hour=23, minute=15),
        'options': {'expires': 3600},
    },
    'nightly-investor-summary-materialization': {
        'task': 'investor.materialize_daily_investor_summary',
        'schedule': crontab(hour=23, minute=30),
        'options': {'expires': 3600},
    },
    'weekly-legal-recall-validation': {
        'task': 'legal.run_recall_validation',
        'schedule': crontab(day_of_week='monday', hour=3, minute=0),
        'options': {'expires': 3600},
    },
    'monthly-forecast-retraining-check': {
        'task': 'forecast.check_retraining_triggers',
        'schedule': crontab(day_of_month=2, hour=4, minute=0),  # 2nd of month, 4 AM Africa/Tunis (after Gold ETL)
        'options': {'expires': 3600},
    },

    # Module 7: Portfolio & Investment Intelligence
    'quarterly-investor-calibration-audit': {
        'task': 'estatemind.intelligence.investor.tasks.run_calibration_audit',
        'schedule': crontab(hour=2, minute=0, day_of_month='1', month_of_year='1,4,7,10'),  # 1st of Jan, Apr, Jul, Oct at 02:00
        'options': {'expires': 3600},
    },
    'daily-ab-test-evaluation': {
        'task': 'estatemind.intelligence.investor.tasks.evaluate_completed_ab_tests',
        'schedule': crontab(hour=1, minute=0),  # Every day at 01:00
        'options': {'expires': 3600},
    },
    'monthly-rl-classifier-precision': {
        'task': 'estatemind.intelligence.investor.tasks.check_rl_classifier_precision',
        'schedule': crontab(hour=3, minute=0, day_of_month='1'),  # 1st of each month at 03:00
        'options': {'expires': 3600},
    },
    'weekly-scorer-registry-sync': {
        'task': 'estatemind.intelligence.investor.tasks.sync_scorer_registry',
        'schedule': crontab(hour=4, minute=0, day_of_week='monday'),  # Every Monday at 04:00
        'options': {'expires': 3600},
    },
    
    # Module 8: Climate Intelligence Layer
    'biannual-climate-score-recomputation': {
        'task': 'estatemind.intelligence.climate.tasks.recompute_all_climate_scores',
        'schedule': crontab(hour=2, minute=0, day_of_month='1', month_of_year='1,7'),  # 1st Jan & Jul at 02:00
        'options': {'expires': 7200},  # 2 hours
    },
    'daily-climate-freshness-check': {
        'task': 'estatemind.intelligence.climate.tasks.check_freshness_and_alert',
        'schedule': crontab(hour=6, minute=0),  # Every day at 06:00
        'options': {'expires': 3600},
    },
    
    # Module 9: AI Real Estate Advisor (Chatbot Hardening)
    'monthly-rlhf-reward-model-retrain': {
        'task': 'estatemind.assistants.chatbot.tasks.retrain_reward_model',
        'schedule': crontab(hour=4, minute=0, day_of_month='1'),  # 1st of month @ 04:00
        'options': {'expires': 3600},
    },
    'daily-chatbot-quality-report': {
        'task': 'estatemind.assistants.chatbot.tasks.generate_quality_report',
        'schedule': crontab(hour=7, minute=0),  # Every day @ 07:00
        'options': {'expires': 3600},
    },
    # Legal assistant (same cadence as the chatbot)
    'daily-legal-quality-report': {
        'task': 'legal.generate_quality_report',
        'schedule': crontab(hour=7, minute=10),
        'options': {'expires': 3600},
    },
    'monthly-legal-reward-model-retrain': {
        'task': 'legal.retrain_reward_model',
        'schedule': crontab(hour=4, minute=10, day_of_month='1'),
        'options': {'expires': 3600},
    },
    'weekly-intent-classifier-accuracy-check': {
        'task': 'estatemind.assistants.chatbot.tasks.evaluate_intent_accuracy',
        'schedule': crontab(hour=3, minute=0, day_of_week='monday'),  # Mondays @ 03:00
        'options': {'expires': 3600},
    },
}

# Email Configuration
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.filebased.EmailBackend')
EMAIL_FILE_PATH = os.path.join(BASE_DIR, 'emails')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@estatemind.tn')

# Frontend URL for email links
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
        'scraper':        {'handlers': ['console'], 'level': 'INFO',  'propagate': False},
        'estatemind.market.scraper': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# Scraper configuration
SCRAPER = {
    # Default HTTP request timeout for scrapers (seconds)
    'REQUEST_TIMEOUT': config('SCRAPER_REQUEST_TIMEOUT', default=25, cast=int),
    # Max retries per URL before giving up
    'MAX_RETRIES': config('SCRAPER_MAX_RETRIES', default=4, cast=int),
    # Comma-separated proxy list (optional): "http://user:pass@host:port,..."
    'PROXIES': [
        p.strip() for p in
        config('SCRAPER_PROXIES', default='').split(',')
        if p.strip()
    ],
}

# Legal RAG Configuration
# Image price multiplier (1.0-1.2x) is a pixel-variance heuristic, not a validated
# model signal; off by default (Phase 4 re-validation).
VALUATION_CV_PRICE_ADJUSTMENT = config('VALUATION_CV_PRICE_ADJUSTMENT', default=False, cast=bool)
# Description-sentiment multiplier (0.9-1.15x): +9.6% on average with no accuracy
# gain against listing prices; shown to the user, kept out of the price.
VALUATION_SENTIMENT_PRICE_ADJUSTMENT = config('VALUATION_SENTIMENT_PRICE_ADJUSTMENT', default=False, cast=bool)

LEGAL_RAG = {
    # Token Factory (OpenAI-compatible hosted LLM — no local Ollama required)
    'LLM_API_URL':       config('LEGAL_LLM_API_URL',  default='https://tokenfactory.esprit.tn/api'),
    'LLM_API_KEY':       config('LEGAL_LLM_API_KEY',  default=''),
    'LLM_MODEL':         config('LEGAL_LLM_MODEL',    default='hosted_vllm/Llama-3.1-70B-Instruct'),
    # 'openai_compatible' (any /chat/completions API) or 'anthropic' (Claude)
    'LLM_PROVIDER':      config('LEGAL_LLM_PROVIDER', default='openai_compatible'),
    'LLM_VERIFY_SSL':    config('LEGAL_LLM_VERIFY_SSL', default=False, cast=bool),
    'LLM_TIMEOUT':       config('LEGAL_LLM_TIMEOUT', default=90, cast=int),
    'LLM_EFFORT':        config('LEGAL_LLM_EFFORT', default='medium'),  # Claude only
    # Optional second endpoint, used only when the primary is unreachable
    # (e.g. Token Factory off the campus network). Off unless PROVIDER is set.
    'LLM_FALLBACK': {
        'provider': config('LEGAL_LLM_FALLBACK_PROVIDER', default=''),
        'base_url': config('LEGAL_LLM_FALLBACK_API_URL', default=''),
        'api_key':  config('LEGAL_LLM_FALLBACK_API_KEY', default=''),
        'model':    config('LEGAL_LLM_FALLBACK_MODEL', default=''),
    },
    # Local embedding model (sentence-transformers, runs on CPU). Multilingual:
    # the corpus is French, questions arrive in French, English and Arabic.
    # Changing it requires `manage.py index_legal_data` (new collection).
    'EMBEDDING_MODEL':   config('EMBEDDING_MODEL', default='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'),
    'EMBEDDING_QUERY_PREFIX':   config('LEGAL_EMBEDDING_QUERY_PREFIX', default=''),
    'EMBEDDING_PASSAGE_PREFIX': config('LEGAL_EMBEDDING_PASSAGE_PREFIX', default=''),
    'CHUNK_WORDS':         80,
    'CHUNK_OVERLAP_WORDS': 20,
    # Grounding check (multilingual NLI)
    'NLI_MODEL':         config('LEGAL_NLI_MODEL', default='MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli'),
    # Retrieval gate: below this best-passage similarity the corpus is treated
    # as not covering the question (calibrated on data/eval_questions.json).
    'RETRIEVAL_MIN_SIMILARITY': config('LEGAL_RETRIEVAL_MIN_SIMILARITY', default=0.52, cast=float),
    'RETRIEVAL_TOP_K':          5,
    'RETRIEVAL_MAX_CONTEXT':    4,
    'RETRIEVAL_CONTEXT_MARGIN': 0.10,
    # ChromaDB vector store
    'CHROMA_PERSIST_DIR': str(CHROMA_DIR / 'legal'),
    'CHROMA_COLLECTION': config('LEGAL_CHROMA_COLLECTION', default='estate_legal'),
}

# Stripe Payment Configuration
STRIPE_PUBLIC_KEY = config('STRIPE_PUBLIC_KEY', default='')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')
# Stripe Price ids (price_...) for monthly plans. When set, checkout creates a renewing
# subscription; when blank, a one-off payment gives 30 days of the plan.
STRIPE_PRICE_IDS = {
    'pro': config('STRIPE_PRICE_PRO', default=''),
    'investor': config('STRIPE_PRICE_INVESTOR', default=''),
}
