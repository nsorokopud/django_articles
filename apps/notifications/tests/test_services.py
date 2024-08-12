from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from articles.models import Article
from ..models import Notification
from ..services import create_new_article_notification


class TestServices(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author")
        self.user = User.objects.create_user(username="user")
        self.a = Article(
            title="a",
            slug="a",
            author=self.author,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

    def test_create_new_article_notification(self):
        notifications_count = Notification.objects.count()
        self.assertEqual(notifications_count, 0)

        create_new_article_notification(self.a, self.user)

        notifications_count = Notification.objects.count()
        self.assertEqual(notifications_count, 1)

        n = Notification.objects.get(sender=self.author, recipient=self.user)
        self.assertEqual(n.type, Notification.Type.NEW_ARTICLE)
        self.assertEqual(n.status, Notification.Status.UNREAD)
        self.assertEqual(n.title, "New Article")
        self.assertEqual(n.message, f"New article from {self.author.username}: '{self.a.title}'")
        self.assertEqual(n.link, reverse("article-details", args=(self.a.slug,)))
