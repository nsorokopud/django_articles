from allauth.account.models import EmailAddress
from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestEmailChangeCancelView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("email-change-cancel")
        self.user = User.objects.create_user(username="user", email="user@test.com")

    def test_anonymous_user(self):
        redirect_url = f'{reverse("login")}?next={self.url}'
        response = self.client.post(self.url)
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_no_pending_email_address(self):
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=True
        )
        self.assertEqual(EmailAddress.objects.filter(user=self.user).count(), 1)
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertRedirects(
            response, reverse("email-change"), status_code=302, target_status_code=200
        )
        self.assertEqual(EmailAddress.objects.filter(user=self.user).count(), 1)

    def test_with_pending_email_address(self):
        email = EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=False, verified=False
        )
        self.assertEqual(EmailAddress.objects.filter(user=self.user).count(), 1)

        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertRedirects(
            response, reverse("email-change"), status_code=302, target_status_code=200
        )
        with self.assertRaises(EmailAddress.DoesNotExist):
            EmailAddress.objects.get(pk=email.pk)
        self.assertEqual(EmailAddress.objects.filter(user=self.user).count(), 0)
