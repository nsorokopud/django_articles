from unittest.mock import patch

from django.test import TestCase

from articles.models import Article, ArticleCategory, ArticleComment
from articles.services import (
    create_article,
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

    def test_create_article(self):
        a1 = create_article(
            title="a1",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            tags=["tag1", "tag2"],
        )

        # articles are sorted by '-created_at' by default, so the last one created will
        # be the first one in queryset
        last_article = Article.objects.first()

        self.assertEqual(last_article.pk, a1.pk)
        self.assertEqual(last_article.slug, "a1")
        self.assertEqual(last_article.author.username, "user")

        expected_tags = ["tag1", "tag2"]
        actual_tags = [tag.name for tag in last_article.tags.all()]
        self.assertCountEqual(actual_tags, expected_tags)

    def test_create_article_with_same_title(self):
        a1 = create_article(
            title="a1",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            tags=["tag1", "tag2"],
        )

        a2 = create_article(
            title="a2",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
        )

        self.assertEqual(a1.slug, "a1")
        self.assertEqual(a2.slug, "a2")

        a3 = create_article(
            title="a1",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            tags=["tag1", "tag2"],
        )

        self.assertEqual(Article.objects.count(), 3)
        self.assertEqual(a1.title, a3.title)
        self.assertNotEqual(a1.pk, a3.pk)
        self.assertNotEqual(a1.slug, a3.slug)

    def test_create_article_tags_creation(self):
        a1 = create_article(
            title="a1",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            tags=["tag1", "tag2"],
        )

        a1_actual_tags = [t.name for t in a1.tags.all()]
        self.assertCountEqual(a1_actual_tags, ["tag1", "tag2"])

        a2 = create_article(
            title="a2",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
        )

        a2_actual_tags = [t.name for t in a2.tags.all()]
        self.assertCountEqual(a2_actual_tags, [])

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
