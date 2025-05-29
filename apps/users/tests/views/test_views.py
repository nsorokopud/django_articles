from django.test import Client, TestCase
from django.urls import reverse

from users.models import User


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )

    def test_post_registration_view(self):
        response = self.client.get(reverse("post-registration"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/post_registration.html")

        response = self.client.post(reverse("post-registration"))
        self.assertEqual(response.status_code, 405)

    def test_author_subscribe_view(self):
        author = User.objects.create_user(username="author1")

        target_url = reverse("author-subscribe", kwargs={"author_id": author.id})
        response = self.client.post(target_url)

        redirect_url = f"{reverse('login')}?next={target_url}"
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

        self.client.force_login(self.test_user)
        self.assertTrue(self.test_user not in author.subscribers.all())

        response = self.client.post(target_url)
        redirect_url = reverse("author-page", kwargs={"author_id": author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertTrue(self.test_user in author.subscribers.all())

        response = self.client.post(target_url)
        redirect_url = reverse("author-page", kwargs={"author_id": author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertTrue(self.test_user not in author.subscribers.all())

    def test_password_set_view_get(self):
        url = reverse("password-set")

        # anonymous user
        response = self.client.get(url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)

        # user with usable password
        self.test_user.set_password("12345")
        self.test_user.save()
        self.client.force_login(self.test_user)
        response = self.client.get(url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)

        # user without usable password
        user = User.objects.create_user(username="user1", email="user1@test.com")
        self.client.force_login(user)
        response = self.client.get(url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/password_set.html")

    def test_password_set_view_post(self):
        user = User.objects.create_user(username="user1", email="user1@test.com")
        password = "Abcd1234!"
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.check_password(password))

        url = reverse("password-set")

        # anonymous user
        response = self.client.post(
            url,
            {
                "password1": password,
                "password2": password,
            },
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)

        # user with usable password
        self.test_user.set_password("12345")
        self.test_user.save()
        self.client.force_login(self.test_user)
        response = self.client.post(
            url,
            {
                "password1": password,
                "password2": password,
            },
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.test_user.check_password("12345"))

        # user without usable password
        self.client.force_login(user)
        response = self.client.post(
            url,
            {
                "password1": password,
                "password2": password,
            },
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertRedirects(
            response, reverse("user-profile"), status_code=302, target_status_code=200
        )
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password(password))
