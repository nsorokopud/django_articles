from allauth.account.models import EmailAddress
from django.contrib.auth.models import AnonymousUser
from django.db.models import signals
from django.http.response import Http404
from django.test import TestCase

from users.models import User
from users.selectors import (
    get_all_subscriptions_of_user,
    get_all_users,
    get_author_with_viewer_subscription_status,
    get_pending_email_address,
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

    def test_get_all_subscriptions_of_user(self):
        a1 = User.objects.create_user(username="author1", email="author1@test.com")
        a2 = User.objects.create_user(username="author2", email="author2@test.com")

        res = get_all_subscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [])

        a1.subscribers.add(self.test_user)
        res = get_all_subscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [(a1.id, a1.username)])

        a2.subscribers.add(self.test_user)
        res = get_all_subscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [(a1.id, a1.username), (a2.id, a2.username)])

        a2.subscribers.remove(self.test_user)
        res = get_all_subscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [(a1.id, a1.username)])

        a1.subscribers.remove(self.test_user)
        res = get_all_subscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [])

    def test_get_all_users(self):
        self.assertCountEqual(get_all_users(), [self.test_user])

        new_user = User.objects.create(username="new_user")
        self.assertCountEqual(get_all_users(), [self.test_user, new_user])

        new_user.delete()
        self.assertCountEqual(get_all_users(), [self.test_user])

        self.assertEqual(EmailAddress.objects.count(), 0)

    def test_get_pending_email_address(self):
        res = get_pending_email_address(self.test_user)
        self.assertEqual(res, None)

        email = EmailAddress.objects.create(
            user=self.test_user,
            email=self.test_user.email,
            primary=True,
            verified=True,
        )
        res = get_pending_email_address(self.test_user)
        self.assertEqual(res, None)

        email.primary = False
        email.save()
        res = get_pending_email_address(self.test_user)
        self.assertEqual(res, None)

        email.primary = True
        email.verified = False
        email.save()
        res = get_pending_email_address(self.test_user)
        self.assertEqual(res, None)

        email.primary = False
        email.verified = False
        email.save()
        res = get_pending_email_address(self.test_user)
        self.assertEqual(res.pk, email.pk)


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
