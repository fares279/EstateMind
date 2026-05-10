"""
Django settings for estatemind project.
Features: Full AI-powered real estate intelligence platform for Tunisia.
"""

from pathlib import Path
from decouple import config
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-changeme-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

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
    'core',
    'features',
    'campaign',
    'users',
    'billing',
    'scraper',
    'valuation',
    'forecast',
    'legal',
    'investor',
    'simulation',
    'chatbot',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000').split(',')
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost:3000').split(',')
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
}

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
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
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
LEGAL_RAG = {
    # Token Factory (OpenAI-compatible hosted LLM — no local Ollama required)
    'LLM_API_URL':       config('LEGAL_LLM_API_URL',  default='https://tokenfactory.esprit.tn/api'),
    'LLM_API_KEY':       config('LEGAL_LLM_API_KEY',  default=''),
    'LLM_MODEL':         config('LEGAL_LLM_MODEL',    default='hosted_vllm/Llama-3.1-70B-Instruct'),
    # Local embedding model (sentence-transformers, runs on CPU)
    'EMBEDDING_MODEL':   config('EMBEDDING_MODEL',    default='all-MiniLM-L6-v2'),
    # ChromaDB vector store
    'CHROMA_PERSIST_DIR': str(BASE_DIR / 'legal' / 'chroma_data'),
    'CHROMA_COLLECTION': config('LEGAL_CHROMA_COLLECTION', default='estate_legal'),
}

# Stripe Payment Configuration
STRIPE_PUBLIC_KEY = config('STRIPE_PUBLIC_KEY', default='pk_test_xxx')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='sk_test_xxx')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='whsec_test_xxx')
