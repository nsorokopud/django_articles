from .base import *
from .env import env


SECRET_KEY = "test_secret_key"
ALLOWED_HOSTS = ["*"]

SECURE_SSL_REDIRECT = False

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "select2": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

TEST_REDIS_URL = env("TEST_REDIS_URL", default="redis://localhost:6379/15")

TEST_REDIS_CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": TEST_REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "test",
    },
}

RATELIMIT_ENABLE = False

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

SOCIALACCOUNT_PROVIDERS["google"]["APP"] = {
    "client_id": env("GOOGLE_OAUTH_CLIENT_ID", default=""),
    "secret": env("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
}

# These are the default values suggested by hCaptcha for testing:
# https://docs.hcaptcha.com/#integration-testing-test-keys.
HCAPTCHA_SITEKEY = env(
    "HCAPTCHA_SITEKEY", default="10000000-ffff-ffff-ffff-000000000001"
)
HCAPTCHA_SECRET = env(
    "HCAPTCHA_SECRET", default="0x0000000000000000000000000000000000000000"
)

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
