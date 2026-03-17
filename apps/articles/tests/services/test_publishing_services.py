from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from articles.models import Article, ArticleStatus
from articles.services.publishing import (
    get_next_article_publish_sequence_value,
    publish_article,
)
from users.models import User


class TestPublishArticle(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
            latest_article_publish_sequence=0,
        )
        self.article = Article.objects.create(
            author=self.author,
            title="a",
            content="c",
        )

    def test_sets_published_fields_and_updates_author_sequence(self):
        before = timezone.now()

        published = publish_article(article_id=self.article.id)

        after = timezone.now()

        self.article.refresh_from_db()
        self.author.refresh_from_db()

        self.assertEqual(published.id, self.article.id)
        self.assertIsNotNone(self.article.published_at)
        self.assertIsNotNone(self.article.publish_sequence)
        self.assertGreaterEqual(self.article.published_at, before)
        self.assertLessEqual(self.article.published_at, after)
        self.assertEqual(
            self.author.latest_article_publish_sequence,
            self.article.publish_sequence,
        )

    @patch("articles.services.publishing.get_next_article_publish_sequence_value")
    @patch("articles.services.publishing.advance_latest_article_publish_sequence")
    def test_returns_already_published_article_without_changing_it(
        self, mock_advance, mock_get_next
    ):
        published_at = timezone.now()
        self.article.status = ArticleStatus.PUBLISHED
        self.article.published_at = published_at
        self.article.publish_sequence = 123
        self.article.save(update_fields=["status", "published_at", "publish_sequence"])

        self.author.latest_article_publish_sequence = 123
        self.author.save(update_fields=["latest_article_publish_sequence"])

        result = publish_article(article_id=self.article.id)

        self.article.refresh_from_db()
        self.author.refresh_from_db()

        self.assertEqual(result.id, self.article.id)
        self.assertEqual(self.article.publish_sequence, 123)
        self.assertEqual(self.article.published_at, published_at)
        self.assertEqual(self.author.latest_article_publish_sequence, 123)
        mock_get_next.assert_not_called()
        mock_advance.assert_not_called()

    @patch("articles.services.publishing.advance_latest_article_publish_sequence")
    @patch("articles.services.publishing.get_next_article_publish_sequence_value")
    def test_calls_advance_with_author_id_and_sequence(
        self,
        mock_get_next,
        mock_advance,
    ):
        mock_get_next.return_value = 777

        publish_article(article_id=self.article.id)

        mock_advance.assert_called_once_with(
            user_id=self.author.id,
            publish_sequence=777,
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.publish_sequence, 777)
        self.assertIsNotNone(self.article.published_at)

    def test_raises_for_missing_article(self):
        with self.assertRaises(Article.DoesNotExist):
            publish_article(article_id=999999)


class TestGetNextArticlePublishSequenceValue(TestCase):
    def test_returns_int(self):
        value = get_next_article_publish_sequence_value()

        self.assertIsInstance(value, int)

    def test_returns_increasing_values(self):
        first = get_next_article_publish_sequence_value()
        second = get_next_article_publish_sequence_value()

        self.assertGreater(second, first)
