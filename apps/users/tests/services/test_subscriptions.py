from django.test import TestCase

from users.models import AuthorSubscription, User
from users.services.subscriptions import (
    advance_subscriptions_last_seen_publish_sequence,
    get_new_articles_summary,
)


class TestGetNewArticlesDigestSummary(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="u", email="u@test.com")

        self.author1 = User.objects.create_user(username="a1", email="a1@test.com")
        self.author2 = User.objects.create_user(username="a2", email="a2@test.com")
        self.author3 = User.objects.create_user(username="a3", email="a3@test.com")

        User.objects.filter(id=self.user.id).update(
            subscriptions_last_seen_publish_sequence=0
        )

    def _sub(self, author: User, *, notifications_enabled: bool = True) -> None:
        AuthorSubscription.objects.create(
            subscriber=self.user,
            author=author,
            notifications_enabled=notifications_enabled,
        )

    def test_uses_max_of_since_and_last_seen_as_watermark(
        self,
    ) -> None:
        User.objects.filter(id=self.user.id).update(
            subscriptions_last_seen_publish_sequence=10
        )

        # author publishes at 11 (should count if watermark is 10)
        User.objects.filter(id=self.author1.id).update(
            latest_article_publish_sequence=11
        )
        self._sub(self.author1, notifications_enabled=True)

        # since_publish_sequence=5 => watermark should
        # still be 10 => has_new True, latest 11
        res = get_new_articles_summary(user_id=self.user.id, since_publish_sequence=5)
        self.assertEqual(res, {"has_new": True, "latest_article_publish_sequence": 11})

        # since_publish_sequence=12 => watermark should
        # be 12 => author(11) not > 12 => False
        res = get_new_articles_summary(user_id=self.user.id, since_publish_sequence=12)
        self.assertEqual(res, {"has_new": False, "latest_article_publish_sequence": 12})

    def test_ignores_subscriptions_with_disabled_notifications(
        self,
    ) -> None:
        User.objects.filter(id=self.author1.id).update(
            latest_article_publish_sequence=100
        )
        self._sub(self.author1, notifications_enabled=False)

        res = get_new_articles_summary(user_id=self.user.id, since_publish_sequence=0)
        self.assertEqual(res, {"has_new": False, "latest_article_publish_sequence": 0})

    def test_aggregate_considers_only_notifications_enabled_subscriptions(self) -> None:
        self._sub(self.author1, notifications_enabled=False)
        self._sub(self.author2, notifications_enabled=True)

        User.objects.filter(id=self.author1.id).update(
            latest_article_publish_sequence=999
        )
        User.objects.filter(id=self.author2.id).update(
            latest_article_publish_sequence=5
        )

        res = get_new_articles_summary(user_id=self.user.id, since_publish_sequence=0)

        self.assertEqual(
            res,
            {"has_new": True, "latest_article_publish_sequence": 5},
        )

    def test_returns_max_latest_article_publish_sequence_across_authors(
        self,
    ) -> None:
        self._sub(self.author1, notifications_enabled=True)
        self._sub(self.author2, notifications_enabled=True)
        self._sub(self.author3, notifications_enabled=True)

        User.objects.filter(id=self.author1.id).update(
            latest_article_publish_sequence=5
        )
        User.objects.filter(id=self.author2.id).update(
            latest_article_publish_sequence=99
        )
        User.objects.filter(id=self.author3.id).update(
            latest_article_publish_sequence=42
        )

        res = get_new_articles_summary(user_id=self.user.id, since_publish_sequence=0)
        self.assertEqual(res, {"has_new": True, "latest_article_publish_sequence": 99})

    def test_returns_false_when_no_subscriptions(
        self,
    ) -> None:
        res = get_new_articles_summary(user_id=self.user.id, since_publish_sequence=0)
        self.assertEqual(res, {"has_new": False, "latest_article_publish_sequence": 0})

    def test_returns_false_when_all_latest_are_at_or_below_watermark(
        self,
    ) -> None:
        self._sub(self.author1, notifications_enabled=True)
        User.objects.filter(id=self.author1.id).update(
            latest_article_publish_sequence=10
        )

        User.objects.filter(id=self.user.id).update(
            subscriptions_last_seen_publish_sequence=10
        )
        res = get_new_articles_summary(user_id=self.user.id, since_publish_sequence=0)
        self.assertEqual(res, {"has_new": False, "latest_article_publish_sequence": 10})

    def test_returns_false_when_subscribed_authors_have_no_published_articles(
        self,
    ) -> None:
        self._sub(self.author1, notifications_enabled=True)
        self._sub(self.author2, notifications_enabled=True)

        res = get_new_articles_summary(user_id=self.user.id, since_publish_sequence=0)

        self.assertEqual(
            res,
            {"has_new": False, "latest_article_publish_sequence": 0},
        )

    def test_returns_false_when_latest_equals_since_publish_sequence(self) -> None:
        self._sub(self.author1, notifications_enabled=True)
        User.objects.filter(id=self.author1.id).update(
            latest_article_publish_sequence=10
        )

        res = get_new_articles_summary(user_id=self.user.id, since_publish_sequence=10)

        self.assertEqual(
            res,
            {"has_new": False, "latest_article_publish_sequence": 10},
        )


class TestAdvanceSubscriptionsLastSeenPublishSequence(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="u", email="u@test.com")

    def test_noop_when_last_seen_publish_sequence_non_positive(
        self,
    ) -> None:
        User.objects.filter(id=self.user.id).update(
            subscriptions_last_seen_publish_sequence=10
        )

        advance_subscriptions_last_seen_publish_sequence(
            user_id=self.user.id, last_seen_publish_sequence=0
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscriptions_last_seen_publish_sequence, 10)

        advance_subscriptions_last_seen_publish_sequence(
            user_id=self.user.id, last_seen_publish_sequence=-5
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscriptions_last_seen_publish_sequence, 10)

    def test_only_moves_forward(
        self,
    ) -> None:
        User.objects.filter(id=self.user.id).update(
            subscriptions_last_seen_publish_sequence=10
        )

        advance_subscriptions_last_seen_publish_sequence(
            user_id=self.user.id, last_seen_publish_sequence=9
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscriptions_last_seen_publish_sequence, 10)

        advance_subscriptions_last_seen_publish_sequence(
            user_id=self.user.id, last_seen_publish_sequence=10
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscriptions_last_seen_publish_sequence, 10)

        advance_subscriptions_last_seen_publish_sequence(
            user_id=self.user.id, last_seen_publish_sequence=11
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscriptions_last_seen_publish_sequence, 11)
