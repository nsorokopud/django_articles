from unittest.mock import patch

from django.db import IntegrityError
from django.template import TemplateDoesNotExist
from django.test import TestCase
from django.urls import NoReverseMatch

from notifications.models import Notification, NotificationType
from notifications.services.creation import (
    create_new_comment_notification,
    create_notification,
    create_system_notification,
)
from users.models import User


class TestCreateNotification(TestCase):
    def setUp(self) -> None:
        self.recipient = User.objects.create_user(
            username="recipient",
            email="recipient@test.com",
        )
        self.sender = User.objects.create_user(
            username="sender",
            email="sender@test.com",
        )

    def test_creates_row_and_increments_unread(self) -> None:
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 0)

        n, created = create_notification(
            recipient_id=self.recipient.id,
            sender_id=self.sender.id,
            notification_type=NotificationType.SYSTEM,
            title="T",
            body="B",
            payload={"link": "/x/"},
            dedupe_key="k1",
        )

        self.assertTrue(created)
        self.assertIsInstance(n, Notification)
        self.assertTrue(Notification.objects.filter(id=n.id).exists())
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 1)

        n_db = Notification.objects.get(id=n.id)
        self.assertEqual(n_db.recipient_id, self.recipient.id)
        self.assertEqual(n_db.sender_id, self.sender.id)
        self.assertEqual(n_db.title, "T")
        self.assertEqual(n_db.body, "B")
        self.assertEqual(n_db.payload, {"link": "/x/"})
        self.assertEqual(n_db.dedupe_key, "k1")

    def test_payload_none_normalizes_to_empty_dict(self) -> None:
        n, created = create_notification(
            recipient_id=self.recipient.id,
            notification_type=NotificationType.SYSTEM,
            title="T",
            body="B",
            payload=None,
            dedupe_key="k_payload_none",
        )
        self.assertTrue(created)
        self.assertEqual(Notification.objects.get(id=n.id).payload, {})

    @patch("notifications.services.creation.logger.warning")
    def test_payload_non_dict_logs_warning_and_becomes_empty_dict(
        self, mock_logger_warning
    ) -> None:
        n, created = create_notification(
            recipient_id=self.recipient.id,
            notification_type=NotificationType.SYSTEM,
            title="T",
            body="B",
            payload=["not-a-dict"],
            dedupe_key="k_payload_bad",
        )
        self.assertTrue(created)
        mock_logger_warning.assert_called_once()
        self.assertEqual(Notification.objects.get(id=n.id).payload, {})

    def test_dedupe_collision_returns_existing_and_does_not_increment_unread(
        self,
    ) -> None:
        n1, created1 = create_notification(
            recipient_id=self.recipient.id,
            notification_type=NotificationType.SYSTEM,
            title="T1",
            body="B1",
            payload={"x": 1},
            dedupe_key="dedupe:1",
        )
        self.assertTrue(created1)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 1)

        n2, created2 = create_notification(
            recipient_id=self.recipient.id,
            notification_type=NotificationType.SYSTEM,
            title="T2-ignored",
            body="B2-ignored",
            payload={"x": 2},
            dedupe_key="dedupe:1",
        )
        self.assertFalse(created2)
        self.assertEqual(n2.id, n1.id)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 1)

        n_db = Notification.objects.get(id=n1.id)
        self.assertEqual(n_db.title, "T1")
        self.assertEqual(n_db.body, "B1")
        self.assertEqual(n_db.payload, {"x": 1})

    @patch(
        "notifications.services.creation.Notification.objects.create",
        side_effect=IntegrityError("error"),
    )
    def test_non_dedupe_integrity_error_reraised_when_no_dedupe_key(
        self, create_mock
    ) -> None:
        with self.assertRaises(IntegrityError):
            create_notification(
                recipient_id=self.recipient.id,
                notification_type=NotificationType.SYSTEM,
                title="T",
                body="B",
                payload={},
                dedupe_key="",
            )

    @patch(
        "notifications.services.creation.Notification.objects.create",
        side_effect=IntegrityError("error"),
    )
    @patch(
        "notifications.services.creation._is_dedupe_violation",
        return_value=False,
    )
    def test_integrity_error_other_constraint_is_reraised(
        self, mock_is_dedupe_violation, mock_create
    ) -> None:
        with self.assertRaises(IntegrityError):
            create_notification(
                recipient_id=self.recipient.id,
                notification_type=NotificationType.SYSTEM,
                title="T",
                body="B",
                payload={},
                dedupe_key="nonempty",
            )

    def test_strips_dedupe_key(self) -> None:
        n1, created1 = create_notification(
            recipient_id=self.recipient.id,
            notification_type=NotificationType.SYSTEM,
            title="T1",
            body="B1",
            payload={},
            dedupe_key="  key  ",
        )
        self.assertTrue(created1)

        n2, created2 = create_notification(
            recipient_id=self.recipient.id,
            notification_type=NotificationType.SYSTEM,
            title="T2",
            body="B2",
            payload={},
            dedupe_key="key",
        )
        self.assertFalse(created2)
        self.assertEqual(n2.id, n1.id)

    def test_empty_dedupe_key_allows_duplicates(self) -> None:
        n1, created1 = create_notification(
            recipient_id=self.recipient.id,
            notification_type=NotificationType.SYSTEM,
            title="T1",
            body="B1",
            payload={},
            dedupe_key="",
        )
        n2, created2 = create_notification(
            recipient_id=self.recipient.id,
            notification_type=NotificationType.SYSTEM,
            title="T2",
            body="B2",
            payload={},
            dedupe_key="",
        )
        self.assertTrue(created1)
        self.assertTrue(created2)
        self.assertNotEqual(n1.id, n2.id)


class TestCreateNewCommentNotification(TestCase):
    def setUp(self) -> None:
        self.recipient = User.objects.create_user(
            username="recipient",
            email="recipient@test.com",
        )
        self.sender = User.objects.create_user(
            username="sender",
            email="sender@test.com",
        )

    def test_returns_none_on_self_comment(self) -> None:
        res = create_new_comment_notification(
            comment_id=1,
            comment_author_id=self.recipient.id,
            comment_author_username=self.recipient.username,
            article_author_id=self.recipient.id,
            article_slug="slug",
            article_title="Title",
        )
        self.assertIsNone(res)

    @patch(
        "notifications.services.creation.render_to_string",
        side_effect=TemplateDoesNotExist("x"),
    )
    @patch(
        "notifications.services.creation.reverse",
        side_effect=NoReverseMatch("x"),
    )
    def test_template_fallback_and_reverse_fallback(
        self, mock_reverse, mock_render
    ) -> None:
        res = create_new_comment_notification(
            comment_id=1,
            comment_author_id=self.sender.id,
            comment_author_username=self.sender.username,
            article_author_id=self.recipient.id,
            article_slug="a-slug",
            article_title="Some Article",
        )

        self.assertIsNotNone(res)
        n, created = res
        self.assertTrue(created)

        n_db = Notification.objects.get(id=n.id)
        self.assertEqual(n_db.recipient_id, self.recipient.id)
        self.assertEqual(n_db.sender_id, self.sender.id)
        self.assertEqual(n_db.notification_type, NotificationType.NEW_COMMENT)
        self.assertEqual(n_db.title, "New Comment")
        self.assertEqual(n_db.payload.get("link"), "/")  # reverse fallback
        self.assertIn("New comment by", n_db.body)  # template fallback

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 1)

    def test_uses_reverse_link_when_available(
        self,
    ) -> None:
        with patch(
            "notifications.services.creation.reverse", return_value="/articles/a-slug/"
        ):
            res = create_new_comment_notification(
                comment_id=1,
                comment_author_id=self.sender.id,
                comment_author_username=self.sender.username,
                article_author_id=self.recipient.id,
                article_slug="a-slug",
                article_title="Some Article",
            )

        self.assertIsNotNone(res)
        n, created = res
        self.assertTrue(created)
        self.assertEqual(
            Notification.objects.get(id=n.id).payload.get("link"), "/articles/a-slug/"
        )


class TestCreateSystemNotification(TestCase):
    def setUp(self) -> None:
        self.recipient = User.objects.create_user(
            username="recipient",
            email="recipient@test.com",
        )
        self.sender = User.objects.create_user(
            username="sender",
            email="sender@test.com",
        )

    def test_create_system_notification_defaults_type_and_level(self) -> None:
        n, created = create_system_notification(
            recipient_id=self.recipient.id,
            title="T",
            body="B",
        )
        self.assertTrue(created)

        n_db = Notification.objects.get(id=n.id)
        self.assertEqual(n_db.notification_type, NotificationType.SYSTEM)
        self.assertEqual(n_db.level, Notification.Level.INFO)
        self.assertEqual(n_db.title, "T")
        self.assertEqual(n_db.body, "B")

    def test_create_system_notification_allows_custom_level(self) -> None:
        n, created = create_system_notification(
            recipient_id=self.recipient.id,
            level=Notification.Level.ERROR,
            title="T",
            body="B",
        )
        self.assertTrue(created)
        self.assertEqual(
            Notification.objects.get(id=n.id).level, Notification.Level.ERROR
        )

    def test_create_system_notification_forwards_sender_payload_and_dedupe(
        self,
    ) -> None:
        n, created = create_system_notification(
            recipient_id=self.recipient.id,
            sender_id=self.sender.id,
            title="T",
            body="B",
            payload={"link": "/x/"},
            dedupe_key="sys:1",
        )
        self.assertTrue(created)

        n_db = Notification.objects.get(id=n.id)
        self.assertEqual(n_db.sender_id, self.sender.id)
        self.assertEqual(n_db.payload, {"link": "/x/"})
        self.assertEqual(n_db.dedupe_key, "sys:1")

    def test_create_system_notification_dedupe_returns_existing(self) -> None:
        n1, created1 = create_system_notification(
            recipient_id=self.recipient.id,
            title="T1",
            body="B1",
            dedupe_key="sys:dedupe",
        )
        self.assertTrue(created1)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 1)

        n2, created2 = create_system_notification(
            recipient_id=self.recipient.id,
            title="T2",
            body="B2",
            dedupe_key="sys:dedupe",
        )
        self.assertFalse(created2)
        self.assertEqual(n2.id, n1.id)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.unread_notifications_count, 1)

        n_db = Notification.objects.get(id=n1.id)
        self.assertEqual(n_db.title, "T1")
        self.assertEqual(n_db.body, "B1")
