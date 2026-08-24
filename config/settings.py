"""Django settings for the Interview Trainer project.

Environment-driven configuration (12-factor style). All secrets and
environment-specific values are read from environment variables or a `.env`
file at the project root (see `.env.example`).
"""

from pathlib import Path
import os

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths & environment
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(key: str, default: str = "False") -> bool:
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------
def _get_secret_key() -> str:
    """Retrieve and sanitize Django SECRET_KEY from environment variables.

    Checks SECRET_KEY, DJANGO_SECRET_KEY, and SECRET while stripping quotes and whitespace.
    Guarantees a non-empty key fallback for development/preview environments to prevent
    django.core.exceptions.ImproperlyConfigured errors.
    """
    for var_name in ("SECRET_KEY", "DJANGO_SECRET_KEY", "SECRET", "secret_key"):
        val = os.getenv(var_name)
        if val is not None:
            cleaned = val.strip().strip("'").strip('"').strip()
            if cleaned:
                return cleaned

    return "django-insecure-dev-only-key-change-me-in-production"


SECRET_KEY = _get_secret_key()


DEBUG = env_bool("DEBUG", "True")

# Host header validation — supports Vercel wildcards, local development, and custom domains
ALLOWED_HOSTS_ENV = os.getenv("ALLOWED_HOSTS", "*")
if ALLOWED_HOSTS_ENV.strip() == "*":
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_ENV.split(",") if h.strip()]
    for fallback in [".vercel.app", ".now.sh", "localhost", "127.0.0.1", "0.0.0.0"]:
        if fallback not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(fallback)

# CSRF trusted origins for HTTPS reverse proxies / Vercel
CSRF_TRUSTED_ORIGINS = [
    "https://*.vercel.app",
    "https://*.now.sh",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
_csrf_env = os.getenv("CSRF_TRUSTED_ORIGINS", "")
if _csrf_env:
    for _origin in _csrf_env.split(","):
        _origin = _origin.strip()
        if _origin and _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

# Reverse proxy / Vercel Edge configuration
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Project apps
    "accounts.apps.AccountsConfig",
    "candidates.apps.CandidatesConfig",
    "dashboard.apps.DashboardConfig",
    "assessments.apps.AssessmentsConfig",
    "results.apps.ResultsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — Zero-setup SQLite Default / Cloud DATABASE_URL / Optional MySQL
# ---------------------------------------------------------------------------
def _get_database_config(debug_mode: bool) -> dict:
    import dj_database_url

    # 1. Explicit DATABASE_URL in environment (e.g. Cloud PostgreSQL or MySQL)
    env_db_url = os.getenv("DATABASE_URL", "").strip().strip("'").strip('"')
    if env_db_url:
        try:
            cfg = dj_database_url.parse(env_db_url, conn_max_age=600, conn_health_checks=True)
            if cfg and cfg.get("ENGINE"):
                return cfg
        except Exception:
            pass

    # 2. Explicit MySQL configured via environment
    db_host = os.getenv("DB_HOST", "").strip().strip("'").strip('"')
    if db_host and (env_bool("USE_MYSQL", "False") or (db_host.lower() != "localhost" and os.getenv("DB_USER"))):
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "interview_trainer"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": db_host,
            "PORT": os.getenv("DB_PORT", "3306") or "3306",
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }

    # 3. Production serverless on Vercel
    if not debug_mode:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "/tmp/db.sqlite3",
            "OPTIONS": {
                "timeout": 30,
            },
        }

    # 4. Local development default (zero local server requirement)
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 30,
        },
    }


DATABASES = {
    "default": _get_database_config(DEBUG),
}

# Ensure SQLite enables Write-Ahead Logging (WAL) and 30s busy timeout for concurrent threads/tests
from django.db.backends.signals import connection_created

def _configure_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        try:
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA busy_timeout=30000;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass

connection_created.connect(_configure_sqlite_pragmas)




# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LOGIN_URL = "home"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

WHITENOISE_USE_FINDERS = True
WHITENOISE_MANIFEST_STRICT = False

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Email / SMTP
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587") or 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", "True")
EMAIL_HOST_USER = os.getenv("EMAIL_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@interviewtrainer.local")

# ---------------------------------------------------------------------------
# Security Headers & Cookie Policies (Enforced when DEBUG is False)
# ---------------------------------------------------------------------------
if not DEBUG:
    CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", "True")
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", "True")
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", "False")
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0") or "0")
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", "False")
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", "False")

# ---------------------------------------------------------------------------
# Platform Configuration
# ---------------------------------------------------------------------------
CRON_SECRET_KEY = os.getenv("CRON_SECRET_KEY", "dev-cron-secret-key-12345")
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "localhost:8000")

