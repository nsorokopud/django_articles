from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase

from users.cache import get_subscribers_count_cache_key
from users.models import AuthorSubscription, User
from users.services.subscriptions import (
    advance_subscriptions_last_seen_publish_sequence,
    get_new_articles_summary,
    set_author_subscription,
)


class TestSetAuthorSubscription(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )

    def test_subscribe_creates_subscription(self):
        self.assertFalse(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).exists()
        )

        is_subscribed, changed = set_author_subscription(
            subscriber=self.user, author=self.author, should_subscribe=True
        )

        self.assertTrue(is_subscribed)
        self.assertTrue(changed)
        self.assertTrue(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).exists()
        )

    def test_subscribe_is_idempotent_when_already_subscribed(self):
        AuthorSubscription.objects.create(subscriber=self.user, author=self.author)

        is_subscribed, changed = set_author_subscription(
            subscriber=self.user, author=self.author, should_subscribe=True
        )

        self.assertTrue(is_subscribed)
        self.assertFalse(changed)
        self.assertEqual(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).count(),
            1,
        )

    def test_unsubscribe_deletes_subscription(self):
        AuthorSubscription.objects.create(subscriber=self.user, author=self.author)

        is_subscribed, changed = set_author_subscription(
            subscriber=self.user, author=self.author, should_subscribe=False
        )

        self.assertFalse(is_subscribed)
        self.assertTrue(changed)
        self.assertFalse(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).exists()
        )

    def test_unsubscribe_is_idempotent_when_not_subscribed(self):
        is_subscribed, changed = set_author_subscription(
            subscriber=self.user, author=self.author, should_subscribe=False
        )

        self.assertFalse(is_subscribed)
        self.assertFalse(changed)
        self.assertFalse(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).exists()
        )

    def test_anonymous_user(self):
        anon_user = AnonymousUser()

        with self.assertRaises(ValidationError) as context:
            set_author_subscription(
                subscriber=anon_user, author=self.author, should_subscribe=True
            )

        self.assertIn(
            "Anonymous users cannot subscribe to authors.", str(context.exception)
        )

    def test_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError) as context:
            set_author_subscription(
                subscriber=self.user, author=self.author, should_subscribe=True
            )

        self.assertIn(
            "Inactive users cannot subscribe to authors.", str(context.exception)
        )

    def test_subscribe_self(self):
        with self.assertRaises(ValidationError) as context:
            set_author_subscription(
                subscriber=self.user, author=self.user, should_subscribe=True
            )

        self.assertIn("Users cannot subscribe to themselves.", str(context.exception))

    def test_inactive_author(self):
        self.author.is_active = False
        self.author.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError) as context:
            set_author_subscription(
                subscriber=self.user, author=self.author, should_subscribe=True
            )

        self.assertIn(
            "Cannot subscribe to inactive authors.",
            str(context.exception),
        )

    def test_cache_invalidation_on_subscribe(self):
        cache_key = get_subscribers_count_cache_key(self.author.id)
        cache.set(cache_key, 42)

        self.assertEqual(cache.get(cache_key), 42)

        with self.captureOnCommitCallbacks(execute=True):
            set_author_subscription(
                subscriber=self.user, author=self.author, should_subscribe=True
            )

        self.assertIsNone(cache.get(cache_key))

    def test_cache_invalidation_on_unsubscribe(self):
        AuthorSubscription.objects.create(subscriber=self.user, author=self.author)

        cache_key = get_subscribers_count_cache_key(self.author.id)
        cache.set(cache_key, 42)

        self.assertEqual(cache.get(cache_key), 42)

        with self.captureOnCommitCallbacks(execute=True):
            set_author_subscription(
                subscriber=self.user, author=self.author, should_subscribe=False
            )

        self.assertIsNone(cache.get(cache_key))

    def test_cache_not_invalidated_when_subscribe_does_not_change_state(self):
        AuthorSubscription.objects.create(subscriber=self.user, author=self.author)

        cache_key = get_subscribers_count_cache_key(self.author.id)
        cache.set(cache_key, 42)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            set_author_subscription(
                subscriber=self.user, author=self.author, should_subscribe=True
            )

        self.assertEqual(callbacks, [])
        self.assertEqual(cache.get(cache_key), 42)

    def test_cache_not_invalidated_when_unsubscribe_does_not_change_state(self):
        cache_key = get_subscribers_count_cache_key(self.author.id)
        cache.set(cache_key, 42)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            set_author_subscription(
                subscriber=self.user, author=self.author, should_subscribe=False
            )

        self.assertEqual(callbacks, [])
        self.assertEqual(cache.get(cache_key), 42)


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
