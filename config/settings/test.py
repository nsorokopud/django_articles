from .base import *


SECRET_KEY = "test_secret_key"
DEBUG = False
ALLOWED_HOSTS = ["*"]

SCHEME = "http"
DOMAIN_NAME = "testserver"

SECURE_SSL_REDIRECT = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "select2": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
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
    "client_id": "",
    "secret": "",
}

# These are the default values suggested by hCaptcha for testing:
# https://docs.hcaptcha.com/#integration-testing-test-keys.
HCAPTCHA_SITEKEY = "10000000-ffff-ffff-ffff-000000000001"
HCAPTCHA_SECRET = "0x0000000000000000000000000000000000000000"

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
