from django.contrib.auth.models import AnonymousUser
from django.db.models import signals
from django.http.response import Http404
from django.test import TestCase

from users.models import PendingEmailChange, User
from users.selectors import (
    find_authors_subscribed_by_user,
    get_author_with_viewer_subscription_status,
    get_pending_email_change,
    get_user_by_id,
)
from users.signals import create_profile


class TestSelectors(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )

    def tearDown(self):
        signals.post_save.connect(create_profile, sender=User)

    def test_get_user_by_id(self):
        u1 = get_user_by_id(self.test_user.id)
        self.assertEqual(u1, self.test_user)

        u1_id = u1.id
        next_user_id = u1_id + 1
        with self.assertRaises(User.DoesNotExist):
            get_user_by_id(next_user_id)

        u2 = User.objects.create(username="user2", email="test2@test.com")
        next_user = get_user_by_id(next_user_id)
        self.assertEqual(next_user, u2)

        with self.assertRaises(User.DoesNotExist):
            get_user_by_id(999)

    def test_find_authors_subscribed_by_user(self):
        a1 = User.objects.create_user(username="author1", email="author1@test.com")
        a2 = User.objects.create_user(username="author2", email="author2@test.com")

        res = find_authors_subscribed_by_user(self.test_user)
        self.assertCountEqual(res, [])

        a1.subscribers.add(self.test_user)
        res = find_authors_subscribed_by_user(self.test_user)
        self.assertCountEqual(res, [a1])

        a2.subscribers.add(self.test_user)
        res = find_authors_subscribed_by_user(self.test_user)
        self.assertCountEqual(res, [a1, a2])

        a2.subscribers.remove(self.test_user)
        res = find_authors_subscribed_by_user(self.test_user)
        self.assertCountEqual(res, [a1])

        a1.subscribers.remove(self.test_user)
        res = find_authors_subscribed_by_user(self.test_user)
        self.assertCountEqual(res, [])

    def test_get_pending_email_change(self):
        res = get_pending_email_change(self.test_user)
        self.assertIsNone(res)

        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="new-test@test.com"
        )

        res = get_pending_email_change(self.test_user)
        self.assertEqual(res.pk, pending_email_change.pk)
        self.assertEqual(res.email, pending_email_change.email)

    def test_get_pending_email_change_after_delete(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.test_user, email="new-test@test.com"
        )

        res = get_pending_email_change(self.test_user)
        self.assertEqual(res.pk, pending_email_change.pk)

        pending_email_change.delete()
        self.test_user.refresh_from_db()

        res = get_pending_email_change(self.test_user)
        self.assertIsNone(res)


class TestGetAuthorWithViewerSubscriptionStatus(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_viewer_is_subscribed(self):
        self.author.subscribers.add(self.user)
        result = get_author_with_viewer_subscription_status(self.author.id, self.user)
        self.assertEqual(result, self.author)
        self.assertTrue(result.is_subscribed_by_viewer)

    def test_viewer_not_subscribed(self):
        result = get_author_with_viewer_subscription_status(self.author.id, self.user)
        self.assertEqual(result, self.author)
        self.assertFalse(result.is_subscribed_by_viewer)

    def test_anonymous_user(self):
        anonymous = AnonymousUser()
        author = get_author_with_viewer_subscription_status(self.author.id, anonymous)
        self.assertFalse(author.is_subscribed_by_viewer)

    def test_author_does_not_exist(self):
        with self.assertRaises(Http404):
            get_author_with_viewer_subscription_status(9999, self.user)
