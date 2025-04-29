import logging
from typing import ClassVar, Optional

import six
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import IntegrityError, connection, transaction

from ..models import TokenCounter, TokenType


logger = logging.getLogger("default_logger")


class BaseTokenGenerator(PasswordResetTokenGenerator):
    token_type: ClassVar[Optional[TokenType]] = None

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


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: AbstractBaseUser, timestamp: int) -> str:
        return (
            six.text_type(user.pk)
            + six.text_type(timestamp)
            + six.text_type(user.is_active)
        )


activation_token_generator = AccountActivationTokenGenerator()
