from unittest.mock import patch

from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch
from django.utils import timezone

from core.db import get_constraint_name
from notifications.models import (
    UNREAD_COMMENT_NOTIFICATION_AGGREGATE_CONSTRAINT,
    Notification,
    NotificationType,
)
from notifications.services.comment_aggregation import (
    _build_article_link,
    _build_comment_aggregate_body,
    _build_comment_aggregate_key,
    _build_comment_aggregate_title,
    _normalize_comment_aggregate_payload,
    _safe_int,
    create_or_update_unread_comment_aggregate_notification,
)
from users.models import User


class TestCreateOrUpdateUnreadCommentAggregateNotification(TestCase):
    def setUp(self):
        self.article_author = User.objects.create_user(
            username="author", email="author@example.com", password="testpass123"
        )
        self.commenter1 = User.objects.create_user(
            username="alice", email="alice@example.com", password="testpass123"
        )
        self.commenter2 = User.objects.create_user(
            username="bob", email="bob@example.com", password="testpass123"
        )

        self.article_id = 101
        self.article_slug = "my-article"
        self.article_title = "My Article"

    def test_returns_none_for_self_comment(self):
        result = create_or_update_unread_comment_aggregate_notification(
            comment_id=1,
            comment_author_id=self.article_author.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )

        self.assertIsNone(result)
        self.assertEqual(Notification.objects.count(), 0)

        self.article_author.refresh_from_db()
        self.assertEqual(self.article_author.unread_notifications_count, 0)

    def test_creates_new_unread_comment_aggregate_notification(self):
        notification, created = create_or_update_unread_comment_aggregate_notification(
            comment_id=11,
            comment_author_id=self.commenter1.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )

        self.assertTrue(created)
        self.assertIsNotNone(notification.id)

        notification.refresh_from_db()
        self.assertEqual(notification.recipient_id, self.article_author.id)
        self.assertEqual(notification.notification_type, NotificationType.NEW_COMMENT)
        self.assertEqual(
            notification.aggregate_key,
            f"new_comment_agg:{self.article_author.id}:{self.article_id}",
        )
        self.assertEqual(notification.dedupe_key, "")
        self.assertIsNone(notification.sender_id)
        self.assertIsNone(notification.read_at)
        self.assertEqual(notification.title, "New Comment")
        self.assertEqual(
            notification.body,
            f'New comment on your article "{self.article_title}".',
        )

        payload = notification.payload
        self.assertEqual(payload["kind"], "comment_aggregate")
        self.assertEqual(payload["article_id"], self.article_id)
        self.assertEqual(payload["article_title"], self.article_title)
        self.assertEqual(payload["comment_count"], 1)
        self.assertEqual(payload["last_comment_id"], 11)
        self.assertNotIn("has_other_commenters", payload)
        self.assertNotIn("sample_commenters", payload)
        self.assertNotIn("commenter_ids", payload)
        self.assertNotIn("distinct_commenter_count", payload)
        self.assertIn("last_comment_at", payload)
        self.assertTrue(payload["link"])

        self.article_author.refresh_from_db()
        self.assertEqual(self.article_author.unread_notifications_count, 1)

    def test_updates_existing_unread_aggregate_instead_of_creating_new_row(self):
        first, first_created = create_or_update_unread_comment_aggregate_notification(
            comment_id=11,
            comment_author_id=self.commenter1.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )
        self.assertTrue(first_created)

        second, second_created = create_or_update_unread_comment_aggregate_notification(
            comment_id=12,
            comment_author_id=self.commenter2.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )

        self.assertFalse(second_created)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Notification.objects.count(), 1)

        second.refresh_from_db()
        self.assertEqual(second.title, "New Comments")
        self.assertEqual(
            second.body,
            f'2 new comments on your article "{self.article_title}".',
        )
        self.assertEqual(second.payload["comment_count"], 2)
        self.assertEqual(second.payload["last_comment_id"], 12)
        self.assertNotIn("has_other_commenters", second.payload)
        self.assertNotIn("sample_commenters", second.payload)
        self.assertNotIn("commenter_ids", second.payload)
        self.assertNotIn("distinct_commenter_count", second.payload)

        self.article_author.refresh_from_db()
        self.assertEqual(self.article_author.unread_notifications_count, 1)

    def test_creates_new_row_after_previous_aggregate_was_read(self):
        notification, created = create_or_update_unread_comment_aggregate_notification(
            comment_id=11,
            comment_author_id=self.commenter1.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )
        self.assertTrue(created)

        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])

        self.article_author.unread_notifications_count = 0
        self.article_author.save(update_fields=["unread_notifications_count"])

        next_notification, next_created = (
            create_or_update_unread_comment_aggregate_notification(
                comment_id=12,
                comment_author_id=self.commenter2.id,
                article_id=self.article_id,
                article_author_id=self.article_author.id,
                article_slug=self.article_slug,
                article_title=self.article_title,
            )
        )

        self.assertTrue(next_created)
        self.assertNotEqual(notification.id, next_notification.id)
        self.assertEqual(Notification.objects.count(), 2)

        unread_qs = Notification.objects.filter(
            recipient=self.article_author,
            notification_type=NotificationType.NEW_COMMENT,
            aggregate_key=f"new_comment_agg:{self.article_author.id}:{self.article_id}",
            read_at__isnull=True,
        )
        self.assertEqual(unread_qs.count(), 1)

        self.article_author.refresh_from_db()
        self.assertEqual(self.article_author.unread_notifications_count, 1)

    def test_multiple_comments_update_count_and_generic_body(self):
        notification, _ = create_or_update_unread_comment_aggregate_notification(
            comment_id=11,
            comment_author_id=self.commenter1.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )

        notification, _ = create_or_update_unread_comment_aggregate_notification(
            comment_id=12,
            comment_author_id=self.commenter2.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )

        notification, _ = create_or_update_unread_comment_aggregate_notification(
            comment_id=13,
            comment_author_id=self.commenter2.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )

        notification.refresh_from_db()

        self.assertEqual(notification.payload["comment_count"], 3)
        self.assertNotIn("has_other_commenters", notification.payload)
        self.assertNotIn("sample_commenters", notification.payload)
        self.assertNotIn("commenter_ids", notification.payload)
        self.assertNotIn("distinct_commenter_count", notification.payload)
        self.assertEqual(
            notification.body,
            f'3 new comments on your article "{self.article_title}".',
        )

    def test_recovers_from_malformed_existing_payload_when_updating(self):
        notification = Notification.objects.create(
            recipient=self.article_author,
            sender=None,
            notification_type=NotificationType.NEW_COMMENT,
            level=Notification.Level.INFO,
            title="bad",
            body="bad",
            payload={
                "comment_count": "not-an-int",
                "has_other_commenters": "yes",
                "article_id": "bad",
                "last_comment_id": None,
            },
            aggregate_key=f"new_comment_agg:{self.article_author.id}:{self.article_id}",
            dedupe_key="",
        )
        self.article_author.unread_notifications_count = 1
        self.article_author.save(update_fields=["unread_notifications_count"])

        updated, created = create_or_update_unread_comment_aggregate_notification(
            comment_id=99,
            comment_author_id=self.commenter2.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )

        self.assertFalse(created)
        self.assertEqual(updated.id, notification.id)

        updated.refresh_from_db()
        self.assertEqual(updated.payload["kind"], "comment_aggregate")
        self.assertEqual(updated.payload["article_id"], self.article_id)
        self.assertEqual(updated.payload["article_title"], self.article_title)
        self.assertEqual(updated.payload["comment_count"], 1)
        self.assertEqual(updated.payload["last_comment_id"], 99)
        self.assertNotIn("has_other_commenters", updated.payload)
        self.assertNotIn("sample_commenters", updated.payload)
        self.assertNotIn("commenter_ids", updated.payload)
        self.assertNotIn("distinct_commenter_count", updated.payload)

        self.article_author.refresh_from_db()
        self.assertEqual(self.article_author.unread_notifications_count, 1)

    def test_unread_aggregate_unique_constraint_allows_only_one_unread_per_article(
        self,
    ):
        aggregate_key = f"new_comment_agg:{self.article_author.id}:{self.article_id}"

        Notification.objects.create(
            recipient=self.article_author,
            sender=None,
            notification_type=NotificationType.NEW_COMMENT,
            level=Notification.Level.INFO,
            title="N1",
            body="B1",
            payload={},
            aggregate_key=aggregate_key,
            dedupe_key="",
        )

        with self.assertRaises(IntegrityError) as exc_ctx:
            Notification.objects.create(
                recipient=self.article_author,
                sender=None,
                notification_type=NotificationType.NEW_COMMENT,
                level=Notification.Level.INFO,
                title="N2",
                body="B2",
                payload={},
                aggregate_key=aggregate_key,
                dedupe_key="",
            )

        self.assertEqual(
            get_constraint_name(exc_ctx.exception),
            UNREAD_COMMENT_NOTIFICATION_AGGREGATE_CONSTRAINT,
        )

    def test_read_row_does_not_block_new_unread_row(self):
        aggregate_key = f"new_comment_agg:{self.article_author.id}:{self.article_id}"

        Notification.objects.create(
            recipient=self.article_author,
            sender=None,
            notification_type=NotificationType.NEW_COMMENT,
            level=Notification.Level.INFO,
            title="Old",
            body="Old",
            payload={},
            aggregate_key=aggregate_key,
            dedupe_key="",
            read_at=timezone.now(),
        )

        unread = Notification.objects.create(
            recipient=self.article_author,
            sender=None,
            notification_type=NotificationType.NEW_COMMENT,
            level=Notification.Level.INFO,
            title="New",
            body="New",
            payload={},
            aggregate_key=aggregate_key,
            dedupe_key="",
        )

        self.assertIsNotNone(unread.id)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.article_author,
                aggregate_key=aggregate_key,
                notification_type=NotificationType.NEW_COMMENT,
            ).count(),
            2,
        )

    def test_same_aggregate_key_on_non_comment_notification_does_not_conflict(self):
        aggregate_key = f"new_comment_agg:{self.article_author.id}:{self.article_id}"

        Notification.objects.create(
            recipient=self.article_author,
            sender=None,
            notification_type=NotificationType.SYSTEM,
            level=Notification.Level.INFO,
            title="System 1",
            body="Body",
            payload={},
            aggregate_key=aggregate_key,
            dedupe_key="",
        )

        notification = Notification.objects.create(
            recipient=self.article_author,
            sender=None,
            notification_type=NotificationType.NEW_COMMENT,
            level=Notification.Level.INFO,
            title="Comment",
            body="Body",
            payload={},
            aggregate_key=aggregate_key,
            dedupe_key="",
        )

        self.assertIsNotNone(notification.id)

    def test_same_user_multiple_comments_updates_same_aggregate(self):
        first, first_created = create_or_update_unread_comment_aggregate_notification(
            comment_id=11,
            comment_author_id=self.commenter1.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )
        self.assertTrue(first_created)

        second, second_created = create_or_update_unread_comment_aggregate_notification(
            comment_id=12,
            comment_author_id=self.commenter1.id,
            article_id=self.article_id,
            article_author_id=self.article_author.id,
            article_slug=self.article_slug,
            article_title=self.article_title,
        )

        self.assertFalse(second_created)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Notification.objects.count(), 1)

        second.refresh_from_db()
        self.assertEqual(second.payload["comment_count"], 2)
        self.assertNotIn("has_other_commenters", second.payload)
        self.assertNotIn("sample_commenters", second.payload)
        self.assertNotIn("commenter_ids", second.payload)
        self.assertNotIn("distinct_commenter_count", second.payload)
        self.assertEqual(
            second.body,
            f'2 new comments on your article "{self.article_title}".',
        )

        self.article_author.refresh_from_db()
        self.assertEqual(self.article_author.unread_notifications_count, 1)


class TestCommentAggregateHelpers(SimpleTestCase):
    def test_safe_int(self):
        self.assertEqual(_safe_int(123), 123)
        self.assertEqual(_safe_int("123"), 123)
        self.assertEqual(_safe_int("abc", 7), 7)
        self.assertEqual(_safe_int(None, 9), 9)

    def test_build_comment_aggregate_key(self):
        self.assertEqual(
            _build_comment_aggregate_key(recipient_id=5, article_id=42),
            "new_comment_agg:5:42",
        )

    @patch("notifications.services.comment_aggregation.reverse")
    def test_build_article_link_uses_reverse(self, reverse_mock):
        reverse_mock.return_value = "/articles/some-slug/"
        self.assertEqual(_build_article_link("some-slug"), "/articles/some-slug/")
        reverse_mock.assert_called_once_with("article-details", args=("some-slug",))

    @patch("notifications.services.comment_aggregation.reverse")
    def test_build_article_link_falls_back_to_root_on_reverse_error(self, reverse_mock):
        reverse_mock.side_effect = NoReverseMatch("error")
        self.assertEqual(_build_article_link("some-slug"), "/")

    def test_normalize_comment_aggregate_payload(self):
        normalized = _normalize_comment_aggregate_payload(
            {
                "kind": "ignored",
                "link": "/x/",
                "article_id": "12",
                "article_title": "Hello",
                "comment_count": "3",
                "has_other_commenters": True,
                "last_comment_id": "55",
                "last_comment_at": "ts",
                "sample_commenters": [
                    {"id": "1", "username": "alice"},
                    "bad",
                    {"id": "oops"},
                    {"id": "2", "username": "bob"},
                    {"id": "3", "username": "carol"},
                    {"id": "4", "username": "dave"},
                ],
            }
        )

        self.assertEqual(normalized["kind"], "comment_aggregate")
        self.assertEqual(normalized["link"], "/x/")
        self.assertEqual(normalized["article_id"], 12)
        self.assertEqual(normalized["article_title"], "Hello")
        self.assertEqual(normalized["comment_count"], 3)
        self.assertEqual(normalized["last_comment_id"], 55)
        self.assertEqual(normalized["last_comment_at"], "ts")
        self.assertNotIn("has_other_commenters", normalized)
        self.assertNotIn("sample_commenters", normalized)
        self.assertNotIn("commenter_ids", normalized)
        self.assertNotIn("distinct_commenter_count", normalized)

    def test_build_comment_aggregate_title(self):
        self.assertEqual(_build_comment_aggregate_title(1), "New Comment")
        self.assertEqual(_build_comment_aggregate_title(2), "New Comments")

    def test_build_comment_aggregate_body_single_comment(self):
        body = _build_comment_aggregate_body(count=1, article_title="Article")
        self.assertEqual(body, 'New comment on your article "Article".')

    def test_build_comment_aggregate_body_multiple_comments(self):
        body = _build_comment_aggregate_body(count=4, article_title="Article")
        self.assertEqual(body, '4 new comments on your article "Article".')
