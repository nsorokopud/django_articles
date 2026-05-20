from typing import Optional

from core.services import EmailConfigDict
from users.normalization import normalize_email

from ..models import Notification, NotificationType


def build_notification_email_config(notification_id: int) -> Optional[EmailConfigDict]:
    try:
        n = (
            Notification.objects.select_related("recipient", "recipient__profile")
            .only(
                "id",
                "notification_type",
                "title",
                "body",
                "payload",
                "recipient_id",
                "recipient__email",
                "recipient__profile__notification_emails_allowed",
            )
            .get(id=notification_id)
        )
    except Notification.DoesNotExist:
        return None

    # Email policy: currently only SYSTEM notifications are emailed.
    # This mirrors the dispatch policy but is duplicated here as a safety check.
    if n.notification_type != NotificationType.SYSTEM:
        return None

    if not n.recipient.profile.notification_emails_allowed:
        return None

    email = normalize_email(n.recipient.email)
    if not email:
        return None

    return {
        "subject": n.title,
        "text_content": n.body,
        "recipients": [email],
    }
