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
# Database — PostgreSQL via DATABASE_URL (with SQLite fallback)
# ---------------------------------------------------------------------------
import dj_database_url

DATABASES = {
    "default": dj_database_url.config(
        default="postgresql://skilltest:skilltest3620@db.quantbots.co/skilltest",
        conn_max_age=600,
        conn_health_checks=True,
    )
}



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
TIME_ZONE = "UTC"
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

# ---------------------------------------------------------------------------
# Platform Configuration
# ---------------------------------------------------------------------------
CRON_SECRET_KEY = os.getenv("CRON_SECRET_KEY", "dev-cron-secret-key-12345")
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "localhost:8000")
