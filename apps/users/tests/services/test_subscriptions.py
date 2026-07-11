from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import TestCase

from users.models import AuthorSubscription, User
from users.services.subscriptions import set_author_subscription


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
