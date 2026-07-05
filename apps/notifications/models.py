from django.db import models
from django.utils import timezone

from users.models import User


NOTIFICATION_DEDUPE_CONSTRAINT = "uniq_notif_recipient_dedupe"
UNREAD_COMMENT_NOTIFICATION_AGGREGATE_CONSTRAINT = "uniq_rec_unread_comm_notif_agg"


class NotificationType(models.TextChoices):
    NEW_COMMENT = "new_comment", "New comment"
    SYSTEM = "system", "System"
    OTHER = "other", "Other"


class Notification(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    level = models.CharField(
        max_length=16, choices=Level.choices, blank=True, default=Level.INFO
    )
    notification_type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
        blank=True,
        default=NotificationType.SYSTEM,
    )
    title = models.CharField(max_length=128, blank=True)
    body = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications", db_index=True
    )
    sender = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name="sent_notifications",
        on_delete=models.SET_NULL,
    )
    dedupe_key = models.CharField(max_length=128, blank=True, default="")
    aggregate_key = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_event_at = models.DateTimeField(default=timezone.now, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ("-last_event_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "dedupe_key"],
                condition=~models.Q(dedupe_key=""),
                name=NOTIFICATION_DEDUPE_CONSTRAINT,
            ),
            models.UniqueConstraint(
                fields=["recipient", "aggregate_key"],
                condition=(
                    ~models.Q(aggregate_key="")
                    & models.Q(read_at__isnull=True)
                    & models.Q(notification_type=NotificationType.NEW_COMMENT)
                ),
                name=UNREAD_COMMENT_NOTIFICATION_AGGREGATE_CONSTRAINT,
            ),
        ]
        indexes = [
            models.Index(
                fields=["recipient", "-last_event_at", "-id"],
                name="notif_rec_event_id_desc_idx",
            ),
            models.Index(
                fields=["recipient", "-last_event_at", "-id"],
                name="notif_unread_rec_event_id_idx",
                condition=models.Q(read_at__isnull=True),
            ),
            models.Index(
                fields=["recipient", "aggregate_key", "-id"],
                name="notif_unread_aggr_lookup_idx",
                condition=(
                    ~models.Q(aggregate_key="")
                    & models.Q(read_at__isnull=True)
                    & models.Q(notification_type=NotificationType.NEW_COMMENT)
                ),
            ),
            models.Index(
                fields=["read_at", "id"],
                name="notif_read_cleanup_idx",
                condition=models.Q(read_at__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        created_at = self.created_at.strftime("%H:%M:%S %d-%m-%Y")
        sender = self.sender.pk if self.sender else "-"
        return (
            f"{created_at} [{self.level}, {self.notification_type}]; "
            f"{sender}->{self.recipient.pk}"
        )
