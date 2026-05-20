from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import AbstractUser
from django.http.request import HttpRequest

from .normalization import normalize_email, normalize_username


class EmailOrUsernameAuthenticationBackend(ModelBackend):
    def authenticate(
        self,
        request: HttpRequest,
        username: str | None = None,
        password: str | None = None,
        **kwargs,
    ) -> Optional[AbstractUser]:
        UserModel = get_user_model()

        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)

        if username is None or password is None:
            return None

        raw_identifier = normalize_username(username)
        if not raw_identifier:
            return None

        try:
            if "@" in raw_identifier:
                identifier = normalize_email(raw_identifier)
                user = UserModel.objects.get(email__iexact=identifier)
            else:
                identifier = normalize_username(raw_identifier)
                user = UserModel.objects.get(username__iexact=identifier)
        except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
            # Dummy password hash to reduce user-enumeration timing differences
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
