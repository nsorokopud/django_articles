import os
import posixpath
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower, Trim
from django.utils.crypto import salted_hmac
from django.utils.text import get_valid_filename

from .normalization import normalize_email, normalize_username
from .validators import validate_username_is_not_email


USER_EMAIL_UNIQUE_CONSTRAINT_NAME = "users_user_email_ci_unique"
USER_USERNAME_UNIQUE_CONSTRAINT_NAME = "users_user_username_ci_unique"

DEFAULT_PROFILE_IMAGE = "users/profile_images/default_avatar.jpg"
PROFILE_IMAGE_UPLOAD_PREFIX = "users/profile_images"
PROFILE_IMAGE_MAX_LENGTH = 512
PROFILE_IMAGE_EXTENSION_MAX_LENGTH = 16
PROFILE_IMAGE_UUID_LENGTH = 32

PENDING_EMAIL_CHANGE_UNIQUE_CONSTRAINT_NAME = (
    "users_pending_email_change_email_ci_unique"
)


class User(AbstractUser):
    email = models.EmailField()
    subscribed_to_authors = models.ManyToManyField(
        "self",
        through="AuthorSubscription",
        symmetrical=False,
        related_name="subscribers",
    )
    unread_notifications_count = models.PositiveIntegerField(default=0)
    session_auth_version = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(email=""), name="users_user_email_not_blank"
            ),
            models.UniqueConstraint(
                Lower(Trim("email")), name=USER_EMAIL_UNIQUE_CONSTRAINT_NAME
            ),
            models.UniqueConstraint(
                Lower(Trim("username")), name=USER_USERNAME_UNIQUE_CONSTRAINT_NAME
            ),
            models.CheckConstraint(
                condition=~models.Q(username__contains="@"),
                name="users_username_not_email_like",
            ),
        ]

    def clean(self):
        super().clean()

        self.username = normalize_username(self.username)
        validate_username_is_not_email(self.username)
        self.email = normalize_email(self.email)

    def save(self, *args, **kwargs):
        self.username = normalize_username(self.username)
        validate_username_is_not_email(self.username)
        self.email = normalize_email(self.email)

        super().save(*args, **kwargs)

    def get_session_auth_hash(self):
        key_salt = "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash"
        return salted_hmac(
            key_salt,
            f"{self.password}:{self.session_auth_version}",
            secret=None,
            algorithm="sha256",
        ).hexdigest()


class PendingEmailChange(models.Model):
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="pending_email_change"
    )
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(email=""),
                name="users_pending_email_change_email_not_blank",
            ),
            models.UniqueConstraint(
                Lower(Trim("email")),
                name=PENDING_EMAIL_CHANGE_UNIQUE_CONSTRAINT_NAME,
            ),
        ]

    def clean(self):
        super().clean()
        self.email = normalize_email(self.email)

    def save(self, *args, **kwargs):
        self.email = normalize_email(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


def profile_image_upload_path(instance, filename) -> str:
    if not instance.user_id:
        raise ValueError("user_id is required to upload profile images")

    directory = posixpath.join(PROFILE_IMAGE_UPLOAD_PREFIX, str(instance.user_id))
    return posixpath.join(directory, _build_uuid_profile_image_filename(filename))


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(
        default=DEFAULT_PROFILE_IMAGE,
        upload_to=profile_image_upload_path,
        max_length=PROFILE_IMAGE_MAX_LENGTH,
    )
    notification_emails_allowed = models.BooleanField(default=True, db_index=True)

    def __str__(self) -> str:
        return f"{self.user.username}'s profile"


class AuthorSubscription(models.Model):
    subscriber = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscriptions_made"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscriptions_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(subscriber=models.F("author")),
                name="sub_prevent_self_subscription",
            ),
            models.UniqueConstraint(
                fields=["subscriber", "author"],
                name="sub_subscriber_author_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.subscriber_id} -> {self.author_id}"


def _build_uuid_profile_image_filename(filename: str) -> str:
    _, extension = os.path.splitext(os.path.basename(filename))
    safe_extension = (
        get_valid_filename(extension.lower()).strip("._")[
            :PROFILE_IMAGE_EXTENSION_MAX_LENGTH
        ]
        if extension
        else ""
    )

    generated_filename = uuid4().hex
    if safe_extension:
        return f"{generated_filename}.{safe_extension}"

    return generated_filename
