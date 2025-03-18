from django.db import models

from users.models import User


class Notification(models.Model):
    class Type(models.TextChoices):
        NEW_ARTICLE = "new article"
        NEW_COMMENT = "new comment"

    class Status(models.TextChoices):
        UNREAD = "unread"
        READ = "read"

    type = models.CharField(max_length=255, choices=Type)
    title = models.CharField(max_length=255, null=True, blank=True)
    message = models.CharField(max_length=500, null=True, blank=True)
    link = models.URLField(max_length=500, null=True, blank=True)
    sender = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name="sent_notifications",
        on_delete=models.SET_NULL,
    )
    recipient = models.ForeignKey(
        User,
        blank=True,
        related_name="received_notifications",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=255, null=True, blank=True, choices=Status, default=Status.UNREAD
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        created_at = self.created_at.strftime("%H:%M:%S %d-%m-%Y")
        sender = self.sender.username
        recipient = self.recipient.username
        return f"{created_at} [{self.type}] from {sender} to {recipient}: {self.link}"
