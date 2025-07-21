import logging
import os
import sys
from pathlib import Path

import sentry_sdk
from django.contrib.messages import constants as messages
from dotenv import load_dotenv
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, os.path.join(BASE_DIR, "apps"))


# Load env. variables
DOTENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(DOTENV_PATH, override=True)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["SECRET_KEY"]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(int(os.environ["DEBUG"]))

ALLOWED_HOSTS = os.environ["ALLOWED_HOSTS"].split(" ")

if DEBUG:
    INTERNAL_IPS = ["127.0.0.1"]

SCHEME = os.environ["SCHEME"]
DOMAIN_NAME = os.environ["DOMAIN_NAME"]

if SCHEME.lower() == "https":
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


ALLOW_NON_ROUTABLE_IPS = bool(int(os.getenv("ALLOW_NON_ROUTABLE_IPS", "0")))


# Application definition

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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
    "cachalot",
    "django_celery_beat",
    "articles",
    "users",
    "notifications",
    "core",
]

if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]


MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django_minify_html.middleware.MinifyHtmlMiddleware",
    "core.middleware.TimezoneMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if DEBUG:
    MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]


ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.include_user_notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Messages

MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": int(os.getenv("DB_PORT", "5432")),
        "CONN_MAX_AGE": int(os.getenv("DB_CONNECTION_MAX_AGE", "60")),
    }
}


# User

AUTH_USER_MODEL = "users.User"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "articles"
LOGOUT_REDIRECT_URL = LOGIN_URL

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "users.auth_backends.EmailOrUsernameAuthenticationBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_ADAPTER = "users.adapters.AccountAdapter"
ACCOUNT_EMAIL_VERIFICATION = "none"

SOCIALACCOUNT_ONLY = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "APP": {
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        },
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "EMAIL_AUTHENTICATION": True,
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Sentry

USE_SENTRY = bool(int(os.getenv("USE_SENTRY", "0")))

if USE_SENTRY:
    SENTRY_DSN = os.environ["SENTRY_DSN"]
    SENTRY_TRACES_SAMPLE_RATE = float(os.environ["SENTRY_TRACES_SAMPLE_RATE"])
    SENTRY_SEND_DEFAULT_PII = bool(int(os.getenv("SENTRY_SEND_DEFAULT_PII", "1")))

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=SENTRY_SEND_DEFAULT_PII,
    )


# Logging

LOGGING_ENABLED = bool(int(os.getenv("ENABLE_LOGGING", "0")))
LOG_TO_CONSOLE = bool(int(os.getenv("LOG_TO_CONSOLE", "0")))
LOGS_PATH = os.path.join(BASE_DIR, os.getenv("LOGS_PATH", "logs"))

if LOGGING_ENABLED:
    os.makedirs(LOGS_PATH, exist_ok=True)

    logging_handlers = {
        "file_general": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "general.log"),
            "maxBytes": 1024 * 1024 * 50,  # 50 MB
            "backupCount": 5,
            "formatter": "default",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "errors.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "default",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_uncaught_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "uncaught_errors.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "exception",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_celery_worker_general": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "celery_worker.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "default",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_celery_worker_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "celery_worker_errors.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "exception",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_celery_beat_general": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "celery_beat.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "default",
            "filters": ["host_name"],
            "delay": True,
        },
        "file_celery_beat_errors": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_PATH, "celery_beat_errors.log"),
            "maxBytes": 1024 * 1024 * 50,
            "backupCount": 5,
            "formatter": "exception",
            "filters": ["host_name"],
            "delay": True,
        },
    }

    if LOG_TO_CONSOLE:
        logging_handlers["console"] = {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
        }

    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "host_name": {"()": "core.logging_filters.HostNameFilter"},
        },
        "formatters": {
            "default": {
                "format": (
                    "{asctime} - [{levelname}] - {host_name}:{processName}:{process}\n"
                    "{name}:{funcName}:{lineno} - {message}"
                ),
                "style": "{",
            },
            "exception": {
                "format": "{asctime} - [{levelname}] - {host_name}:{processName}:"
                "{process}\n{message}",
                "style": "{",
            },
        },
        "handlers": logging_handlers,
        "root": {
            "handlers": [
                h
                for h in ["console", "file_general", "file_errors"]
                if h in logging_handlers
            ],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
        },
        "loggers": {
            "django": {
                "handlers": [h for h in ["console"] if h in logging_handlers],
                "level": "INFO",
                "propagate": False,
            },
            "django.server": {
                "handlers": [h for h in ["console"] if h in logging_handlers],
                "level": "INFO",
                "propagate": False,
            },
            "django.request": {
                "handlers": [
                    h
                    for h in ["console", "file_uncaught_errors"]
                    if h in logging_handlers
                ],
                "level": "INFO",
                "propagate": False,
            },
            "daphne": {
                "handlers": [
                    h for h in ["console", "file_errors"] if h in logging_handlers
                ],
                "level": "INFO",
                "propagate": False,
            },
            "celery": {
                "handlers": [
                    h
                    for h in [
                        "file_celery_worker_general",
                        "file_celery_worker_errors",
                    ]
                    if h in logging_handlers
                ],
                "level": "INFO",
                "propagate": False,
            },
            "celery.beat": {
                "handlers": [
                    h
                    for h in ["file_celery_beat_general", "file_celery_beat_errors"]
                    if h in logging_handlers
                ],
                "level": "INFO",
                "propagate": False,
            },
        },
    }


# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"

# Default time zone for frontend rendering
DEFAULT_USER_TZ = os.getenv("DEFAULT_USER_TZ", "Europe/London")

USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = "staticfiles"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]


MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

ALLOWED_UPLOAD_FILE_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
}

MAX_UPLOAD_FILE_SIZE = int(
    int(os.getenv("MAX_UPLOAD_FILE_SIZE", str(5 * 1024 * 1024)))
)  # 5MB default


X_FRAME_OPTIONS = "SAMEORIGIN"


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Chrispy forms

CRISPY_TEMPLATE_PACK = "bootstrap4"


# hCaptcha

HCAPTCHA_SITEKEY = os.environ["HCAPTCHA_SITEKEY"]
HCAPTCHA_SECRET = os.environ["HCAPTCHA_SECRET"]


# TinyMCE

TINYMCE_JS_URL = "https://cdn.jsdelivr.net/npm/tinymce@7.3.0/tinymce.min.js"

TINYMCE_EXTRA_MEDIA = {
    "js": ["js/tinymce-upload-handler.js"],
}

TINYMCE_DEFAULT_CONFIG = {
    "theme": "silver",
    "height": 500,
    "width": "100%",
    "menubar": False,
    "plugins": (
        "image link autolink media advlist lists table codesample charmap" "fullscreen"
    ),
    "toolbar": [
        (
            "undo redo | fullscreen | hr image media table codesample blockquote | "
            "subscript superscript charmap"
        ),
        (
            "blocks | bullist numlist indent outdent | "
            "alignleft aligncenter alignright alignjustify lineheight"
        ),
        (
            "fontfamily fontsize | "
            "bold italic underline strikethrough forecolor backcolor | removeformat"
        ),
    ],
    "file_picker_types": "image media",
    "images_upload_url": "/tinymce/upload",
    "images_upload_handler": "tinymceUploadHandler",
    "automatic_uploads": False,
    "promotion": False,
    "license_key": "gpl",
}


# AWS

USE_AWS_S3 = bool(int(os.environ["USE_AWS_S3"]))

if USE_AWS_S3:
    AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    AWS_S3_FILE_OVERWRITE = False


# Storages

STORAGES = {
    "default": {
        "BACKEND": (
            "storages.backends.s3boto3.S3Boto3Storage"
            if USE_AWS_S3
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": ("django.contrib.staticfiles.storage.StaticFilesStorage"),
    },
}


# Redis

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


# Cache

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
    "select2": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
}


# Django Channels

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
        },
    },
}


# Celery

CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Select2

SELECT2_CACHE_BACKEND = "select2"


# Emails

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ["EMAIL_HOST_USER"]
EMAIL_HOST_PASSWORD = os.environ["EMAIL_HOST_PASSWORD"]
EMAIL_USE_TLS = bool(int(os.getenv("EMAIL_USE_TLS", "1")))
