"""
Django settings for Online Attendance Tracking System project.

Generated for industry-standard production-ready foundation.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from django.contrib.messages import constants as messages

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

from django.core.exceptions import ImproperlyConfigured

# SECURITY WARNING: don't run with debug turned on in production!
# Defaults to False for security. Set DEBUG=True in local .env for development.
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-attendance-tracking-system-change-in-production'
    elif os.getenv('VERCEL'):
        # Fallback to prevent hard crash on Vercel preview before env vars are populated in dashboard
        SECRET_KEY = 'django-insecure-vercel-temporary-key-replace-in-production-dashboard'
    else:
        raise ImproperlyConfigured(
            "CRITICAL: The SECRET_KEY environment variable is missing. "
            "In production environments (DEBUG=False), a cryptographically strong SECRET_KEY must be configured."
        )

# Hosts / Domain names that this Django site can serve
# Explicitly permit local environments, testserver, and the verified Vercel production deployment domain.
BASE_ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'testserver',
    'online-attendance-tracker-bdkq.vercel.app',
    '.vercel.app',  # Permits Vercel deployment subdomains (e.g. preview and production URLs)
]

# Read additional hostnames from environment variables (supports DJANGO_ALLOWED_HOSTS and ALLOWED_HOSTS)
allowed_hosts_env = os.getenv('DJANGO_ALLOWED_HOSTS') or os.getenv('ALLOWED_HOSTS', '')
if allowed_hosts_env:
    extra_hosts = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]
else:
    extra_hosts = []

# If Vercel dynamically sets VERCEL_URL (e.g. preview deployment URL)
vercel_url = os.getenv('VERCEL_URL')
if vercel_url:
    clean_vurl = vercel_url.strip()
    extra_hosts.extend([clean_vurl, f".{clean_vurl}"])

# Deduplicate while preserving order; never use wildcard '*'
ALLOWED_HOSTS = list(dict.fromkeys(BASE_ALLOWED_HOSTS + extra_hosts))

# Trusted origins for CSRF protection on HTTPS (Django 4.0+)
BASE_CSRF_TRUSTED_ORIGINS = [
    'https://online-attendance-tracker-bdkq.vercel.app',
    'https://*.vercel.app',
]

csrf_trusted_env = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS') or os.getenv('CSRF_TRUSTED_ORIGINS', '')
if csrf_trusted_env:
    extra_csrf = [origin.strip() for origin in csrf_trusted_env.split(',') if origin.strip()]
else:
    extra_csrf = []

# If Vercel dynamically sets VERCEL_URL
if vercel_url:
    clean_vurl = vercel_url.strip()
    if not clean_vurl.startswith(('http://', 'https://')):
        extra_csrf.append(f"https://{clean_vurl}")
    else:
        extra_csrf.append(clean_vurl)

CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(BASE_CSRF_TRUSTED_ORIGINS + extra_csrf))





# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party packages
    'crispy_forms',
    'crispy_bootstrap5',

    # Local application modules
    'accounts.apps.AccountsConfig',
    'academics.apps.AcademicsConfig',
    'students.apps.StudentsConfig',
    'attendance.apps.AttendanceConfig',
    'dashboard.apps.DashboardConfig',
]

MIDDLEWARE = [
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
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database Configuration
# Supports DATABASE_URL / POSTGRES_URL (PostgreSQL, Neon, Supabase, Vercel Postgres) via dj-database-url,
# discrete DB_* variables, and falls back to SQLite for local development or ephemeral serverless preview.
import dj_database_url

DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=int(os.getenv('CONN_MAX_AGE', 0 if os.getenv('VERCEL') else 600)),
            conn_health_checks=True,
            ssl_require=True if (os.getenv('VERCEL') or 'neon.tech' in DATABASE_URL or 'supabase' in DATABASE_URL) else False,
        )
    }
elif os.getenv('DB_ENGINE'):
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE'),
            'NAME': os.getenv('DB_NAME', ''),
            'USER': os.getenv('DB_USER', ''),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', ''),
            'PORT': os.getenv('DB_PORT', ''),
            'CONN_MAX_AGE': int(os.getenv('CONN_MAX_AGE', 0 if os.getenv('VERCEL') else 600)),
            'CONN_HEALTH_CHECKS': True,
        }
    }
elif os.getenv('VERCEL'):
    # On Vercel serverless, /var/task is strictly read-only.
    # /tmp is the only writable directory in serverless execution.
    import shutil
    tmp_db = Path('/tmp') / 'db.sqlite3'
    bundled_db = BASE_DIR / 'db.sqlite3'
    if bundled_db.exists() and not tmp_db.exists():
        try:
            shutil.copy2(bundled_db, tmp_db)
        except Exception:
            pass
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': tmp_db,
            'OPTIONS': {
                'timeout': 20,
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Custom User Model
AUTH_USER_MODEL = 'accounts.User'


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise storage configuration
# Uses compressed storage in production; falls back to staticfiles finders for serverless resilience
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# Allow WhiteNoise to fall back directly to STATICFILES_DIRS when staticfiles/ is not pre-collected
WHITENOISE_USE_FINDERS = True
WHITENOISE_MANIFEST_STRICT = False


# Media files (User uploads, avatars, documents)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Crispy Forms Configuration (Bootstrap 5)
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'


# Authentication URL Redirection
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGOUT_REDIRECT_URL = 'accounts:login'


# Django Messages Styling for Bootstrap 5
MESSAGE_TAGS = {
    messages.DEBUG: 'secondary',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}


# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

# Attendance Business Rules Configuration
# Teachers cannot submit or edit attendance older than this many calendar days in the past.
# Administrators can override this restriction when necessary.
MAX_BACKDATED_ATTENDANCE_DAYS = int(os.getenv('MAX_BACKDATED_ATTENDANCE_DAYS', 7))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session and Cookie Security Configuration
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = int(os.getenv('SESSION_COOKIE_AGE', 1209600))  # 14 days default
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Reverse Proxy SSL Header (for Vercel, Nginx, Caddy, AWS ALB, Cloudflare, etc.)
# Vercel automatically terminates SSL and passes HTTP_X_FORWARDED_PROTO = 'https'
if os.getenv('VERCEL') or os.getenv('USE_X_FORWARDED_PROTO', 'False').lower() in ('true', '1', 't'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    # Production Security Hardening
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'
    
    # HTTPS / SSL settings
    # Default to True in production; can be set to False if SSL termination is handled upstream
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 't')
    
    # HTTP Strict Transport Security (HSTS)
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_SUBDOMAINS', 'True').lower() in ('true', '1', 't')
    SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', 'True').lower() in ('true', '1', 't')
else:
    # Development security defaults
    X_FRAME_OPTIONS = 'DENY'
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0

# Production Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}


