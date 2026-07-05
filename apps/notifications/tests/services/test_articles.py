from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from notifications.models import Notification
from notifications.services.articles import (
    notify_article_published,
    notify_article_rejected,
    notify_article_unpublished,
)


class TestNotifyArticlePublished(SimpleTestCase):
    @patch("notifications.services.articles.dispatch_notification_after_commit")
    @patch("notifications.services.articles.create_deduped_system_notification")
    def test_with_published_at(
        self, mock_create_deduped_system_notification, mock_dispatch
    ):
        notification = Mock()
        notification.id = 101
        notification.notification_type = "system"
        mock_create_deduped_system_notification.return_value = (notification, True)

        article_id = 22
        published_at = timezone.now()

        notify_article_published(
            recipient_id=11,
            article_id=article_id,
            article_slug="my-article",
            article_title="My Article",
            actor_id=33,
            published_at=published_at,
        )

        mock_create_deduped_system_notification.assert_called_once_with(
            recipient_id=11,
            sender_id=33,
            level=Notification.Level.SUCCESS,
            title="Article published",
            body='Your article "My Article" has been published.',
            payload={
                "kind": "article_published",
                "articleId": article_id,
                "articleSlug": "my-article",
                "articleTitle": "My Article",
                "url": reverse(
                    "article-details",
                    kwargs={"article_slug": "my-article"},
                ),
            },
            dedupe_key=f"article-published:{article_id}:{published_at.isoformat()}",
        )
        mock_dispatch.assert_called_once_with(
            notification_id=101, notification_type="system", is_new_unread=True
        )


class TestNotifyArticleRejected(SimpleTestCase):
    @patch("notifications.services.articles.dispatch_notification_after_commit")
    @patch("notifications.services.articles.create_deduped_system_notification")
    def test_with_review_note_and_timestamp(
        self,
        mock_create_deduped_system_notification,
        mock_dispatch,
    ):
        notification = Mock()
        notification.id = 201
        notification.notification_type = "system"
        mock_create_deduped_system_notification.return_value = (notification, True)

        article_id = 20

        notify_article_rejected(
            recipient_id=10,
            article_id=article_id,
            article_slug="draft-article",
            article_title="Draft Article",
            review_note="Please improve structure.",
            reviewer_id=30,
            reviewed_at_ts="2026-03-31T12:34:56+00:00",
        )

        mock_create_deduped_system_notification.assert_called_once_with(
            recipient_id=10,
            sender_id=30,
            level=Notification.Level.WARNING,
            title="Article rejected",
            body=(
                'Your article "Draft Article" was rejected. '
                "Review note: Please improve structure."
            ),
            payload={
                "kind": "article_rejected",
                "articleId": article_id,
                "articleSlug": "draft-article",
                "articleTitle": "Draft Article",
                "reviewNote": "Please improve structure.",
                "url": reverse("article-update", kwargs={"pk": article_id}),
                "reviewedAt": "2026-03-31T12:34:56+00:00",
            },
            dedupe_key=f"article-rejected:{article_id}:2026-03-31T12:34:56+00:00",
        )
        mock_dispatch.assert_called_once_with(
            notification_id=201,
            notification_type="system",
            is_new_unread=True,
        )

    @patch("notifications.services.articles.dispatch_notification_after_commit")
    @patch("notifications.services.articles.create_deduped_system_notification")
    def test_without_review_note_or_timestamp_does_not_dispatch_when_deduped(
        self,
        mock_create_deduped_system_notification,
        mock_dispatch,
    ):
        notification = Mock()
        notification.id = 202
        notification.notification_type = "system"
        mock_create_deduped_system_notification.return_value = (notification, False)

        article_id = 20

        notify_article_rejected(
            recipient_id=10,
            article_id=article_id,
            article_slug="draft-article",
            article_title="Draft Article",
            review_note="",
            reviewer_id=None,
            reviewed_at_ts=None,
        )

        mock_create_deduped_system_notification.assert_called_once_with(
            recipient_id=10,
            sender_id=None,
            level=Notification.Level.WARNING,
            title="Article rejected",
            body='Your article "Draft Article" was rejected.',
            payload={
                "kind": "article_rejected",
                "articleId": article_id,
                "articleSlug": "draft-article",
                "articleTitle": "Draft Article",
                "reviewNote": "",
                "url": reverse("article-update", kwargs={"pk": article_id}),
                "reviewedAt": None,
            },
            dedupe_key=f"article-rejected:{article_id}:draft-article",
        )
        mock_dispatch.assert_not_called()


class TestNotifyArticleUnpublished(SimpleTestCase):
    @patch("notifications.services.articles.dispatch_notification_after_commit")
    @patch("notifications.services.articles.create_deduped_system_notification")
    def test_with_timestamp(
        self,
        mock_create_deduped_system_notification,
        mock_dispatch,
    ):
        notification = Mock()
        notification.id = 301
        notification.notification_type = "system"
        mock_create_deduped_system_notification.return_value = (notification, True)

        article_id = 24

        notify_article_unpublished(
            recipient_id=12,
            article_id=article_id,
            article_slug="published-article",
            article_title="Published Article",
            actor_id=36,
            unpublished_at_ts="2026-03-31T15:00:00+00:00",
        )

        mock_create_deduped_system_notification.assert_called_once_with(
            recipient_id=12,
            sender_id=36,
            level=Notification.Level.WARNING,
            title="Article unpublished",
            body='Your article "Published Article" was unpublished.',
            payload={
                "kind": "article_unpublished",
                "articleId": article_id,
                "articleSlug": "published-article",
                "articleTitle": "Published Article",
                "url": reverse("article-update", kwargs={"pk": article_id}),
                "unpublishedAt": "2026-03-31T15:00:00+00:00",
            },
            dedupe_key=f"article-unpublished:{article_id}:2026-03-31T15:00:00+00:00",
        )
        mock_dispatch.assert_called_once_with(
            notification_id=301,
            notification_type="system",
            is_new_unread=True,
        )

    @patch("notifications.services.articles.dispatch_notification_after_commit")
    @patch("notifications.services.articles.create_deduped_system_notification")
    def test_without_timestamp_does_not_dispatch_when_deduped(
        self,
        mock_create_deduped_system_notification,
        mock_dispatch,
    ):
        notification = Mock()
        notification.id = 302
        notification.notification_type = "system"
        mock_create_deduped_system_notification.return_value = (notification, False)

        article_id = 24

        notify_article_unpublished(
            recipient_id=12,
            article_id=article_id,
            article_slug="published-article",
            article_title="Published Article",
            actor_id=None,
            unpublished_at_ts=None,
        )

        mock_create_deduped_system_notification.assert_called_once_with(
            recipient_id=12,
            sender_id=None,
            level=Notification.Level.WARNING,
            title="Article unpublished",
            body='Your article "Published Article" was unpublished.',
            payload={
                "kind": "article_unpublished",
                "articleId": article_id,
                "articleSlug": "published-article",
                "articleTitle": "Published Article",
                "url": reverse("article-update", kwargs={"pk": article_id}),
                "unpublishedAt": None,
            },
            dedupe_key=f"article-unpublished:{article_id}:published-article",
        )
        mock_dispatch.assert_not_called()
