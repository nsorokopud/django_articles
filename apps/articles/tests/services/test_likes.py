from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
from articles.services.likes import (
    set_article_like,
    set_comment_like,
    sync_article_likes_count,
    sync_comment_likes_count,
)
from users.models import User


class TestSetLikeServices(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.other_user = User.objects.create_user(
            username="user1", email="test@test.com"
        )
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")

    def create_published_article(self, *, slug="a1") -> Article:
        return Article.objects.create(
            title=slug,
            slug=slug,
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            content_text="content1",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
        )

    def test_set_article_like(self):
        article = self.create_published_article()

        likes_count, liked = set_article_like(
            article_slug=article.slug, user_id=self.user.id, liked=True
        )

        article.refresh_from_db()
        self.assertEqual(likes_count, 1)
        self.assertTrue(liked)
        self.assertEqual(article.likes_count, 1)
        self.assertEqual(article.users_that_liked.count(), 1)

    def test_set_article_like_is_idempotent(self):
        article = self.create_published_article()

        set_article_like(article_slug=article.slug, user_id=self.user.id, liked=True)
        likes_count, liked = set_article_like(
            article_slug=article.slug,
            user_id=self.user.id,
            liked=True,
        )

        article.refresh_from_db()
        self.assertEqual(likes_count, 1)
        self.assertTrue(liked)
        self.assertEqual(article.likes_count, 1)
        self.assertEqual(article.users_that_liked.count(), 1)

    def test_set_article_unlike(self):
        article = self.create_published_article()

        set_article_like(article_slug=article.slug, user_id=self.user.id, liked=True)

        likes_count, liked = set_article_like(
            article_slug=article.slug,
            user_id=self.user.id,
            liked=False,
        )

        article.refresh_from_db()
        self.assertEqual(likes_count, 0)
        self.assertFalse(liked)
        self.assertEqual(article.likes_count, 0)
        self.assertEqual(article.users_that_liked.count(), 0)

    def test_set_article_unlike_is_idempotent(self):
        article = self.create_published_article()

        likes_count, liked = set_article_like(
            article_slug=article.slug,
            user_id=self.user.id,
            liked=False,
        )

        article.refresh_from_db()
        self.assertEqual(likes_count, 0)
        self.assertFalse(liked)
        self.assertEqual(article.likes_count, 0)
        self.assertEqual(article.users_that_liked.count(), 0)

    def test_multiple_users_can_like_article(self):
        article = self.create_published_article()

        set_article_like(article_slug=article.slug, user_id=self.user.id, liked=True)
        likes_count, liked = set_article_like(
            article_slug=article.slug,
            user_id=self.other_user.id,
            liked=True,
        )

        article.refresh_from_db()
        self.assertEqual(likes_count, 2)
        self.assertTrue(liked)
        self.assertEqual(article.likes_count, 2)
        self.assertEqual(article.users_that_liked.count(), 2)

    def test_cannot_like_unpublished_article(self):
        article = Article.objects.create(
            title="draft",
            slug="draft",
            category=self.category,
            author=self.user,
            preview_text="text",
            content="content",
            status=ArticleStatus.DRAFT,
        )

        with self.assertRaises(Http404):
            set_article_like(
                article_slug=article.slug,
                user_id=self.user.id,
                liked=True,
            )

        article.refresh_from_db()
        self.assertEqual(article.likes_count, 0)
        self.assertEqual(article.users_that_liked.count(), 0)

    def test_set_comment_like(self):
        article = self.create_published_article()
        comment = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="text",
        )

        likes_count, liked = set_comment_like(
            comment_id=comment.id,
            user_id=self.user.id,
            liked=True,
        )

        comment.refresh_from_db()
        self.assertEqual(likes_count, 1)
        self.assertTrue(liked)
        self.assertEqual(comment.likes_count, 1)
        self.assertEqual(comment.users_that_liked.count(), 1)

    def test_set_comment_like_is_idempotent(self):
        article = self.create_published_article()
        comment = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="text",
        )

        set_comment_like(comment_id=comment.id, user_id=self.user.id, liked=True)
        likes_count, liked = set_comment_like(
            comment_id=comment.id,
            user_id=self.user.id,
            liked=True,
        )

        comment.refresh_from_db()
        self.assertEqual(likes_count, 1)
        self.assertTrue(liked)
        self.assertEqual(comment.likes_count, 1)
        self.assertEqual(comment.users_that_liked.count(), 1)

    def test_set_comment_unlike(self):
        article = self.create_published_article()
        comment = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="text",
        )

        set_comment_like(comment_id=comment.id, user_id=self.user.id, liked=True)

        likes_count, liked = set_comment_like(
            comment_id=comment.id,
            user_id=self.user.id,
            liked=False,
        )

        comment.refresh_from_db()
        self.assertEqual(likes_count, 0)
        self.assertFalse(liked)
        self.assertEqual(comment.likes_count, 0)
        self.assertEqual(comment.users_that_liked.count(), 0)

    def test_set_comment_unlike_is_idempotent(self):
        article = self.create_published_article()
        comment = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="text",
        )

        likes_count, liked = set_comment_like(
            comment_id=comment.id,
            user_id=self.user.id,
            liked=False,
        )

        comment.refresh_from_db()
        self.assertEqual(likes_count, 0)
        self.assertFalse(liked)
        self.assertEqual(comment.likes_count, 0)
        self.assertEqual(comment.users_that_liked.count(), 0)

    def test_multiple_users_can_like_comment(self):
        article = self.create_published_article()
        comment = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="text",
        )

        set_comment_like(comment_id=comment.id, user_id=self.user.id, liked=True)
        likes_count, liked = set_comment_like(
            comment_id=comment.id,
            user_id=self.other_user.id,
            liked=True,
        )

        comment.refresh_from_db()
        self.assertEqual(likes_count, 2)
        self.assertTrue(liked)
        self.assertEqual(comment.likes_count, 2)
        self.assertEqual(comment.users_that_liked.count(), 2)

    def test_cannot_like_comment_on_unpublished_article(self):
        article = Article.objects.create(
            title="draft",
            slug="draft",
            category=self.category,
            author=self.user,
            preview_text="text",
            content="content",
            status=ArticleStatus.DRAFT,
        )
        comment = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="comment",
        )

        with self.assertRaises(Http404):
            set_comment_like(
                comment_id=comment.id,
                user_id=self.user.id,
                liked=True,
            )

        comment.refresh_from_db()
        self.assertEqual(comment.likes_count, 0)
        self.assertEqual(comment.users_that_liked.count(), 0)


class TestSyncLikeCountServices(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.other_user = User.objects.create_user(
            username="user1", email="test@test.com"
        )
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")

    def create_published_article(self, *, slug="a1") -> Article:
        return Article.objects.create(
            title=slug,
            slug=slug,
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            content_text="content1",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
        )

    def test_sync_article_likes_count_repairs_stale_count(self):
        article = self.create_published_article()

        article.users_that_liked.add(self.user, self.other_user)
        Article.objects.filter(pk=article.pk).update(likes_count=0)

        sync_article_likes_count()

        article.refresh_from_db()
        self.assertEqual(article.likes_count, 2)

    def test_sync_article_likes_count_resets_zero_likes(self):
        article = self.create_published_article()
        Article.objects.filter(pk=article.pk).update(likes_count=5)

        sync_article_likes_count()

        article.refresh_from_db()
        self.assertEqual(article.likes_count, 0)

    def test_sync_article_likes_count_handles_multiple_batches(self):
        article_1 = self.create_published_article(slug="a1")
        article_2 = self.create_published_article(slug="a2")
        article_3 = self.create_published_article(slug="a3")

        article_1.users_that_liked.add(self.user)
        article_2.users_that_liked.add(self.user, self.other_user)
        Article.objects.filter(
            pk__in=[article_1.pk, article_2.pk, article_3.pk]
        ).update(
            likes_count=99,
        )

        sync_article_likes_count(batch_size=2)

        article_1.refresh_from_db()
        article_2.refresh_from_db()
        article_3.refresh_from_db()

        self.assertEqual(article_1.likes_count, 1)
        self.assertEqual(article_2.likes_count, 2)
        self.assertEqual(article_3.likes_count, 0)

    def test_sync_comment_likes_count_repairs_stale_count(self):
        article = self.create_published_article()
        comment = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="comment",
        )

        comment.users_that_liked.add(self.user, self.other_user)
        ArticleComment.objects.filter(pk=comment.pk).update(likes_count=0)

        sync_comment_likes_count()

        comment.refresh_from_db()
        self.assertEqual(comment.likes_count, 2)

    def test_sync_comment_likes_count_resets_zero_likes(self):
        article = self.create_published_article()
        comment = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="comment",
        )

        ArticleComment.objects.filter(pk=comment.pk).update(likes_count=5)

        sync_comment_likes_count()

        comment.refresh_from_db()
        self.assertEqual(comment.likes_count, 0)

    def test_sync_comment_likes_count_handles_multiple_batches(self):
        article = self.create_published_article()
        comment_1 = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="comment 1",
        )
        comment_2 = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="comment 2",
        )
        comment_3 = ArticleComment.objects.create(
            article=article,
            author=self.user,
            text="comment 3",
        )

        comment_1.users_that_liked.add(self.user)
        comment_2.users_that_liked.add(self.user, self.other_user)
        ArticleComment.objects.filter(
            pk__in=[comment_1.pk, comment_2.pk, comment_3.pk]
        ).update(likes_count=99)

        sync_comment_likes_count(batch_size=2)

        comment_1.refresh_from_db()
        comment_2.refresh_from_db()
        comment_3.refresh_from_db()

        self.assertEqual(comment_1.likes_count, 1)
        self.assertEqual(comment_2.likes_count, 2)
        self.assertEqual(comment_3.likes_count, 0)
