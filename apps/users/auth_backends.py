from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import AbstractUser
from django.http.request import HttpRequest


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

        identifier = username.strip()
        if not identifier:
            return None

        try:
            if "@" in identifier:
                user = UserModel.objects.get(email__iexact=identifier)
            else:
                user = UserModel.objects.get(username__iexact=identifier)
        except UserModel.DoesNotExist:
            return None
        except UserModel.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
