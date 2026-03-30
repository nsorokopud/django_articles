from datetime import datetime
from unittest.mock import Mock, patch

from django.test import TestCase

from articles.models import Article, ArticleCategory, ArticleStatus
from articles.services.articles import save_article
from users.models import User


class TestSaveArticle(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@test.com",
        )
        self.category = ArticleCategory.objects.create(
            title="cat",
            slug="cat",
        )

    @patch("articles.services.articles.publish_article")
    def test_creates_article_unpublished_by_default(self, mock_publish_article):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        save_m2m = Mock()

        saved = save_article(
            article=article,
            author=self.author,
            save_m2m=save_m2m,
        )

        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.author, self.author)
        self.assertIsNone(saved.published_at)
        self.assertIsNone(saved.publish_sequence)

        save_m2m.assert_called_once_with()
        mock_publish_article.assert_not_called()

    @patch("articles.services.articles.publish_article")
    def test_creates_article_assigns_author_and_publishes_when_publish_true(
        self,
        mock_publish_article,
    ):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        mock_publish_article.side_effect = lambda *, article_id: Article.objects.get(
            id=article_id
        )

        save_m2m = Mock()

        saved = save_article(
            article=article,
            author=self.author,
            save_m2m=save_m2m,
            publish=True,
        )

        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.author, self.author)
        self.assertEqual(saved.title, "a1")
        self.assertEqual(saved.slug, "a1")
        self.assertEqual(saved.category, self.category)
        self.assertEqual(saved.preview_text, "preview")
        self.assertEqual(saved.content, "content")

        db_article = Article.objects.get(id=saved.id)
        self.assertEqual(db_article.author, self.author)

        save_m2m.assert_called_once_with()
        mock_publish_article.assert_called_once_with(article_id=saved.id)

    def test_creates_article_without_publishing_when_publish_false(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        save_m2m = Mock()

        saved = save_article(
            article=article,
            author=self.author,
            save_m2m=save_m2m,
            publish=False,
        )

        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.author, self.author)
        self.assertIsNone(saved.published_at)
        self.assertIsNone(saved.publish_sequence)

        db_article = Article.objects.get(id=saved.id)
        self.assertEqual(db_article.author, self.author)
        self.assertIsNone(db_article.published_at)
        self.assertIsNone(db_article.publish_sequence)

        save_m2m.assert_called_once_with()

    @patch("articles.services.articles.publish_article")
    def test_updates_existing_article_without_replacing_author(
        self,
        mock_publish_article,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
        )
        article.title = "updated"
        article.preview_text = "updated preview"

        save_m2m = Mock()

        saved = save_article(
            article=article,
            author=self.other_user,
            save_m2m=save_m2m,
            publish=False,
        )

        self.assertEqual(saved.pk, article.pk)
        self.assertEqual(saved.author, self.author)
        self.assertEqual(saved.title, "updated")
        self.assertEqual(saved.preview_text, "updated preview")

        article.refresh_from_db()
        self.assertEqual(article.author, self.author)
        self.assertEqual(article.title, "updated")
        self.assertEqual(article.preview_text, "updated preview")

        save_m2m.assert_called_once_with()
        mock_publish_article.assert_not_called()

    def test_raises_when_creating_article_without_author(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        save_m2m = Mock()

        with self.assertRaises(ValueError):
            save_article(
                article=article,
                save_m2m=save_m2m,
                publish=False,
            )

        self.assertEqual(Article.objects.count(), 0)
        save_m2m.assert_not_called()

    @patch("articles.services.articles.publish_article")
    def test_calls_publish_service_for_already_published_article_when_publish_true(
        self,
        mock_publish_article,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.PUBLISHED,
            publish_sequence=123,
            published_at=datetime(2026, 1, 1),
        )

        mock_publish_article.return_value = article
        save_m2m = Mock()

        saved = save_article(
            article=article,
            save_m2m=save_m2m,
            publish=True,
        )

        self.assertEqual(saved.pk, article.pk)
        save_m2m.assert_called_once_with()
        mock_publish_article.assert_called_once_with(article_id=article.id)

    @patch("articles.services.articles.publish_article")
    def test_publishes_existing_unpublished_article_when_publish_true(
        self,
        mock_publish_article,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
        )

        mock_publish_article.side_effect = lambda *, article_id: Article.objects.get(
            id=article_id
        )
        save_m2m = Mock()

        saved = save_article(
            article=article,
            save_m2m=save_m2m,
            publish=True,
        )

        self.assertEqual(saved.pk, article.pk)
        save_m2m.assert_called_once_with()
        mock_publish_article.assert_called_once_with(article_id=article.id)

    @patch("articles.services.articles.restore_article_to_draft")
    @patch("articles.services.articles.publish_article")
    def test_updates_rejected_article_restores_to_draft_when_publish_false(
        self,
        mock_publish_article,
        mock_restore_article_to_draft,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.REJECTED,
            review_note="Needs work",
        )
        article.title = "updated"

        mock_restore_article_to_draft.side_effect = (
            lambda *, article_id: Article.objects.get(id=article_id)
        )

        save_m2m = Mock()

        saved = save_article(
            article=article,
            save_m2m=save_m2m,
            publish=False,
        )

        article.refresh_from_db()
        self.assertEqual(article.title, "updated")
        self.assertEqual(saved.pk, article.pk)
        save_m2m.assert_called_once_with()
        mock_restore_article_to_draft.assert_called_once_with(article_id=article.id)
        mock_publish_article.assert_not_called()

    @patch("articles.services.articles.restore_article_to_draft")
    @patch("articles.services.articles.publish_article")
    def test_rejected_article_with_publish_true_does_not_restore_to_draft(
        self,
        mock_publish_article,
        mock_restore_article_to_draft,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.REJECTED,
            review_note="Needs work",
        )

        mock_publish_article.side_effect = ValueError(
            "only draft articles can be published"
        )
        save_m2m = Mock()

        with self.assertRaises(ValueError):
            save_article(
                article=article,
                save_m2m=save_m2m,
                publish=True,
            )

        save_m2m.assert_called_once_with()
        mock_restore_article_to_draft.assert_not_called()
        mock_publish_article.assert_called_once_with(article_id=article.id)

    @patch("articles.services.articles.restore_article_to_draft")
    def test_existing_draft_does_not_restore_to_draft_again(
        self, mock_restore_article_to_draft
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.DRAFT,
        )
        article.title = "updated"

        save_m2m = Mock()

        saved = save_article(
            article=article,
            save_m2m=save_m2m,
            publish=False,
        )

        self.assertEqual(saved.pk, article.pk)
        save_m2m.assert_called_once_with()
        mock_restore_article_to_draft.assert_not_called()

    def test_saves_article_when_save_m2m_is_none(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )

        saved = save_article(
            article=article,
            author=self.author,
            save_m2m=None,
            publish=False,
        )

        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.author, self.author)
        self.assertEqual(Article.objects.count(), 1)
