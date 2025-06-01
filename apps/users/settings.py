import os


SUBSCRIBERS_COUNT_CACHE_TIMEOUT = int(
    os.getenv("SUBSCRIBERS_COUNT_CACHE_TIMEOUT", "300")  # 5 minutes
)

ACTIVATION_EMAIL_SUBJECT = "User account activation at Django Articles"
ACTIVATION_EMAIL_TEXT_TEMPLATE = "users/emails/activation_email.txt"
ACTIVATION_EMAIL_HTML_TEMPLATE = "users/emails/activation_email.html"

EMAIL_CHANGE_SUBJECT = "Confirm email change at Django Articles"
EMAIL_CHANGE_TEXT_TEMPLATE = "users/emails/email_change.txt"
EMAIL_CHANGE_HTML_TEMPLATE = "users/emails/email_change.html"
