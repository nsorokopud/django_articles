from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(
        default="users/profile_images/default_avatar.jpg",
        upload_to="users/profile_images/",
    )
    subscribers = models.ManyToManyField(User, related_name="subscribed_profiles")
    notification_emails_allowed = models.BooleanField(default=True)

    def __str__(self):
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
            models.Index(fields=["subscriber"]),
            models.Index(fields=["author"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(subscriber=models.F("author")),
                name="prevent_self_subscription",
            ),
            models.UniqueConstraint(
                fields=["subscriber", "author"], name="unique_subscription"
            ),
        ]

    def __str__(self):
        return f"{self.subscriber} -> {self.author}"


class TokenType(models.TextChoices):
    ACCOUNT_ACTIVATION = "account activation"
    EMAIL_CHANGE = "email change"
    PASSWORD_CHANGE = "password change"  # nosec


class TokenCounter(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    token_type = models.CharField(max_length=32, choices=TokenType.choices)
    token_count = models.IntegerField(default=0)

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
