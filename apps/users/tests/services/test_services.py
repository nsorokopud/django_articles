from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import signals
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.models import Profile, User
from users.services.services import (
    activate_user,
    change_email_address,
    create_pending_email_address,
    create_user_profile,
    deactivate_user,
    delete_pending_email_address,
    delete_social_accounts_with_email,
    enforce_unique_email_type_per_user,
    find_user_profiles_with_subscribers,
    get_all_supscriptions_of_user,
    get_all_users,
    get_pending_email_address,
    get_user_by_id,
    get_user_by_username,
    send_account_activation_email,
    send_email_change_link,
    toggle_user_supscription,
)
from users.signals import create_profile


class TestServices(TestCase):
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
        self.assertFalse(user.is_active)

    def test_create_user_profile(self):
        signals.post_save.disconnect(create_profile, sender=User)

        u = User.objects.create(username="user", email="test1@test.com")

        with self.assertRaises(Profile.DoesNotExist):
            profile = Profile.objects.get(user=u)

        profile = create_user_profile(u)
        self.assertEqual(profile.user, u)
        self.assertEqual(Profile.objects.filter(user=u).first(), profile)

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

    def test_get_all_supscriptions_of_user(self):
        a1 = User.objects.create_user(username="author1", email="author1@test.com")
        a2 = User.objects.create_user(username="author2", email="author2@test.com")

        res = get_all_supscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [])

        a1.profile.subscribers.add(self.test_user)
        res = get_all_supscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [a1.username])

        a2.profile.subscribers.add(self.test_user)
        res = get_all_supscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [a1.username, a2.username])

        a2.profile.subscribers.remove(self.test_user)
        res = get_all_supscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [a1.username])

        a1.profile.subscribers.remove(self.test_user)
        res = get_all_supscriptions_of_user(self.test_user)
        self.assertCountEqual(res, [])

    def test_get_all_users(self):
        self.assertCountEqual(get_all_users(), [self.test_user])

        new_user = User.objects.create(username="new_user")
        self.assertCountEqual(get_all_users(), [self.test_user, new_user])

        new_user.delete()
        self.assertCountEqual(get_all_users(), [self.test_user])

    def test_send_account_activation_email(self):
        html_template = (
            "\n  Hello, {username}.\n  <br>\n  <br>\n"
            "  Please follow the link to finish your registration:\n"
            '  <a href="{url}">'
            "Finish registration</a>\n\n"
        )
        plain_template = (
            "Hello, {username}.\n\nPlease follow the link to finish your registration:"
            "\n{url}\n"
        )

        user1 = User.objects.create_user(username="user1", email="user1@test.com")
        user2 = User.objects.create_user(username="user2", email="user2@test.com")

        self.assertEqual(len(mail.outbox), 0)

        factory = RequestFactory()
        request = factory.get(reverse("post-registration"), secure=True)
        request.META["HTTP_HOST"] = "testserver"
        request.user = user1

        with patch(
            "users.services.tokens.activation_token_generator.make_token",
            return_value="token1",
        ):
            send_account_activation_email(request, user1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), ["user1@test.com"])
        self.assertEqual(mail.outbox[0].subject, "User account activation")
        uid = urlsafe_base64_encode(force_bytes(user1.pk))
        expected_url = f"https://testserver/activate_account/{uid}/token1/"
        self.assertEqual(
            mail.outbox[0].alternatives[0][0],
            html_template.format(username=user1.username, url=expected_url),
        )
        self.assertEqual(
            mail.outbox[0].body,
            plain_template.format(username=user1.username, url=expected_url),
        )
        self.assertEqual(len(mail.outbox[0].alternatives), 1)

        request = factory.get(reverse("post-registration"), secure=False)
        request.META["HTTP_HOST"] = "testserver"
        request.user = user2

        with patch(
            "users.services.tokens.activation_token_generator.make_token",
            return_value="token2",
        ):
            send_account_activation_email(request, user2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].recipients(), ["user2@test.com"])
        uid = urlsafe_base64_encode(force_bytes(user2.pk))
        expected_url = f"http://testserver/activate_account/{uid}/token2/"
        self.assertEqual(
            mail.outbox[1].alternatives[0][0],
            html_template.format(username=user2.username, url=expected_url),
        )
        self.assertEqual(
            mail.outbox[1].body,
            plain_template.format(username=user2.username, url=expected_url),
        )
        self.assertEqual(len(mail.outbox[1].alternatives), 1)

    def test_send_email_change_link(self):
        html_template = (
            "\n  Hello, {username}.\n  <br>\n  <br>\n"
            "  Please follow the link to confirm this email address as your new one:\n"
            '  <a href="{url}">'
            "Change email</a>\n\n"
        )
        plain_template = (
            "Hello, {username}.\n\nPlease follow the link to confirm this "
            "email address as your new one:\n{url}\n"
        )

        user1 = User.objects.create_user(username="user1", email="user1@test.com")
        user2 = User.objects.create_user(username="user2", email="user2@test.com")

        factory = RequestFactory()
        request = factory.get(
            reverse("email-change-confirm", args=["token1"]), secure=True
        )
        request.META["HTTP_HOST"] = "testserver"

        request.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):  # change exception type
            send_email_change_link(request, user1)
        self.assertEqual(len(mail.outbox), 0)

        request.user = user1
        with patch(
            "users.services.tokens.email_change_token_generator.make_token",
            return_value="token1",
        ):
            send_email_change_link(request, "u1@test.com")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), ["u1@test.com"])
        self.assertEqual(mail.outbox[0].subject, "Confirm email change")
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        expected_url = "https://testserver/confirm_email_change/token1/"
        self.assertEqual(
            mail.outbox[0].alternatives[0][0],
            html_template.format(username=user1.username, url=expected_url),
        )
        self.assertEqual(
            mail.outbox[0].body,
            plain_template.format(username=user1.username, url=expected_url),
        )

        request = factory.get(
            reverse("email-change-confirm", args=["token2"]), secure=False
        )
        request.META["HTTP_HOST"] = "testserver"
        request.user = user2

        with patch(
            "users.services.tokens.email_change_token_generator.make_token",
            return_value="token2",
        ):
            send_email_change_link(request, "u2@test.com")

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].recipients(), ["u2@test.com"])
        expected_url = "http://testserver/confirm_email_change/token2/"
        self.assertEqual(
            mail.outbox[1].alternatives[0][0],
            html_template.format(username=user2.username, url=expected_url),
        )
        self.assertEqual(
            mail.outbox[1].body,
            plain_template.format(username=user2.username, url=expected_url),
        )

    def test_toggle_user_supscription(self):
        author = User.objects.create(username="author")

        self.assertTrue(self.test_user not in author.profile.subscribers.all())

        toggle_user_supscription(self.test_user, author)
        self.assertTrue(self.test_user in author.profile.subscribers.all())

        toggle_user_supscription(self.test_user, author)
        self.assertTrue(self.test_user not in author.profile.subscribers.all())

        self.assertTrue(self.test_user not in self.test_user.profile.subscribers.all())
        toggle_user_supscription(self.test_user, self.test_user)
        self.assertTrue(self.test_user not in self.test_user.profile.subscribers.all())

    def test_create_pending_email_address(self):
        self.assertEqual(
            EmailAddress.objects.filter(
                user=self.test_user, primary=False, verified=False
            ).count(),
            0,
        )
        create_pending_email_address(self.test_user, email="new@test.com")
        self.assertEqual(
            EmailAddress.objects.get(
                user=self.test_user, primary=False, verified=False
            ).email,
            "new@test.com",
        )

    def test_delete_pending_email_address(self):
        self.assertEqual(EmailAddress.objects.count(), 0)
        delete_pending_email_address(self.test_user)

        email = EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )
        self.assertEqual(EmailAddress.objects.count(), 1)
        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 1)

        email.primary = False
        email.save()
        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 1)

        email.primary = True
        email.verified = False
        email.save()
        delete_pending_email_address(self.test_user)
        self.assertEqual(EmailAddress.objects.count(), 1)

        email.primary = False
        email.save()
        delete_pending_email_address(self.test_user)
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

    def test_change_email_address(self):
        email1 = EmailAddress.objects.create(
            user=self.test_user, email=self.test_user.email, primary=True, verified=True
        )
        email2 = EmailAddress.objects.create(
            user=self.test_user, email="e2@test.com", primary=False, verified=True
        )
        SocialAccount.objects.create(
            user=self.test_user,
            provider="p1",
            uid="123",
            extra_data={"email": email1.email},
        )
        self.assertEqual(SocialAccount.objects.count(), 1)

        with self.assertRaises(EmailAddress.DoesNotExist):
            change_email_address(self.test_user.id)

        email2.verified = False
        email2.save(update_fields=["verified"])

        change_email_address(self.test_user.id)
        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.email, email2.email)

        email2.refresh_from_db()
        self.assertTrue(email2.primary)
        self.assertTrue(email2.verified)

        with self.assertRaises(EmailAddress.DoesNotExist):
            EmailAddress.objects.get(pk=email1.pk)

        self.assertEqual(SocialAccount.objects.count(), 0)


class TestEnforceUniqueEmailTypePerUser(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="test@test.com")

    def test_one_primary_email_allowed(self):
        EmailAddress.objects.create(
            user=self.user, email="test1@test.com", primary=True
        )
        email2 = EmailAddress(user=self.user, email="test2@test.com", primary=False)
        enforce_unique_email_type_per_user(email2)

        email2.save()
        email3 = EmailAddress(user=self.user, email="test3@test.com", primary=False)
        with self.assertRaises(ValidationError) as context:
            enforce_unique_email_type_per_user(email3)
            self.assertEqual(
                str(context.exception),
                "['This user already has a primary email address.']",
            )

    def test_one_non_primary_email_allowed(self):
        EmailAddress.objects.create(
            user=self.user, email="test1@test.com", primary=False
        )
        email2 = EmailAddress(user=self.user, email="test2@test.com", primary=True)
        enforce_unique_email_type_per_user(email2)

        email2.save()
        email3 = EmailAddress(user=self.user, email="test3@test.com", primary=True)
        with self.assertRaises(ValidationError) as context:
            enforce_unique_email_type_per_user(email3)
            self.assertEqual(
                str(context.exception),
                "['This user already has a primary email address.']",
            )

    def test_many_unsaved_instances_allowed(self):
        email1 = EmailAddress(user=self.user, email="e1@test.com", primary=True)
        email2 = EmailAddress(user=self.user, email="e2@test.com", primary=True)
        email3 = EmailAddress(user=self.user, email="e3@test.com", primary=True)
        enforce_unique_email_type_per_user(email1)
        enforce_unique_email_type_per_user(email2)
        enforce_unique_email_type_per_user(email3)

        email4 = EmailAddress(user=self.user, email="e4@test.com", primary=False)
        email5 = EmailAddress(user=self.user, email="e5@test.com", primary=False)
        email6 = EmailAddress(user=self.user, email="e6@test.com", primary=False)
        enforce_unique_email_type_per_user(email4)
        enforce_unique_email_type_per_user(email5)
        enforce_unique_email_type_per_user(email6)
