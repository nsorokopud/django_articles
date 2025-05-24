from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import signals
from django.test import TestCase

from apps.users.cache import get_subscribers_count_cache_key
from users.models import Profile, User
from users.services import (
    activate_user,
    create_user_profile,
    deactivate_user,
    delete_social_accounts_with_email,
    toggle_user_subscription,
)
from users.signals import create_profile


class TestUserServices(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )

    def tearDown(self):
        signals.post_save.connect(create_profile, sender=User)

    def test_activate_user(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )

        self.assertFalse(user.is_active)
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 0)
        with self.assertRaises(EmailAddress.DoesNotExist):
            EmailAddress.objects.get(user=user, email=user.email)

        activate_user(user)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)
        allauth_email = EmailAddress.objects.get(user=user)
        self.assertEqual(allauth_email.email, user.email)
        self.assertTrue(allauth_email.verified)
        self.assertTrue(allauth_email.primary)

    def test_deactivate_user(self):
        user = User.objects.create_user(username="user", email="user@test.com")
        self.assertTrue(user.is_active)
        deactivate_user(user)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_create_user_profile(self):
        signals.post_save.disconnect(create_profile, sender=User)

        u = User.objects.create(username="user", email="test1@test.com")

        with self.assertRaises(Profile.DoesNotExist):
            profile = Profile.objects.get(user=u)

        profile = create_user_profile(u)
        self.assertEqual(profile.user, u)
        self.assertEqual(Profile.objects.filter(user=u).first(), profile)

    def test_delete_social_accounts_with_email(self):
        email = "email@test.com"
        email2 = "email2@test.com"
        account1 = SocialAccount(
            user=self.test_user, provider="p1", uid="123", extra_data={"email": email}
        )
        account2 = SocialAccount(
            user=self.test_user, provider="p2", uid="456", extra_data={"email": email}
        )
        account3 = SocialAccount(
            user=self.test_user, provider="p3", uid="789", extra_data={"email": email2}
        )
        SocialAccount.objects.bulk_create([account1, account2, account3])

        delete_social_accounts_with_email("nonexistent@test.com")

        self.assertEqual(
            SocialAccount.objects.filter(extra_data__email=email).count(), 2
        )
        self.assertEqual(
            SocialAccount.objects.filter(extra_data__email=email2).count(), 1
        )

        delete_social_accounts_with_email(email)

        self.assertEqual(
            SocialAccount.objects.filter(extra_data__email=email).count(), 0
        )
        self.assertEqual(
            SocialAccount.objects.filter(extra_data__email=email2).count(), 1
        )


class TestToggleUserSubscription(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user",
            email="user@test.com",
            is_active=True,
        )
        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
            is_active=True,
        )

    def test_subscribe_unsubscribe(self):
        self.assertNotIn(self.user, self.author.profile.subscribers.all())
        res = toggle_user_subscription(self.user, self.author)
        self.assertTrue(res)
        self.assertIn(self.user, self.author.profile.subscribers.all())
        res = toggle_user_subscription(self.user, self.author)
        self.assertFalse(res)
        self.assertNotIn(self.user, self.author.profile.subscribers.all())

    def test_anonymous_user(self):
        anon_user = AnonymousUser()
        with self.assertRaises(ValidationError) as context:
            toggle_user_subscription(anon_user, self.author)
        self.assertIn(
            "Anonymous users cannot subscribe to authors.", str(context.exception)
        )

    def test_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(ValidationError) as context:
            toggle_user_subscription(self.user, self.author)
        self.assertIn(
            "Inactive users cannot subscribe to authors.", str(context.exception)
        )

    def test_subscribe_self(self):
        with self.assertRaises(ValidationError) as context:
            toggle_user_subscription(self.user, self.user)
        self.assertIn("Users cannot subscribe to themselves.", str(context.exception))

    def test_inactive_author(self):
        self.author.is_active = False
        self.author.save()
        with self.assertRaises(ValidationError) as context:
            toggle_user_subscription(self.user, self.author)
        self.assertIn("Cannot subscribe to inactive authors.", str(context.exception))

    def test_author_without_profile(self):
        self.author.profile.delete()
        self.author.refresh_from_db()
        with self.assertRaises(ValidationError) as context:
            toggle_user_subscription(self.user, self.author)
        self.assertIn("Author does not have a profile.", str(context.exception))

    def test_cache_invalidation(self):
        cache.set(get_subscribers_count_cache_key(self.author.id), 42)
        self.assertEqual(cache.get(get_subscribers_count_cache_key(self.author.id)), 42)

        toggle_user_subscription(self.user, self.author)

        self.assertIsNone(cache.get(get_subscribers_count_cache_key(self.author.id)))
