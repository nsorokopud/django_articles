from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db.models import F

from ..models import User
from ..normalization import normalize_email
from ..selectors import get_pending_email_change


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: AbstractBaseUser, timestamp: int) -> str:
        return super()._make_hash_value(user, timestamp) + str(user.is_active)


class EmailChangeTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: AbstractBaseUser, timestamp: int) -> str:
        pending_email_change = get_pending_email_change(user)
        base_hash = super()._make_hash_value(user, timestamp)

        if pending_email_change is None:
            return f"{base_hash}__no_pending_email_change__"

        return (
            f"{base_hash}"
            f"{pending_email_change.pk}"
            f"{normalize_email(pending_email_change.email)}"
        )


class CustomPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: AbstractBaseUser, timestamp: int) -> str:
        return super()._make_hash_value(user, timestamp) + str(
            user.password_reset_token_version
        )


def advance_password_reset_token_version(user_id: int) -> User:
    User.objects.filter(pk=user_id).update(
        password_reset_token_version=F("password_reset_token_version") + 1
    )

    return User.objects.only(
        "id",
        "password",
        "last_login",
        "is_active",
        "email",
        "password_reset_token_version",
    ).get(pk=user_id)


activation_token_generator = AccountActivationTokenGenerator()
email_change_token_generator = EmailChangeTokenGenerator()
password_reset_token_generator = CustomPasswordResetTokenGenerator()
