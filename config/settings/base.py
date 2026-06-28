import sys

from django.contrib.messages import constants as messages

from .env import BASE_DIR, env


APPS_DIR = BASE_DIR / "apps"
sys.path.insert(0, str(APPS_DIR))


SECRET_KEY = env("SECRET_KEY", default="unsafe-secret-key")
DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

DOMAIN_NAME = env("DOMAIN_NAME", default="localhost")

SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = None
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False


ALLOW_NON_ROUTABLE_IPS = env.bool("ALLOW_NON_ROUTABLE_IPS", default=False)

X_FRAME_OPTIONS = "SAMEORIGIN"


INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "tinymce",
    "crispy_forms",
    "crispy_bootstrap4",
    "hcaptcha_field",
    "taggit",
    "django_filters",
    "django_select2",
    "storages",
    "channels",
    "channels_redis",
    "django_minify_html",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "django_celery_beat",
    "articles",
    "users",
    "notifications",
    "core",
    "django_cleanup.apps.CleanupConfig",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django_minify_html.middleware.MinifyHtmlMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.TimezoneMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_ratelimit.middleware.RatelimitMiddleware",
]


ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.include_notification_count",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="django_articles"),
        "USER": env("DB_USER", default="postgres"),
        "PASSWORD": env("DB_PASSWORD", default="postgres"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env.int("DB_PORT", default=5432),
        "CONN_MAX_AGE": env.int("DB_CONNECTION_MAX_AGE", default=60),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Messages

MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}


# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"

# Default time zone for frontend rendering
DEFAULT_USER_TZ = env("DEFAULT_USER_TZ", default="Europe/London")

USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]


# Crispy forms

CRISPY_TEMPLATE_PACK = "bootstrap4"


# Select2

SELECT2_CACHE_BACKEND = "select2"


from .components.articles import *  # noqa pylint: disable=W0401,W0614
from .components.auth import *  # noqa pylint: disable=W0401,W0614
from .components.cache import *  # noqa pylint: disable=W0401,W0614
from .components.celery import *  # noqa pylint: disable=W0401,W0614
from .components.channels import *  # noqa pylint: disable=W0401,W0614
from .components.email import *  # noqa pylint: disable=W0401,W0614
from .components.hcaptcha import *  # noqa pylint: disable=W0401,W0614
from .components.logging import LOGGING  # noqa
from .components.media import *  # noqa pylint: disable=W0401,W0614
from .components.notifications import *  # noqa pylint: disable=W0401,W0614
from .components.sentry import *  # noqa pylint: disable=W0401,W0614
from .components.tinymce import *  # noqa pylint: disable=W0401,W0614
from .components.users import *  # noqa pylint: disable=W0401,W0614
