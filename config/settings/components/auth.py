from ..env import env


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
            "client_id": env("GOOGLE_OAUTH_CLIENT_ID", default=""),
            "secret": env("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
        },
        "AUTH_PARAMS": {
            "access_type": "online",
            "prompt": "select_account",
        },
        "EMAIL_AUTHENTICATION": True,
        "VERIFIED_EMAIL": True,
    }
}

PASSWORD_RESET_TIMEOUT = 60 * 15

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
