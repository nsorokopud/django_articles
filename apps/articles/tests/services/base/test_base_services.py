from django.test import TestCase
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
from articles.services import toggle_article_like, toggle_comment_like
from users.models import User


class TestServices(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")

    def test_toggle_article_like(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
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
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
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
