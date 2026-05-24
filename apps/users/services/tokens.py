from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.tokens import PasswordResetTokenGenerator

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


activation_token_generator = AccountActivationTokenGenerator()
email_change_token_generator = EmailChangeTokenGenerator()
