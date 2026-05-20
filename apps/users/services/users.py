import logging

from botocore.exceptions import BotoCoreError, ClientError
from django.core.cache import cache
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from users.models import (
    DEFAULT_PROFILE_IMAGE,
    PENDING_EMAIL_CHANGE_UNIQUE_CONSTRAINT_NAME,
    USER_EMAIL_UNIQUE_CONSTRAINT_NAME,
    USER_USERNAME_UNIQUE_CONSTRAINT_NAME,
    AuthorSubscription,
    PendingEmailChange,
    Profile,
    User,
)

from ..cache import get_subscribers_count_cache_key
from ..validators import validate_username_is_not_email
from .email_addresses import delete_expired_pending_email_changes_for_email


logger = logging.getLogger(__name__)


def register_user(*, username: str, email: str, password: str) -> User:
    username = (username or "").strip()
    email = (email or "").strip().lower()

    if not username:
        raise ValidationError({"username": "Username is required."})

    validate_username_is_not_email(username)

    if not email:
        raise ValidationError({"email": "Email is required."})

    validate_email(email)

    try:
        with transaction.atomic():
            delete_expired_pending_email_changes_for_email(email=email)

            _validate_registration_availability(username=username, email=email)

            return User.objects.create_user(
                username=username, email=email, password=password, is_active=False
            )

    except IntegrityError as e:
        constraint_name = _get_constraint_name(e)

        if constraint_name == USER_EMAIL_UNIQUE_CONSTRAINT_NAME:
            raise ValidationError(
                {"email": "A user with that email already exists."}
            ) from e

        if constraint_name == USER_USERNAME_UNIQUE_CONSTRAINT_NAME:
            raise ValidationError(
                {"username": "A user with that username already exists."}
            ) from e

        if constraint_name == PENDING_EMAIL_CHANGE_UNIQUE_CONSTRAINT_NAME:
            raise ValidationError(
                {"email": "That email address is currently pending confirmation."}
            ) from e

        try:
            _validate_registration_availability(username=username, email=email)
        except ValidationError as validation_error:
            raise validation_error from e

        raise


@transaction.atomic
def activate_user(user: User) -> None:
    user = User.objects.select_for_update().get(pk=user.pk)

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
        logger.info("User %s was activated.", user.id)
    else:
        logger.info("User %s was already active.", user.id)


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

    username = (username or "").strip()

    if not username:
        raise ValidationError({"username": "Username is required."})

    validate_username_is_not_email(username)

    if user.username.strip() != username:
        if User.objects.exclude(pk=user.pk).filter(username__iexact=username).exists():
            raise ValidationError(
                {"username": "A user with that username already exists."}
            )

        try:
            user.username = username
            user.save(update_fields=["username"])
        except IntegrityError as e:
            if _get_constraint_name(e) == USER_USERNAME_UNIQUE_CONSTRAINT_NAME:
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


@transaction.atomic
def set_author_subscription(
    *, subscriber: User, author: User, should_subscribe: bool
) -> tuple[bool, bool]:
    """Sets the desired subscription state.

    Returns:
        (is_subscribed, changed)

        is_subscribed:
            Final state after the operation.

        changed:
            True if the DB row was created or deleted.
            False if the requested state already existed.
    """
    _validate_subscription_action(subscriber=subscriber, author=author)

    if should_subscribe:
        changed = _subscribe_to_author(subscriber=subscriber, author=author)
        return True, changed

    changed = _unsubscribe_from_author(subscriber=subscriber, author=author)
    return False, changed


def advance_latest_article_publish_sequence(
    *, user_id: int, publish_sequence: int
) -> None:
    User.objects.filter(
        id=user_id,
        latest_article_publish_sequence__lt=publish_sequence,
    ).update(latest_article_publish_sequence=publish_sequence)


def _validate_registration_availability(*, username: str, email: str) -> None:
    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError({"username": "A user with that username already exists."})

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "A user with that email already exists."})

    if PendingEmailChange.objects.filter(email__iexact=email).exists():
        raise ValidationError(
            {"email": "That email address is currently pending confirmation."}
        )


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


def _validate_subscription_action(*, subscriber: User, author: User) -> None:
    if not subscriber.is_authenticated:
        raise ValidationError("Anonymous users cannot subscribe to authors.")

    if not subscriber.is_active:
        raise ValidationError("Inactive users cannot subscribe to authors.")

    if subscriber.pk == author.pk:
        raise ValidationError("Users cannot subscribe to themselves.")

    if not author.is_active:
        raise ValidationError("Cannot subscribe to inactive authors.")


def _subscribe_to_author(*, subscriber: User, author: User) -> bool:
    _, created = AuthorSubscription.objects.get_or_create(
        subscriber=subscriber, author=author
    )

    if created:
        logger.info("User %s subscribed to author %s", subscriber.id, author.id)
        _invalidate_subscribers_count_cache_after_commit(author_id=author.id)
    else:
        logger.info(
            "User %s was already subscribed to author %s", subscriber.id, author.id
        )

    return created


def _unsubscribe_from_author(*, subscriber: User, author: User) -> bool:
    deleted_count, _ = AuthorSubscription.objects.filter(
        subscriber=subscriber, author=author
    ).delete()

    changed = deleted_count > 0

    if changed:
        logger.info("User %s unsubscribed from author %s", subscriber.id, author.id)
        _invalidate_subscribers_count_cache_after_commit(author_id=author.id)
    else:
        logger.info("User %s was not subscribed to author %s", subscriber.id, author.id)

    return changed


def _invalidate_subscribers_count_cache_after_commit(*, author_id: int) -> None:
    transaction.on_commit(
        lambda: cache.delete(get_subscribers_count_cache_key(author_id))
    )


def _get_constraint_name(exc: IntegrityError) -> str | None:
    diagnostics = getattr(exc.__cause__, "diag", None)
    return getattr(diagnostics, "constraint_name", None)
