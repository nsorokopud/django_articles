from django.contrib.auth.models import User
from django.test import TestCase

from articles.models import Article


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
