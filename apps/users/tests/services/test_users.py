from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.db.models import signals
from django.test import TestCase

from users.models import Profile, User
from users.services.users import (
    activate_user,
    advance_latest_article_publish_sequence,
    create_user_profile,
    deactivate_user,
    delete_social_accounts_with_email,
)
from users.signals import create_profile


class TestActivateUser(TestCase):
    def test_creates_lowercase_verified_primary_email_address(self):
        user = User.objects.create_user(
            username="user", email="USER@TEST.COM", is_active=False
        )

        self.assertFalse(user.is_active)
        self.assertEqual(user.email, "user@test.com")
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 0)

        activate_user(user)
        user.refresh_from_db()

        self.assertTrue(user.is_active)
        self.assertEqual(user.email, "user@test.com")
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)

        allauth_email = EmailAddress.objects.get(user=user)
        self.assertEqual(allauth_email.email, "user@test.com")
        self.assertTrue(allauth_email.verified)
        self.assertTrue(allauth_email.primary)

    def test_updates_existing_matching_email_address(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )
        email_address = EmailAddress.objects.create(
            user=user, email="user@test.com", verified=False, primary=False
        )

        activate_user(user)
        user.refresh_from_db()
        email_address.refresh_from_db()

        self.assertTrue(user.is_active)
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)

        self.assertEqual(email_address.email, "user@test.com")
        self.assertTrue(email_address.verified)
        self.assertTrue(email_address.primary)

    def test_demotes_existing_primary_email_address_when_different_email_matches_user(
        self,
    ):
        user = User.objects.create_user(
            username="user", email="new@test.com", is_active=False
        )
        old_primary = EmailAddress.objects.create(
            user=user, email="old@test.com", verified=True, primary=True
        )
        matching_email = EmailAddress.objects.create(
            user=user, email="new@test.com", verified=False, primary=False
        )

        activate_user(user)
        user.refresh_from_db()
        old_primary.refresh_from_db()
        matching_email.refresh_from_db()

        self.assertTrue(user.is_active)

        self.assertFalse(old_primary.primary)
        self.assertTrue(old_primary.verified)

        self.assertTrue(matching_email.primary)
        self.assertTrue(matching_email.verified)
        self.assertEqual(matching_email.email, "new@test.com")

        self.assertEqual(
            EmailAddress.objects.filter(user=user, primary=True).count(), 1
        )

    def test_demotes_existing_primary_email_address_and_creates_matching_email(self):
        user = User.objects.create_user(
            username="user", email="new@test.com", is_active=False
        )
        old_primary = EmailAddress.objects.create(
            user=user, email="old@test.com", verified=True, primary=True
        )

        activate_user(user)
        user.refresh_from_db()
        old_primary.refresh_from_db()

        self.assertTrue(user.is_active)
        self.assertFalse(old_primary.primary)

        matching_email = EmailAddress.objects.get(user=user, email="new@test.com")
        self.assertTrue(matching_email.primary)
        self.assertTrue(matching_email.verified)

        self.assertEqual(
            EmailAddress.objects.filter(user=user, primary=True).count(), 1
        )

    def test_normalizes_user_email_before_activation(self):
        user = User.objects.create_user(
            username="user", email="  User.Abc@Test.COM  ", is_active=False
        )

        activate_user(user)
        user.refresh_from_db()

        self.assertTrue(user.is_active)
        self.assertEqual(user.email, "user.abc@test.com")

        allauth_email = EmailAddress.objects.get(user=user)
        self.assertEqual(allauth_email.email, "user.abc@test.com")
        self.assertTrue(allauth_email.primary)
        self.assertTrue(allauth_email.verified)

    def test_is_idempotent(self):
        user = User.objects.create_user(
            username="user", email="user@test.com", is_active=False
        )

        activate_user(user)
        activate_user(user)

        user.refresh_from_db()

        self.assertTrue(user.is_active)
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)

        allauth_email = EmailAddress.objects.get(user=user)
        self.assertEqual(allauth_email.email, "user@test.com")
        self.assertTrue(allauth_email.verified)
        self.assertTrue(allauth_email.primary)


class TestUserServices(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )

    def tearDown(self):
        signals.post_save.connect(create_profile, sender=User)

    def test_deactivate_user(self):
        user = User.objects.create_user(username="user", email="user@test.com")
        self.assertTrue(user.is_active)
        deactivate_user(user)
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


class TestAdvanceLatestArticlePublishSequence(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user",
            email="user@test.com",
            latest_article_publish_sequence=10,
        )

    def test_updates_sequence_when_new_value_is_greater(self):
        advance_latest_article_publish_sequence(
            user_id=self.user.id,
            publish_sequence=15,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 15)

    def test_does_not_update_sequence_when_new_value_is_equal(self):
        advance_latest_article_publish_sequence(
            user_id=self.user.id,
            publish_sequence=10,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 10)

    def test_does_not_update_sequence_when_new_value_is_smaller(self):
        advance_latest_article_publish_sequence(
            user_id=self.user.id,
            publish_sequence=5,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 10)

    def test_does_nothing_when_user_does_not_exist(self):
        advance_latest_article_publish_sequence(
            user_id=999999,
            publish_sequence=20,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 10)
