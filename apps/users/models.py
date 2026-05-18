import os
import posixpath
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower, Trim
from django.utils.text import get_valid_filename


DEFAULT_PROFILE_IMAGE = "users/profile_images/default_avatar.jpg"


class User(AbstractUser):
    email = models.EmailField()
    subscribed_to_authors = models.ManyToManyField(
        "self",
        through="AuthorSubscription",
        symmetrical=False,
        related_name="subscribers",
    )
    latest_article_publish_sequence = models.BigIntegerField(default=0, db_index=True)
    subscriptions_last_seen_publish_sequence = models.BigIntegerField(
        default=0, db_index=True
    )
    unread_notifications_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(email=""), name="users_user_email_not_blank"
            ),
            models.UniqueConstraint(
                Lower(Trim("email")), name="users_user_email_ci_unique"
            ),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class PendingEmailChange(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="pending_email_change",
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
                name="users_pending_email_change_email_ci_unique",
            ),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


def profile_image_upload_path(instance, filename) -> str:
    if not instance.user_id:
        raise ValueError("user_id is required to upload profile images")

    raw_base_name = os.path.basename(filename)
    base_name, extension = os.path.splitext(raw_base_name)

    safe_base_name = get_valid_filename(base_name).strip("._-") or "avatar"
    safe_extension = (
        get_valid_filename(extension.lower()).strip("._") if extension else ""
    )

    final_filename = f"{safe_base_name}_{uuid4().hex}"
    if safe_extension:
        final_filename = f"{final_filename}.{safe_extension}"

    return posixpath.join(
        "users", "profile_images", str(instance.user_id), final_filename
    )


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(
        default=DEFAULT_PROFILE_IMAGE, upload_to=profile_image_upload_path
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
    notifications_enabled = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["subscriber", "author"],
                name="sub_notif_enabl_sub_author_idx",
                condition=models.Q(notifications_enabled=True),
            ),
        ]
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


class TokenType(models.TextChoices):
    ACCOUNT_ACTIVATION = "account_activation", "Account activation"
    EMAIL_CHANGE = "email_change", "Email change"
    PASSWORD_CHANGE = "password_change", "Password change"


class TokenCounter(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    token_type = models.CharField(max_length=32, choices=TokenType.choices)
    token_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ["user", "token_type"]
        indexes = [
            models.Index(fields=["user", "token_type"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(token_type__in=TokenType.values),
                name="%(app_label)s_%(class)s_token_type_valid",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.token_type} - {self.token_count}"
