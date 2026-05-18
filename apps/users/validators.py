from django.core.exceptions import ValidationError


def validate_username_is_not_email(value: str) -> None:
    value = (value or "").strip()

    if "@" in value:
        raise ValidationError("Username cannot be an email address.")
