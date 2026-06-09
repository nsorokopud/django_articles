from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleStatus
from articles.services.articles import delete_article
from users.models import User


class TestDeleteArticle(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.category = ArticleCategory.objects.create(
            title="Category", slug="category"
        )

    def _article(self, **overrides):
        data = {
            "title": "Test article",
            "slug": "test-article",
            "category": self.category,
            "author": self.author,
            "preview_text": "Preview text",
            "content": "<p>Article body</p>",
            "content_text": "Article body",
            "status": ArticleStatus.DRAFT,
        }
        data.update(overrides)
        return Article.objects.create(**data)

    def test_deletes_draft_article(self):
        article = self._article(status=ArticleStatus.DRAFT)

        delete_article(article_id=article.id)

        self.assertFalse(Article.objects.filter(pk=article.pk).exists())

    def test_deletes_rejected_article(self):
        article = self._article(
            status=ArticleStatus.REJECTED,
            review_note="Needs work",
            reviewed_at=timezone.now(),
            reviewed_by=self.author,
        )

        delete_article(article_id=article.id)

        self.assertFalse(Article.objects.filter(pk=article.pk).exists())

    def test_rejects_published_article(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        with self.assertRaisesMessage(
            ValueError, "published or pending-review articles cannot be deleted"
        ):
            delete_article(article_id=article.id)

        self.assertTrue(Article.objects.filter(pk=article.pk).exists())

    def test_rejects_pending_review_article(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)

        with self.assertRaisesMessage(
            ValueError, "published or pending-review articles cannot be deleted"
        ):
            delete_article(article_id=article.id)

        self.assertTrue(Article.objects.filter(pk=article.pk).exists())

    @patch("articles.tasks.delete_article_media_task.delay")
    @patch("articles.services.articles.invalidate_article_slug_id")
    def test_after_commit_invalidates_slug_cache_and_schedules_media_cleanup(
        self, mock_invalidate, mock_delete_media_task
    ):
        article = self._article(slug="cached-slug")
        article_id = article.id
        author_id = article.author_id
        preview_image_name = article.preview_image.name

        with self.captureOnCommitCallbacks(execute=True):
            delete_article(article_id=article_id)

        mock_invalidate.assert_called_once_with(article_slug="cached-slug")
        mock_delete_media_task.assert_called_once_with(
            article_id=article_id,
            author_id=author_id,
            preview_image_name=preview_image_name,
        )

    @patch("articles.tasks.delete_article_media_task.delay")
    def test_does_not_schedule_media_cleanup_when_delete_rejected(
        self, mock_delete_media_task
    ):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        with self.assertRaisesMessage(
            ValueError, "published or pending-review articles cannot be deleted"
        ):
            delete_article(article_id=article.id)

        mock_delete_media_task.assert_not_called()
