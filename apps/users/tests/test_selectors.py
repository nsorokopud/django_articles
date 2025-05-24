from allauth.account.models import EmailAddress
from django.db.models import signals
from django.test import TestCase

from users.models import Profile, User
from users.selectors import (
    find_user_profiles_with_subscribers,
    get_all_subscriptions_of_user,
    get_all_users,
    get_pending_email_address,
    get_user_by_id,
    get_user_by_username,
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

    def test_find_user_profiles_with_subscribers(self):
        signals.post_save.disconnect(create_profile, sender=User)

        u1 = User.objects.create(username="user1", email="test1@test.com")
        u2 = User.objects.create(username="user2", email="test2@test.com")

        p0 = self.test_user.profile
        p1 = Profile.objects.create(user=u1)
        p2 = Profile.objects.create(user=u2)

        self.assertCountEqual(find_user_profiles_with_subscribers(), [])

        p0.subscribers.add(*[u1, u2])
        self.assertCountEqual(find_user_profiles_with_subscribers(), [p0])

        p1.subscribers.add(u2)
        self.assertCountEqual(find_user_profiles_with_subscribers(), [p0, p1])

        p1.subscribers.remove(u2)
        self.assertCountEqual(find_user_profiles_with_subscribers(), [p0])

        p0.subscribers.remove(*[u1, u2])
        self.assertCountEqual(find_user_profiles_with_subscribers(), [])

    def test_get_user_by_username(self):
        u1 = User.objects.create_user(username="user1")

        res = get_user_by_username(self.test_user.username)
        self.assertEqual(res, self.test_user)

        res = get_user_by_username(u1.username)
        self.assertEqual(res, u1)

        with self.assertRaises(User.DoesNotExist):
            get_user_by_username("non_existent_user")

    def test_get_all_subscriptions_of_user(self):
        a1 = User.objects.create_user(username="author1", email="author1@test.com")
        a2 = User.objects.create_user(username="author2", email="author2@test.com")

        res = get_all_subscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [])

        a1.profile.subscribers.add(self.test_user)
        res = get_all_subscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [(a1.id, a1.username)])

        a2.profile.subscribers.add(self.test_user)
        res = get_all_subscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [(a1.id, a1.username), (a2.id, a2.username)])

        a2.profile.subscribers.remove(self.test_user)
        res = get_all_subscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [(a1.id, a1.username)])

        a1.profile.subscribers.remove(self.test_user)
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
