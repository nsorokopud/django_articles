from unittest.mock import patch

from django.test import TestCase

from articles.models import Article, ArticleCategory, ArticleComment
from articles.services import (
    generate_unique_article_slug,
    toggle_article_like,
    toggle_comment_like,
)
from users.models import User


class TestServices(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")

    @patch("articles.services.base.generate", return_value="suffix")
    def test_generate_unique_article_slug(self, mock_generate):
        self.assertEqual(generate_unique_article_slug("abc"), "abc")

        Article.objects.create(
            title="abc",
            slug="abc",
            author=self.user,
            preview_text="1",
            content="1",
        )

        self.assertEqual(generate_unique_article_slug("abc"), "abc-suffix")
        self.assertEqual(generate_unique_article_slug("abc "), "abc-suffix")
        self.assertEqual(generate_unique_article_slug("abc-"), "abc-suffix")
        self.assertEqual(generate_unique_article_slug("abc -"), "abc-suffix")
        self.assertEqual(generate_unique_article_slug("non-existent"), "non-existent")

    def test_toggle_article_like(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

        user = User(username="user1", email="test@test.com")
        user.set_password("12345")
        user.save()

        likes_count = toggle_article_like(a.slug, self.user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_article_like(a.slug, self.user.id)
        self.assertEqual(likes_count, 0)

        likes_count = toggle_article_like(a.slug, self.user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_article_like(a.slug, user.id)
        self.assertEqual(likes_count, 2)
        likes_count = toggle_article_like(a.slug, self.user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_article_like(a.slug, user.id)
        self.assertEqual(likes_count, 0)

    def test_toggle_comment_like(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        comment = ArticleComment.objects.create(
            article=a, author=self.user, text="text"
        )

        user = User(username="user1", email="test@test.com")
        user.set_password("12345")
        user.save()

        likes_count = toggle_comment_like(comment.id, self.user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_comment_like(comment.id, self.user.id)
        self.assertEqual(likes_count, 0)

        likes_count = toggle_comment_like(comment.id, self.user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_comment_like(comment.id, user.id)
        self.assertEqual(likes_count, 2)
        likes_count = toggle_comment_like(comment.id, self.user.id)
        self.assertEqual(likes_count, 1)
        likes_count = toggle_comment_like(comment.id, user.id)
        self.assertEqual(likes_count, 0)
