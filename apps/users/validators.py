from django.core.exceptions import ValidationError

from .normalization import normalize_username


def validate_username_is_not_email(value: str) -> None:
    value = normalize_username(value)

    if "@" in value:
        raise ValidationError("Username cannot be an email address.")
