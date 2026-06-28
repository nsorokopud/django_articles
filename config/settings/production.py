# flake8: noqa
# mypy: disable-error-code="index,assignment"

from .base import *  # pylint: disable=W0401,W0614
from .components.cache import redis_url
from .env import env


DEBUG = False

SECRET_KEY = env("SECRET_KEY")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

DOMAIN_NAME = env("DOMAIN_NAME")

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


INSTALLED_APPS += ["cachalot"]


DATABASES["default"].update(
    {
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env.int("DB_PORT", default=5432),
        "CONN_MAX_AGE": env.int("DB_CONNECTION_MAX_AGE", default=60),
    }
)

REDIS_HOST = env("REDIS_HOST")
REDIS_PORT = env.int("REDIS_PORT", default=6379)

REDIS_CACHE_URL = env(
    "REDIS_CACHE_URL", default=redis_url(host=REDIS_HOST, port=REDIS_PORT, db=0)
)
REDIS_SELECT2_URL = env(
    "REDIS_SELECT2_URL", default=redis_url(host=REDIS_HOST, port=REDIS_PORT, db=1)
)
REDIS_CHANNELS_URL = env(
    "REDIS_CHANNELS_URL", default=redis_url(host=REDIS_HOST, port=REDIS_PORT, db=2)
)
REDIS_CELERY_BROKER_URL = env(
    "REDIS_CELERY_BROKER_URL", default=redis_url(host=REDIS_HOST, port=REDIS_PORT, db=3)
)
REDIS_CELERY_RESULT_URL = env(
    "REDIS_CELERY_RESULT_URL", default=redis_url(host=REDIS_HOST, port=REDIS_PORT, db=4)
)

CACHES["default"]["LOCATION"] = REDIS_CACHE_URL
CACHES["select2"]["LOCATION"] = REDIS_SELECT2_URL

CHANNEL_LAYERS["default"]["CONFIG"]["hosts"] = [REDIS_CHANNELS_URL]

CELERY_BROKER_URL = REDIS_CELERY_BROKER_URL
CELERY_RESULT_BACKEND = REDIS_CELERY_RESULT_URL

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
AWS_S3_FILE_OVERWRITE = False

SOCIALACCOUNT_PROVIDERS["google"]["APP"] = {
    "client_id": env("GOOGLE_OAUTH_CLIENT_ID"),
    "secret": env("GOOGLE_OAUTH_CLIENT_SECRET"),
}

EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")

HCAPTCHA_SITEKEY = env("HCAPTCHA_SITEKEY")
HCAPTCHA_SECRET = env("HCAPTCHA_SECRET")
