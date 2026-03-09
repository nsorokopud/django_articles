from typing import Optional

from core.services import EmailConfigDict

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

    email = (n.recipient.email or "").strip()
    if not email:
        return None

    link = None
    if isinstance(n.payload, dict):
        link = n.payload.get("link") or n.payload.get("url")

    return {
        "recipients": [email],
        "subject_template": "emails/notifications/system_subject.txt",
        "text_template": "emails/notifications/system.txt",
        "html_template": "emails/notifications/system.html",
        "context": {
            "title": n.title,
            "body": n.body,
            "link": link,
            "notification_id": n.id,
        },
        "fail_silently": False,
    }
