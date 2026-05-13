from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import AbstractUser
from django.db.models import Q
from django.http.request import HttpRequest


class EmailOrUsernameAuthenticationBackend(ModelBackend):
    def authenticate(
        self,
        request: HttpRequest,
        username: str | None = None,
        password: str | None = None,
        **kwargs,
    ) -> Optional[AbstractUser]:
        if username is None or password is None:
            return None

        identifier = username.strip()
        if not identifier:
            return None

        UserModel = get_user_model()

        try:
            user = UserModel.objects.get(
                Q(username=identifier) | Q(email__iexact=identifier)
            )
        except UserModel.DoesNotExist:
            return None
        except UserModel.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
