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


# Application definition

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "ckeditor",
    "ckeditor_uploader",
    "crispy_forms",
    "debug_toolbar",
    "taggit",
    "storages",
    "channels",
    "channels_redis",

    "articles",
    "users",
    "notifications",
]

MIDDLEWARE = [
    "config.middleware.ErrorLoggingMiddleware",
    "config.middleware.TimezoneMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
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
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ["DB_PORT"],
    }
}


# User
LOGIN_REDIRECT_URL = "home"


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

# Whitenoise
USE_WHITENOISE = bool(int(os.getenv("USE_WHITENOISE", 0)))

if USE_WHITENOISE:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
    WHITENOISE_USE_FINDERS = True

MEDIA_URL = "/media/"
MEDIA_ROOT = "media"


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Chrispy forms

CRISPY_TEMPLATE_PACK = "bootstrap4"

# CKEditor

CKEDITOR_UPLOAD_PATH = "ckeditor_uploads/"
CKEDITOR_IMAGE_BACKEND = "pillow"
CKEDITOR_BROWSE_SHOW_DIRS = True
CKEDITOR_RESTRICT_BY_USER = True

CKEDITOR_CONFIGS = {
    "default": {
        "toolbar": [
            ["Undo", "Redo", "Maximize"],
            ["PasteFromWord"],
            ["Find", "Replace", "SelectAll"],
            ["Bold", "Italic", "Underline", "Strike", "Subscript", "Superscript"],
            ["Font", "FontSize", "TextColor", "BGColor", "Styles", "Format", "RemoveFormat"],
            ["JustifyLeft", "JustifyCenter", "JustifyRight", "JustifyBlock"],
            ["NumberedList", "BulletedList", "Outdent", "Indent", "BidiLtr", "BidiRtl"],
            ["Link", "Unlink", "Anchor"],
            ["Image", "Iframe", "Table", "HorizontalRule", "Smiley", "SpecialChar", "Blockquote"],
            ["Source", "Preview"],
        ],
        "width": "100%",
    },
}

# AWS

USE_AWS_S3 = bool(int(os.environ["USE_AWS_S3"]))

if USE_AWS_S3:
    AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    AWS_S3_FILE_OVERWRITE = False

    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"


# Heroku

USE_HEROKU = bool(int(os.getenv("USE_HEROKU", False)))

if USE_HEROKU:
    if "test" in sys.argv:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql_psycopg2",
                "NAME": os.environ["TEST_DB_NAME"],
                "USER": os.environ["TEST_DB_USER"],
                "PASSWORD": os.environ["TEST_DB_PASSWORD"],
                "HOST": os.environ["TEST_DB_HOST"],
                "PORT": os.environ["TEST_DB_PORT"],
                "TEST": {
                    "NAME": os.environ["TEST_DB_NAME"],
                },
            }
        }


# Redis

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = os.environ["REDIS_PORT"]


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
