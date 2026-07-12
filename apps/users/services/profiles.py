import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.db import get_constraint_name
from users.models import (
    DEFAULT_PROFILE_IMAGE,
    USER_USERNAME_UNIQUE_CONSTRAINT_NAME,
    Profile,
    User,
)

from ..normalization import normalize_username
from ..validators import validate_username_is_not_email


logger = logging.getLogger(__name__)


@transaction.atomic
def create_user_profile(user: User) -> Profile:
    profile, created = Profile.objects.get_or_create(user=user)
    if created:
        logger.info("Profile for user %s was created", user.id)
    else:
        logger.info("Profile for user %s already exists", user.id)
    return profile


@transaction.atomic
def update_user_profile(
    *,
    user: User,
    username: str,
    image=None,
    image_changed: bool = False,
    notification_emails_allowed: bool,
) -> tuple[User, Profile]:
    user = User.objects.select_for_update().get(pk=user.pk)
    profile = Profile.objects.select_for_update().get(user=user)

    username = normalize_username(username)

    if not username:
        raise ValidationError({"username": "Username is required."})

    validate_username_is_not_email(username)

    if normalize_username(user.username) != username:
        if User.objects.exclude(pk=user.pk).filter(username__iexact=username).exists():
            raise ValidationError(
                {"username": "A user with that username already exists."}
            )

        try:
            user.username = username
            user.save(update_fields=["username"])
        except IntegrityError as e:
            if get_constraint_name(e) == USER_USERNAME_UNIQUE_CONSTRAINT_NAME:
                raise ValidationError(
                    {"username": "A user with that username already exists."}
                ) from e
            raise

    update_fields = []

    if profile.notification_emails_allowed != notification_emails_allowed:
        profile.notification_emails_allowed = notification_emails_allowed
        update_fields.append("notification_emails_allowed")

    if image_changed:
        profile.image = image or DEFAULT_PROFILE_IMAGE
        update_fields.append("image")

    if update_fields:
        profile.save(update_fields=update_fields)

    return user, profile
