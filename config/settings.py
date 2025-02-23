import os
import sys
from pathlib import Path

from dotenv import load_dotenv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

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
    "debug_toolbar",
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

    "articles",
    "core",
    "users",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django_minify_html.middleware.MinifyHtmlMiddleware",
    "config.middleware.ErrorLoggingMiddleware",
    "config.middleware.TimezoneMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

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


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ["DB_PORT"],
    }
}


# User

AUTH_USER_MODEL = "users.User"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "articles"
LOGOUT_REDIRECT_URL = LOGIN_URL

SITE_ID = 2

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
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
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


# Logging

LOGGING_ENABLED = bool(int(os.getenv("ENABLE_LOGGING", 0)))

LOGS_PATH = os.path.join(BASE_DIR, os.getenv("LOGS_PATH", "logs"))

if LOGGING_ENABLED:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default_formatter": {
                "format": "{asctime} - [{levelname}] - {filename}:{funcName}:{lineno} - {message}",
                "style": "{",
            },
            "uncatched_errors_formatter": {
                "format": "{asctime} - [{levelname}] - {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
            },
            "default_file": {
                "level": "INFO",
                "class": "logging.FileHandler",
                "filename": os.path.join(LOGS_PATH, "info.log"),
                "formatter": "default_formatter",
            },
            "uncatched_errors_file": {
                "level": "ERROR",
                "class": "logging.FileHandler",
                "filename": os.path.join(LOGS_PATH, "uncatched_errors.log"),
                "formatter": "uncatched_errors_formatter",
            },
        },
        "loggers": {
            "default_logger": {
                "handlers": ["default_file"],
                "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
                "propagate": False,
            },
            "uncatched_errors_logger": {
                "handlers": ["uncatched_errors_file"],
                "level": "ERROR",
                "propagate": False,
            },
        },
    }


# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
DEFAULT_USER_TZ = os.getenv("DEFAULT_USER_TZ", "Europe/London")  # default time zone for rendering
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = "staticfiles"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]


MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")


X_FRAME_OPTIONS = "SAMEORIGIN"


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Chrispy forms

CRISPY_TEMPLATE_PACK = "bootstrap4"


# hCaptcha

HCAPTCHA_SITEKEY = os.getenv("HCAPTCHA_SITEKEY", "")
HCAPTCHA_SECRET = os.getenv("HCAPTCHA_SECRET", "")


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
    "plugins": "image link autolink media advlist lists table codesample charmap fullscreen",
    "toolbar": [
        "undo redo | fullscreen | hr image media table codesample blockquote | subscript superscript charmap",
        "blocks | bullist numlist indent outdent | alignleft aligncenter alignright alignjustify lineheight",
        "fontfamily fontsize | bold italic underline strikethrough forecolor backcolor | removeformat",
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
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}


# Redis

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = os.environ["REDIS_PORT"]


# Cache

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
    "select2": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/2",
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
            "hosts": [(os.environ["REDIS_HOST"], os.environ["REDIS_PORT"])],
        },
    },
}


# Celery

CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"


# Select2

SELECT2_CACHE_BACKEND = "select2"


# Emails

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ["EMAIL_HOST"]
EMAIL_PORT = os.environ["EMAIL_PORT"]
EMAIL_HOST_USER = os.environ["EMAIL_HOST_USER"]
EMAIL_HOST_PASSWORD = os.environ["EMAIL_HOST_PASSWORD"]
EMAIL_USE_TLS = os.environ["EMAIL_USE_TLS"]
