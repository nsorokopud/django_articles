from django.test import RequestFactory, TestCase

from ..auth_backends import EmailOrUsernameAuthenticationBackend
from ..models import User


class TestAuthenticationBackends(TestCase):
    def setUp(self):
        self.backend = EmailOrUsernameAuthenticationBackend()
        self.authenticate = self.backend.authenticate
        self.request = RequestFactory().get("/login/")

        self.user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password="user1_Abc1234"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password="user2_Xyz1234"
        )

    def test_authenticates_by_username(self):
        self.assertEqual(
            self.authenticate(self.request, username="user1", password="user1_Abc1234"),
            self.user1,
        )
        self.assertEqual(
            self.authenticate(self.request, username="user2", password="user2_Xyz1234"),
            self.user2,
        )

    def test_authenticates_by_username_case_insensitively(self):
        self.assertEqual(
            self.authenticate(self.request, username="USER1", password="user1_Abc1234"),
            self.user1,
        )
        self.assertEqual(
            self.authenticate(self.request, username="User2", password="user2_Xyz1234"),
            self.user2,
        )

    def test_authenticates_by_email_case_insensitively(self):
        self.assertEqual(
            self.authenticate(
                self.request, username="USER1@TEST.COM", password="user1_Abc1234"
            ),
            self.user1,
        )
        self.assertEqual(
            self.authenticate(
                self.request, username="User2@Test.Com", password="user2_Xyz1234"
            ),
            self.user2,
        )

    def test_identifier_with_at_symbol_is_treated_as_email(self):
        user = User.objects.create_user(
            username="plainusername",
            email="plainusername@test.com",
            password="plain_Abc1234",
        )

        self.assertEqual(
            self.authenticate(
                self.request,
                username="plainusername@test.com",
                password="plain_Abc1234",
            ),
            user,
        )

        self.assertIsNone(
            self.authenticate(
                self.request,
                username="plainusername@test.com",
                password="wrong_password",
            )
        )

    def test_strips_identifier_whitespace(self):
        self.assertEqual(
            self.authenticate(
                self.request, username="  user1@test.com  ", password="user1_Abc1234"
            ),
            self.user1,
        )
        self.assertEqual(
            self.authenticate(
                self.request, username="  user1  ", password="user1_Abc1234"
            ),
            self.user1,
        )

    def test_returns_none_when_username_or_password_missing(self):
        self.assertIsNone(self.authenticate(self.request, username="user1"))
        self.assertIsNone(self.authenticate(self.request, password="user1_Abc1234"))
        self.assertIsNone(
            self.authenticate(self.request, username=None, password="user1_Abc1234")
        )
        self.assertIsNone(
            self.authenticate(self.request, username="user1", password=None)
        )

    def test_returns_none_when_identifier_is_blank(self):
        self.assertIsNone(
            self.authenticate(self.request, username="", password="user1_Abc1234")
        )
        self.assertIsNone(
            self.authenticate(self.request, username="   ", password="user1_Abc1234")
        )

    def test_returns_none_for_unknown_identifier(self):
        self.assertIsNone(
            self.authenticate(self.request, username="user99", password="abc")
        )
        self.assertIsNone(
            self.authenticate(
                self.request, username="user99@test.com", password="user1_Abc1234"
            )
        )

    def test_returns_none_for_wrong_password(self):
        self.assertIsNone(
            self.authenticate(self.request, username="user1", password="wrong_password")
        )
        self.assertIsNone(
            self.authenticate(
                self.request, username="user1@test.com", password="wrong_password"
            )
        )
        self.assertIsNone(
            self.authenticate(self.request, username="user2", password="user1_Abc1234")
        )
        self.assertIsNone(
            self.authenticate(
                self.request, username="user2@test.com", password="user1_Abc1234"
            )
        )

    def test_returns_none_for_empty_password(self):
        self.assertIsNone(
            self.authenticate(self.request, username="user1", password="")
        )

    def test_returns_none_for_inactive_user(self):
        inactive_user = User.objects.create_user(
            username="inactive",
            email="inactive@test.com",
            password="inactive_Abc1234",
            is_active=False,
        )

        self.assertIsNone(
            self.authenticate(
                self.request, username="inactive", password="inactive_Abc1234"
            )
        )
        self.assertIsNone(
            self.authenticate(
                self.request, username="INACTIVE@TEST.COM", password="inactive_Abc1234"
            )
        )

        inactive_user.refresh_from_db()
        self.assertFalse(inactive_user.is_active)
