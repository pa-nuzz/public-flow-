import os
import sys
import base64
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from decouple import config
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-test-key')
DEBUG = config('DEBUG', default=True, cast=bool)
def parse_csv_env(var, default=''):
    val = config(var, default=default)
    return [v.strip() for v in val.split(',') if v.strip()]

ALLOWED_HOSTS = parse_csv_env('ALLOWED_HOSTS', 'localhost,127.0.0.1')

# --- Explicit CSRF_TRUSTED_ORIGINS logic for ngrok/dev ---
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='').split(',')
CSRF_TRUSTED_ORIGINS = [x.strip() for x in CSRF_TRUSTED_ORIGINS if x.strip()]
if DEBUG:
    CSRF_TRUSTED_ORIGINS += [
        'https://*.ngrok-free.app',
        'https://*.ngrok.io',
        'http://127.0.0.1:51239',  # Browser preview proxy
        'http://localhost:51239',
    ]
    ALLOWED_HOSTS += ['*.ngrok-free.app', '*.ngrok.io', '127.0.0.1', 'localhost']
NGROK_DOMAIN = config('NGROK_DOMAIN', default='').strip()
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default='http://127.0.0.1:8000').strip().rstrip('/')

def _normalize_host(value: str) -> str:
    if not value:
        return ''
    parsed = urlparse(value if '://' in value else f'https://{value}')
    return parsed.netloc or parsed.path

ngrok_host = _normalize_host(NGROK_DOMAIN)
if ngrok_host and ngrok_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(ngrok_host)

if PUBLIC_BASE_URL:
    public_host = urlparse(PUBLIC_BASE_URL).netloc
    if public_host and public_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(public_host)

# Add wildcard ngrok domains for dev convenience
for wildcard_host in ['.ngrok-free.dev', '.ngrok.io']:
    if wildcard_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(wildcard_host)

# CSRF trusted origins
if ngrok_host:
    ngrok_origin = f'https://{ngrok_host}'
    if ngrok_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(ngrok_origin)

if PUBLIC_BASE_URL and PUBLIC_BASE_URL.startswith('https://'):
    if PUBLIC_BASE_URL not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(PUBLIC_BASE_URL)

for default_origin in [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://*.ngrok-free.dev',
    'https://*.ngrok.io',
]:
    if default_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(default_origin)

# Remove duplicates and empty strings
ALLOWED_HOSTS = list({h for h in ALLOWED_HOSTS if h})
CSRF_TRUSTED_ORIGINS = list({o for o in CSRF_TRUSTED_ORIGINS if o})
STATIC_VERSION = config('STATIC_VERSION', default='1')

if not DEBUG and SECRET_KEY == 'django-insecure-test-key':
    raise ValueError('SECRET_KEY must be set from environment in production')

# Fix AutoField warnings
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_NAME = config('SESSION_COOKIE_NAME', default='mailflow_session_v2')
SESSION_EXPIRE_AT_BROWSER_CLOSE = config('SESSION_EXPIRE_AT_BROWSER_CLOSE', default=True, cast=bool)
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=60 * 60 * 8, cast=int)
SESSION_SAVE_EVERY_REQUEST = config('SESSION_SAVE_EVERY_REQUEST', default=True, cast=bool)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

IS_RUNSERVER = 'runserver' in sys.argv

# Never force HTTPS for local development server execution.
# This prevents accidental browser HTTPS/HSTS loops on localhost.
if DEBUG or IS_RUNSERVER:
    FORCE_HTTPS = False
else:
    FORCE_HTTPS = config('FORCE_HTTPS', default=True, cast=bool)

SECURE_SSL_REDIRECT = False if (DEBUG or IS_RUNSERVER) else FORCE_HTTPS
SESSION_COOKIE_SECURE = False if (DEBUG or IS_RUNSERVER) else config('SESSION_COOKIE_SECURE', default=FORCE_HTTPS, cast=bool)
CSRF_COOKIE_SECURE = False if (DEBUG or IS_RUNSERVER) else config('CSRF_COOKIE_SECURE', default=FORCE_HTTPS, cast=bool)

# Trust reverse proxy protocol headers (ngrok / load balancers)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# In HTTPS-enforced environments only:
if FORCE_HTTPS:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',


    # Third Party
    'compressor',
    'django_ratelimit',
    'widget_tweaks',

    # Local Apps
    'apps.accounts',
    'apps.senders',
    'apps.campaigns',
    'apps.intelligence',
    'apps.dashboard',
    'apps.contacts',
    'apps.automations',
]

MIDDLEWARE = [
    'core.middleware.DevHTTPMiddleware',  # Remove HSTS headers in dev to prevent HTTPS caching
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.CSPMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates', BASE_DIR / 'apps' / 'contacts' / 'templates'],
          # root templates folder
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'core.context_processors.static_version',
                'apps.dashboard.context_processors.dashboard_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / "db.sqlite3",  # Creates a db file in your project folder
    }
}

CACHE_BACKEND = config('CACHE_BACKEND', default='locmem')

if CACHE_BACKEND == 'redis':
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': config('REDIS_CACHE_URL', default='redis://localhost:6379/0'),
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'mailflow-local-cache',
        }
    }

# Ratelimit settings
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_FAIL_OPEN = False

# Database (PostgreSQL)
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': config('DB_NAME'),
#         'USER': config('DB_USER'),
#         'PASSWORD': config('DB_PASSWORD'),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='5432'),
#     }
# }

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Tailwind/Compressor
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

# Email Configuration
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    _auto_email_backend = 'django.core.mail.backends.smtp.EmailBackend'
elif DEBUG:
    _auto_email_backend = 'django.core.mail.backends.console.EmailBackend'
else:
    raise ValueError("EMAIL_HOST_USER and EMAIL_HOST_PASSWORD must be set in production")

EMAIL_BACKEND = config('EMAIL_BACKEND', default=_auto_email_backend)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
SERVER_EMAIL = config('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=20, cast=int)

# Public base URL used for email tracking links (opens/clicks). Example: https://your-domain.com
TRACKING_BASE_URL = config('TRACKING_BASE_URL', default=PUBLIC_BASE_URL).strip().rstrip('/')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'level': 'WARNING',
        },
    },
    'root': {'handlers': ['console', 'file'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        'apps': {'handlers': ['console', 'file'], 'level': 'DEBUG', 'propagate': False},
    },
}

# Custom user
AUTH_USER_MODEL = 'accounts.User'

# Auth URLs
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# SMTP Encryption Key
SMTP_ENCRYPTION_KEY = config('SMTP_ENCRYPTION_KEY', default=os.environ.get('ENCRYPTION_KEY', ''))
ENCRYPTION_KEY = config('ENCRYPTION_KEY', default=os.environ.get('ENCRYPTION_KEY', ''))

# Generate deterministic development key if not set
if not ENCRYPTION_KEY:
    if DEBUG:
        # Deterministic development key so encrypted sender passwords survive restarts
        ENCRYPTION_KEY = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode('utf-8')).digest()).decode('utf-8')
    else:
        raise ValueError("ENCRYPTION_KEY must be set in production environment")

# Clean the key
ENCRYPTION_KEY = ENCRYPTION_KEY.strip()

# Machine Learning
ML_MODEL_PATH = Path(config('ML_MODEL_PATH', default=str(BASE_DIR / 'models_ml' / 'spam_model.pkl')))
ML_VECTORIZER_PATH = Path(config('ML_VECTORIZER_PATH', default=str(BASE_DIR / 'models_ml' / 'tfidf_vectorizer.pkl')))

# Silencing django-ratelimit strict cache checks for development
SILENCED_SYSTEM_CHECKS = ['django_ratelimit.E003']
