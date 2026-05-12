from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    subscribed_to_authors = models.ManyToManyField(
        "self",
        through="AuthorSubscription",
        symmetrical=False,
        related_name="subscribers",
    )
    latest_article_publish_sequence = models.BigIntegerField(default=0, db_index=True)
    subscriptions_last_seen_publish_sequence = models.BigIntegerField(
        default=0,
        db_index=True,
    )
    unread_notifications_count = models.IntegerField(default=0)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(
        default="users/profile_images/default_avatar.jpg",
        upload_to="users/profile_images/",
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
