import logging
import os
import sys
from datetime import timedelta

import sentry_sdk
from celery.schedules import crontab
from django.contrib.messages import constants as messages
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from .env import BASE_DIR, env


APPS_DIR = BASE_DIR / "apps"
sys.path.insert(0, str(APPS_DIR))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

if DEBUG:
    INTERNAL_IPS = ["127.0.0.1"]

SCHEME = env("SCHEME")
DOMAIN_NAME = env("DOMAIN_NAME")

if SCHEME.lower() == "https":
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


ALLOW_NON_ROUTABLE_IPS = env.bool("ALLOW_NON_ROUTABLE_IPS", default=False)


# Application definition

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
    "cachalot",
    "django_celery_beat",
    "articles",
    "users",
    "notifications",
    "core",
    "django_cleanup.apps.CleanupConfig",
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
    "django_ratelimit.middleware.RatelimitMiddleware",
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
                "notifications.context_processors.include_notification_count",
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
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env.int("DB_PORT", default=5432),
        "CONN_MAX_AGE": env.int("DB_CONNECTION_MAX_AGE", default=60),
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
ACCOUNT_CHANGE_EMAIL = False

SOCIALACCOUNT_ADAPTER = "users.adapters.SocialAccountAdapter"
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_ONLY = False
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "APP": {
            "client_id": env("GOOGLE_OAUTH_CLIENT_ID"),
            "secret": env("GOOGLE_OAUTH_CLIENT_SECRET"),
        },
        "AUTH_PARAMS": {
            "access_type": "online",
            "prompt": "select_account",
        },
        "EMAIL_AUTHENTICATION": True,
        "VERIFIED_EMAIL": True,
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

PASSWORD_RESET_TIMEOUT = 60 * 15  # 15 min

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

USE_SENTRY = env.bool("USE_SENTRY", default=False)

if USE_SENTRY:
    SENTRY_DSN = env("SENTRY_DSN")
    SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE")
    SENTRY_SEND_DEFAULT_PII = env.bool("SENTRY_SEND_DEFAULT_PII", default=True)

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=SENTRY_SEND_DEFAULT_PII,
    )


# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"

# Default time zone for frontend rendering
DEFAULT_USER_TZ = env("DEFAULT_USER_TZ", default="Europe/London")

USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = "staticfiles"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]


MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Allowed root URLs for media files (for validating external image URLs in TinyMCE)
MEDIA_ALLOWED_ROOT_URLS = env.list("MEDIA_ALLOWED_ROOT_URLS")

ALLOWED_IMAGE_UPLOAD_FILE_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

MAX_IMAGE_UPLOAD_FILE_SIZE = env.int(
    "MAX_IMAGE_UPLOAD_FILE_SIZE", default=5 * 1024 * 1024  # 5MB default
)


X_FRAME_OPTIONS = "SAMEORIGIN"


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Chrispy forms

CRISPY_TEMPLATE_PACK = "bootstrap4"


# hCaptcha

HCAPTCHA_SITEKEY = env("HCAPTCHA_SITEKEY")
HCAPTCHA_SECRET = env("HCAPTCHA_SECRET")


# TinyMCE

TINYMCE_JS_URL = "https://cdn.jsdelivr.net/npm/tinymce@7.3.0/tinymce.min.js"

TINYMCE_EXTRA_MEDIA = {
    "js": ["js/tinymce-upload-handler.js", "js/tinymce-setup.js"],
}

TINYMCE_DEFAULT_CONFIG = {
    "theme": "silver",
    "height": 750,
    "width": "100%",
    "menubar": False,
    "promotion": False,
    "license_key": "gpl",
    "plugins": (
        "autolink link image advlist lists table codesample charmap fullscreen"
    ),
    "toolbar": [
        "undo redo | fullscreen | hr uploadimage table codesample blockquote | charmap",
        "blocks | bullist numlist indent outdent | alignleft aligncenter alignright"
        " alignjustify",
        "fontfamily fontsize | bold italic underline strikethrough | removeformat",
    ],
    "file_picker_types": "image",
    "image_url_input": False,
    "images_upload_url": "/tinymce/upload/",
    "images_upload_handler": "tinymceUploadHandler",
    "automatic_uploads": False,
    "convert_urls": False,
    "relative_urls": False,
    "remove_script_host": True,
    "invalid_elements": (
        "script,iframe,object,embed,form,input,button,select,textarea,style"
    ),
    "setup": "tinymceCustomSetup",
    "content_css": ["/static/css/tinymce-content.css"],
    "object_resizing": "table",
}


# AWS

USE_AWS_S3 = env.bool("USE_AWS_S3")

if USE_AWS_S3:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
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

REDIS_HOST = env("REDIS_HOST")
REDIS_PORT = env.int("REDIS_PORT", default=6379)


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


# Rate limiting

RATELIMIT_ENABLE = env.bool("RATELIMIT_ENABLE", default=True)

RATELIMIT_VIEW = "core.ratelimit.ratelimited"


# Django Channels

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
            "capacity": 50,  # max queued messages per channel
            "expiry": 10,  # seconds; drop queued messages after this
        },
    },
}


# Celery

CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = env.bool(
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP", default=True
)


CELERY_BEAT_SCHEDULE = {
    "articles.cleanup-unused-media": {
        "task": "articles.tasks.cleanup_unused_article_inline_media_task",
        "schedule": timedelta(hours=1),
    },
    "articles.sync-view-counts": {
        "task": "articles.tasks.sync_article_views_task",
        "schedule": timedelta(minutes=5),
    },
    "articles.sync-article-likes-counts": {
        "task": "articles.tasks.sync_article_likes_count_task",
        "schedule": timedelta(hours=1),
    },
    "articles.sync-article-comment-counts": {
        "task": "articles.tasks.sync_article_comments_count_task",
        "schedule": timedelta(hours=1),
    },
    "articles.sync-comment-likes-counts": {
        "task": "articles.tasks.sync_comment_likes_count_task",
        "schedule": timedelta(hours=1),
    },
    "notifications.cleanup-old-read": {
        "task": "notifications.tasks_retention.cleanup_old_read_notifications_task",
        "schedule": timedelta(hours=1),
    },
    "notifications.sync-unread-counts": {
        "task": "notifications.tasks.sync_unread_notification_counts_task",
        "schedule": crontab(minute=0, hour="*/6"),  # every 6 hours
    },
    "users.delete-expired-pending-email-changes": {
        "task": "users.tasks.delete_expired_pending_email_changes_task",
        "schedule": timedelta(hours=1),
    },
}

# Select2

SELECT2_CACHE_BACKEND = "select2"


# Emails

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)


from .articles import *  # noqa pylint: disable=W0401,W0614
from .logging import LOGGING  # noqa
from .notifications import *  # noqa pylint: disable=W0401,W0614
