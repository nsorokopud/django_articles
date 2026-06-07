from ..env import env


EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

EMAIL_TASK_MAX_RETRIES = env.int("EMAIL_TASK_MAX_RETRIES", default=3)
EMAIL_TASK_BASE_RETRY_DELAY = env.int("EMAIL_TASK_BASE_RETRY_DELAY", default=60)
EMAIL_TASK_EXPONENTIAL_BACKOFF_FACTOR = env.int(
    "EMAIL_TASK_EXPONENTIAL_BACKOFF_FACTOR", default=2
)
