import logging
from typing import ClassVar, Optional

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import IntegrityError, connection, transaction

from ..models import TokenCounter, TokenType
from ..selectors import get_pending_email_address


logger = logging.getLogger(__name__)


class BaseTokenGenerator(PasswordResetTokenGenerator):
    """Base class for token generators that invalidates previous tokens
    by tracking a per-user/token-type counter. Each time a new token is
    generated, the counter is incremented, which invalidates all
    previously issued tokens of the same type for that user.

    Tokens also get invalidated if other conditions defined in
    PasswordResetTokenGenerator apply (e.g. timestamp expiration,
    user state changes).
    """

    token_type: ClassVar[Optional[str]] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.token_type is None:
            raise ValueError(
                "Subclasses of `BaseTokenGenerator` must define `token_type`."
            )
        if not isinstance(cls.token_type, TokenType):
            raise ValueError("Token type must be a `TokenType` instance.")

    @transaction.atomic
    def make_token(self, user: AbstractBaseUser) -> str:
        self._increment_token_counter(user)
        return super().make_token(user)

    def get_token_count(self, user: AbstractBaseUser) -> int:
        try:
            return TokenCounter.objects.get(
                user=user, token_type=self.token_type
            ).token_count
        except TokenCounter.DoesNotExist:
            return 0

    def _make_hash_value(self, user: AbstractBaseUser, timestamp: int) -> str:
        token_count = self.get_token_count(user)
        return (
            super()._make_hash_value(user, timestamp)
            + f"{self.token_type}{token_count}"
        )

    def _increment_token_counter(self, user: AbstractBaseUser) -> int:
        if not connection.in_atomic_block:
            raise transaction.TransactionManagementError(
                "This method must be called inside an atomic transaction."
            )

        try:
            counter = TokenCounter.objects.select_for_update().get(
                user=user, token_type=self.token_type
            )
        except TokenCounter.DoesNotExist:
            try:
                counter = TokenCounter.objects.create(
                    user=user, token_type=self.token_type, token_count=1
                )
                return counter.token_count
            except IntegrityError:
                logger.warning(
                    "Race condition while creating TokenCounter(user_id=%s, "
                    "token_type=%s). Falling back to select_for_update().get()",
                    user.pk,
                    self.token_type,
                )
                counter = TokenCounter.objects.select_for_update().get(
                    user=user, token_type=self.token_type
                )

        counter.token_count += 1
        counter.save(update_fields=["token_count"])
        return counter.token_count


class AccountActivationTokenGenerator(BaseTokenGenerator):
    token_type: ClassVar[str] = TokenType.ACCOUNT_ACTIVATION

    def _make_hash_value(self, user: AbstractBaseUser, timestamp: int) -> str:
        base_hash = super()._make_hash_value(user, timestamp)
        return base_hash + str(user.is_active)


class EmailChangeTokenGenerator(BaseTokenGenerator):
    """Token generator for confirming email address changes. Token
    becomes invalid if the pending email changes, or if other conditions
    defined in the base token generator apply (e.g. timestamp
    expiration, user state changes).
    """

    token_type: ClassVar[str] = TokenType.EMAIL_CHANGE

    def _make_hash_value(self, user: AbstractBaseUser, timestamp: int) -> str:
        email = get_pending_email_address(user)
        email_value = getattr(email, "email", "__no_email__")
        base_hash = super()._make_hash_value(user, timestamp)
        return f"{base_hash}{email_value}"


class CustomPasswordResetTokenGenerator(BaseTokenGenerator):
    """Token generator for resetting passwords. Token becomes invalid if
    conditions defined in the base token generator apply (e.g. timestamp
    expiration, user state changes).
    """

    token_type: ClassVar[str] = TokenType.PASSWORD_CHANGE


activation_token_generator = AccountActivationTokenGenerator()
email_change_token_generator = EmailChangeTokenGenerator()
password_reset_token_generator = CustomPasswordResetTokenGenerator()
