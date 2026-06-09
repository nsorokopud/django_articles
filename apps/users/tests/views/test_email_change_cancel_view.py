from django.test import Client, TestCase
from django.urls import reverse

from users.models import PendingEmailChange, User


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

    def test_no_pending_email_change(self):
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())

        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertRedirects(
            response, reverse("email-change"), status_code=302, target_status_code=200
        )
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())

    def test_with_pending_email_change(self):
        pending_email_change = PendingEmailChange.objects.create(
            user=self.user, email="new-user@test.com"
        )

        self.assertTrue(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertRedirects(
            response, reverse("email-change"), status_code=302, target_status_code=200
        )
        self.assertFalse(
            PendingEmailChange.objects.filter(pk=pending_email_change.pk).exists()
        )
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())
