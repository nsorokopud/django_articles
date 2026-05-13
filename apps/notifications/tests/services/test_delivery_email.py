from django.test import TestCase

from notifications.models import Notification, NotificationType
from notifications.services.delivery_email import build_notification_email_config
from users.models import Profile, User


class TestBuildNotificationEmailConfig(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="u1",
            email="u1@test.com",
        )
        Profile.objects.update_or_create(
            user=self.user,
            defaults={"notification_emails_allowed": True},
        )

    def _create_notification(
        self,
        *,
        notification_type: str = NotificationType.SYSTEM,
        title: str = "T",
        body: str = "B",
        payload=None,
    ) -> Notification:
        if payload is None:
            payload = {}
        return Notification.objects.create(
            recipient=self.user,
            notification_type=notification_type,
            title=title,
            body=body,
            payload=payload,
        )

    def test_returns_none_when_notification_missing(self) -> None:
        cfg = build_notification_email_config(notification_id=99999)
        self.assertIsNone(cfg)

    def test_returns_none_for_non_system_notification(self) -> None:
        n = self._create_notification(notification_type=NotificationType.NEW_COMMENT)
        cfg = build_notification_email_config(notification_id=n.id)
        self.assertIsNone(cfg)

    def test_returns_none_when_user_disables_notification_emails(self) -> None:
        self.user.profile.notification_emails_allowed = False
        self.user.profile.save(update_fields=["notification_emails_allowed"])

        n = self._create_notification(notification_type=NotificationType.SYSTEM)
        cfg = build_notification_email_config(notification_id=n.id)
        self.assertIsNone(cfg)

    def test_builds_config_for_system_notification(self) -> None:
        n = self._create_notification(
            notification_type=NotificationType.SYSTEM,
            title="T",
            body="B",
            payload={"link": "/x/"},
        )

        cfg = build_notification_email_config(notification_id=n.id)
        self.assertIsNotNone(cfg)
        assert cfg is not None
        self.assertEqual(cfg["recipients"], ["u1@test.com"])
        self.assertEqual(cfg["subject"], "T")
        self.assertEqual(cfg["text_content"], "B")

    def test_email_is_stripped_before_returning_config(self) -> None:
        self.user.email = "  u1@test.com  "
        self.user.save(update_fields=["email"])

        n = self._create_notification(notification_type=NotificationType.SYSTEM)
        cfg = build_notification_email_config(notification_id=n.id)

        self.assertIsNotNone(cfg)
        assert cfg is not None
        self.assertEqual(cfg["recipients"], ["u1@test.com"])
