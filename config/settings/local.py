from .base import *  # noqa: F401,F403 pylint: disable=W0401,W0614
from .env import env


DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])

DOMAIN_NAME = env("DOMAIN_NAME", default="localhost")

INTERNAL_IPS = env.list("INTERNAL_IPS", default=["127.0.0.1"])

if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

HCAPTCHA_SITEKEY = env(
    "HCAPTCHA_SITEKEY", default="10000000-ffff-ffff-ffff-000000000001"
)
HCAPTCHA_SECRET = env(
    "HCAPTCHA_SECRET", default="0x0000000000000000000000000000000000000000"
)
