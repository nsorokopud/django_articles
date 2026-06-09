from django.test import Client, TestCase
from django.urls import reverse

from users.models import AuthorSubscription, User


class TestAuthorSubscribeView(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.url = reverse("author-subscribe", kwargs={"author_id": self.author.id})

    def test_post_anonymous_user(self):
        response = self.client.post(self.url)

        redirect_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_post_user_not_subscribed_creates_subscription(self):
        self.assertFalse(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).exists()
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url)

        redirect_url = reverse("author-page", kwargs={"author_id": self.author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertTrue(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).exists()
        )

    def test_post_user_already_subscribed_keeps_subscription(self):
        AuthorSubscription.objects.create(subscriber=self.user, author=self.author)

        self.client.force_login(self.user)
        response = self.client.post(self.url)

        redirect_url = reverse("author-page", kwargs={"author_id": self.author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertEqual(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).count(),
            1,
        )

    def test_post_user_cannot_subscribe_to_self(self):
        target_url = reverse("author-subscribe", kwargs={"author_id": self.user.id})

        self.client.force_login(self.user)
        response = self.client.post(target_url)

        redirect_url = reverse("author-page", kwargs={"author_id": self.user.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertFalse(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.user
            ).exists()
        )


class TestAuthorUnsubscribeView(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.url = reverse("author-unsubscribe", kwargs={"author_id": self.author.id})

    def test_post_anonymous_user(self):
        response = self.client.post(self.url)

        redirect_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_post_user_subscribed_deletes_subscription(self):
        AuthorSubscription.objects.create(subscriber=self.user, author=self.author)

        self.client.force_login(self.user)
        response = self.client.post(self.url)

        redirect_url = reverse("author-page", kwargs={"author_id": self.author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertFalse(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).exists()
        )

    def test_post_user_not_subscribed_keeps_unsubscribed(self):
        self.assertFalse(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).exists()
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url)

        redirect_url = reverse("author-page", kwargs={"author_id": self.author.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertFalse(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.author
            ).exists()
        )

    def test_post_user_cannot_unsubscribe_from_self(self):
        target_url = reverse("author-unsubscribe", kwargs={"author_id": self.user.id})

        self.client.force_login(self.user)
        response = self.client.post(target_url)

        redirect_url = reverse("author-page", kwargs={"author_id": self.user.id})
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertFalse(
            AuthorSubscription.objects.filter(
                subscriber=self.user, author=self.user
            ).exists()
        )
