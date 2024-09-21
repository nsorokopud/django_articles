from django.test import TestCase
from django.urls import reverse

from ..auth_backends import EmailOrUsernameAuthenticationBackend
from ..models import User


class TestAuthenticationBackends(TestCase):
    def test_email_or_username_authentication_backend(self):
        user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="user1_Abc1234"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="user2_Xyz1234"
        )

        authenticate = EmailOrUsernameAuthenticationBackend().authenticate

        request = self.client.get(reverse("login"))
        self.assertEqual(request.status_code, 200)

        self.assertEqual(authenticate(request, username="user1", password="user1_Abc1234"), user1)
        self.assertEqual(
            authenticate(request, username="user1@test.com", password="user1_Abc1234"), user1
        )
        self.assertEqual(authenticate(request, username="user2", password="user2_Xyz1234"), user2)
        self.assertEqual(
            authenticate(request, username="user2@test.com", password="user2_Xyz1234"), user2
        )

        self.assertEqual(authenticate(request, username="user1"), None)
        self.assertEqual(authenticate(request, password="user1_Abcd1234"), None)
        self.assertEqual(authenticate(request, username="user99", password="abc"), None)
        self.assertEqual(authenticate(request, username="user1", password=""), None)
        self.assertEqual(authenticate(request, username="user2", password="user1_Abc1234"), None)
        self.assertEqual(authenticate(request, username="user99", password="user1_Abc1234"), None)
        self.assertEqual(
            authenticate(request, username="user2@test.com", password="user1_Abc1234"), None
        )
        self.assertEqual(
            authenticate(request, username="user99@test.com", password="user1_Abc1234"), None
        )
