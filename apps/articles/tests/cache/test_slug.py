from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from articles.cache.slug import (
    ARTICLE_SLUG_ID_CACHE_KEY,
    cache_article_slug_id,
    get_cached_article_id_by_slug,
    invalidate_article_slug_id,
)
from articles.models import Article, ArticleStatus
from users.models import User


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-article-slug-cache",
        }
    }
)
class TestGetCachedArticleIdBySlug(TestCase):
    def setUp(self):
        cache.clear()
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )

    def tearDown(self):
        cache.clear()

    def _create_article(self, *, slug="test-article", status=ArticleStatus.PUBLISHED):
        article = Article(
            title="Test Article",
            slug=slug,
            author=self.author,
            preview_text="Preview text",
            content="<p>Content</p>",
            content_text="Content",
            status=status,
        )
        if status == ArticleStatus.PUBLISHED:
            article.published_at = timezone.now()

        article.save()
        return article

    def test_get_cached_article_id_by_slug_returns_published_article_id(self):
        article = self._create_article(slug="published-article")

        result = get_cached_article_id_by_slug("published-article")
        self.assertEqual(result, article.id)

    def test_get_cached_article_id_by_slug_stores_article_id_in_cache(self):
        article = self._create_article(slug="cached-article")
        cache_key = ARTICLE_SLUG_ID_CACHE_KEY.format(slug="cached-article")

        self.assertIsNone(cache.get(cache_key))

        result = get_cached_article_id_by_slug("cached-article")

        self.assertEqual(result, article.id)
        self.assertEqual(cache.get(cache_key), article.id)

    def test_get_cached_article_id_by_slug_uses_cached_value_without_db_query(self):
        article = self._create_article(slug="cached-only")
        cache_key = ARTICLE_SLUG_ID_CACHE_KEY.format(slug="cached-only")
        cache.set(cache_key, article.id)

        with self.assertNumQueries(0):
            result = get_cached_article_id_by_slug("cached-only")

        self.assertEqual(result, article.id)

    def test_get_cached_article_id_by_slug_returns_none_for_missing_article(self):
        result = get_cached_article_id_by_slug("missing-article")
        self.assertIsNone(result)

    def test_get_cached_article_id_by_slug_does_not_cache_missing_article(self):
        cache_key = ARTICLE_SLUG_ID_CACHE_KEY.format(slug="missing-article")

        result = get_cached_article_id_by_slug("missing-article")
        self.assertIsNone(result)
        self.assertIsNone(cache.get(cache_key))

    def test_get_cached_article_id_by_slug_ignores_draft_article(self):
        self._create_article(slug="draft-article", status=ArticleStatus.DRAFT)

        result = get_cached_article_id_by_slug("draft-article")
        self.assertIsNone(result)

    def test_get_cached_article_id_by_slug_ignores_pending_review_article(self):
        self._create_article(
            slug="pending-article", status=ArticleStatus.PENDING_REVIEW
        )

        result = get_cached_article_id_by_slug("pending-article")
        self.assertIsNone(result)

    def test_get_cached_article_id_by_slug_ignores_rejected_article(self):
        self._create_article(slug="rejected-article", status=ArticleStatus.REJECTED)

        result = get_cached_article_id_by_slug("rejected-article")
        self.assertIsNone(result)

    def test_deletes_invalid_cached_value_and_queries_db(self):
        article = self._create_article(slug="bad-cache")
        cache_key = ARTICLE_SLUG_ID_CACHE_KEY.format(slug="bad-cache")
        cache.set(cache_key, "not-an-int")

        result = get_cached_article_id_by_slug("bad-cache")
        self.assertEqual(result, article.id)
        self.assertEqual(cache.get(cache_key), article.id)

    def test_deletes_invalid_cached_value_when_article_missing(self):
        cache_key = ARTICLE_SLUG_ID_CACHE_KEY.format(slug="missing-bad-cache")
        cache.set(cache_key, "not-an-int")

        result = get_cached_article_id_by_slug("missing-bad-cache")
        self.assertIsNone(result)
        self.assertIsNone(cache.get(cache_key))


class TestArticleSlugCache(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_article_slug_id_sets_cache_value(self):
        cache_article_slug_id(article_slug="a", article_id=123)

        cache_key = ARTICLE_SLUG_ID_CACHE_KEY.format(slug="a")
        self.assertEqual(cache.get(cache_key), 123)

    def test_invalidate_article_slug_id_deletes_cache_value(self):
        cache_key = ARTICLE_SLUG_ID_CACHE_KEY.format(slug="a")
        cache.set(cache_key, 123)

        invalidate_article_slug_id(article_slug="a")
        self.assertIsNone(cache.get(cache_key))
