import os

from .base import *


SECRET_KEY = "test_secret_key"
ALLOWED_HOSTS = ["*"]

SECURE_SSL_REDIRECT = False

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "select2": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

SOCIALACCOUNT_PROVIDERS["google"]["APP"] = {
    "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
    "secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
}

# These are the default values suggested by hCaptcha for testing:
# https://docs.hcaptcha.com/#integration-testing-test-keys.
HCAPTCHA_SITEKEY = os.getenv("HCAPTCHA_SITEKEY", "10000000-ffff-ffff-ffff-000000000001")
HCAPTCHA_SECRET = os.getenv(
    "HCAPTCHA_SECRET", "0x0000000000000000000000000000000000000000"
)

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
