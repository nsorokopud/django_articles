import logging

from botocore.exceptions import BotoCoreError, ClientError
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.files.storage import default_storage
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

    old_image_name = profile.image.name if profile.image else ""

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

    new_image_name = profile.image.name if profile.image else ""

    if _should_delete_old_profile_image(
        old_image_name=old_image_name, new_image_name=new_image_name
    ):
        transaction.on_commit(lambda: _delete_profile_image(old_image_name))

    return user, profile


def _should_delete_old_profile_image(
    *, old_image_name: str, new_image_name: str
) -> bool:
    return bool(
        old_image_name
        and old_image_name != DEFAULT_PROFILE_IMAGE
        and old_image_name != new_image_name
    )


def _delete_profile_image(file_name: str) -> None:
    if not file_name or file_name == DEFAULT_PROFILE_IMAGE:
        return

    if Profile.objects.filter(image=file_name).exists():
        logger.info("Skipped deleting profile image still in use: %s", file_name)
        return

    try:
        default_storage.delete(file_name)
    except (OSError, BotoCoreError, ClientError, SuspiciousFileOperation):
        logger.exception("Failed to delete old profile image: %s", file_name)
