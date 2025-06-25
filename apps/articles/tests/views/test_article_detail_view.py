from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django_redis import get_redis_connection

from articles.cache import (
    ARTICLE_VIEWED_BY_KEY,
    ARTICLE_VIEWS_KEY,
    VIEWED_ARTICLES_SET_KEY,
)
from articles.forms import ArticleCommentForm
from articles.models import Article, ArticleCategory, ArticleComment
from articles.settings import (
    ARTICLE_DETAILS_PAGE_CACHE_TIMEOUT,
    ARTICLE_UNIQUE_VIEW_TIMEOUT,
)
from config.settings import CACHES
from users.models import User


@override_settings(CACHES=CACHES)
class TestArticleDetailView(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.redis_conn = get_redis_connection("default")

    @classmethod
    def tearDownClass(cls):
        cls.redis_conn.flushdb()
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        self.redis_conn.flushdb()

        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.user,
            preview_text="1",
            content="1",
            is_published=True,
        )
        self.comment = ArticleComment.objects.create(
            author=self.user, article=self.article, text="comment"
        )
        self.url = reverse("article-details", args=[self.article.slug])

    def test_context_data_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article.html")
        self.assertEqual(response.context["article"], self.article)
        self.assertEqual(response.context["comments_count"], 1)
        self.assertCountEqual(response.context["comments"], [self.comment])
        self.assertFalse(response.context["user_liked"])
        self.assertIsNone(response.context.get("form"))
        self.assertIsNone(response.context.get("liked_comments"))

    def test_context_data_authenticated(self):
        self.article.users_that_liked.add(self.user)
        self.comment.users_that_liked.add(self.user)

        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article.html")
        self.assertEqual(response.context["article"], self.article)
        self.assertEqual(response.context["comments_count"], 1)
        self.assertCountEqual(response.context["comments"], [self.comment])
        self.assertTrue(response.context["user_liked"])
        self.assertIsInstance(response.context.get("form"), ArticleCommentForm)
        self.assertCountEqual(response.context.get("liked_comments"), [self.comment.id])

    def test_cached_for_anonymous_user(self):
        query_string = "*:views.decorators.cache.cache_page*"
        self.assertEqual(self.redis_conn.keys(query_string), [])

        response1 = self.client.get(self.url)
        keys = self.redis_conn.keys(query_string)
        self.assertEqual(len(keys), 1)
        self.assertEqual(
            self.redis_conn.ttl(keys[0]), ARTICLE_DETAILS_PAGE_CACHE_TIMEOUT
        )
        self.assertTemplateUsed(response1, "articles/article.html")

        response2 = self.client.get(self.url)
        self.assertEqual(response1.content, response2.content)
        self.assertTemplateNotUsed(response2, "articles/article.html")

    def test_not_cached_for_authenticated_user(self):
        query_string = "*:views.decorators.cache.cache_page*"
        self.assertEqual(self.redis_conn.keys(query_string), [])
        self.client.force_login(self.user)

        response1 = self.client.get(self.url)
        self.assertEqual(self.redis_conn.keys(query_string), [])
        response2 = self.client.get(self.url)
        self.assertEqual(self.redis_conn.keys(query_string), [])
        self.assertNotEqual(response1.content, response2.content)
        self.assertTemplateUsed(response1, "articles/article.html")
        self.assertTemplateUsed(response2, "articles/article.html")

    @patch("articles.views.decorators.get_visitor_id")
    def test_cached_views_increment(self, mock_get_id):
        mock_get_id.side_effect = lambda request: (
            "user:test_user" if request.user.is_authenticated else "user:anonymous"
        )

        self.article.views_count = 111
        self.article.save(update_fields=["views_count"])

        views_key = ARTICLE_VIEWS_KEY.format(id=self.article.id)
        viewed_by_key1 = ARTICLE_VIEWED_BY_KEY.format(
            article_id=self.article.id, viewer_id="user:anonymous"
        )

        self.assertIsNone(self.redis_conn.get(VIEWED_ARTICLES_SET_KEY))
        self.assertIsNone(self.redis_conn.get(views_key))
        self.assertIsNone(self.redis_conn.get(viewed_by_key1))

        self.client.get(self.url)
        self.assertEqual(self.redis_conn.get(views_key), b"1")
        self.assertCountEqual(
            self.redis_conn.smembers(VIEWED_ARTICLES_SET_KEY),
            [str(self.article.id).encode()],
        )

        self.client.get(self.url)
        self.assertEqual(self.redis_conn.get(views_key), b"1")
        self.assertEqual(self.redis_conn.get(viewed_by_key1), b"1")
        self.assertEqual(
            self.redis_conn.ttl(viewed_by_key1), ARTICLE_UNIQUE_VIEW_TIMEOUT
        )

        viewed_by_key2 = ARTICLE_VIEWED_BY_KEY.format(
            article_id=self.article.id, viewer_id="user:test_user"
        )
        self.assertEqual(self.redis_conn.get(viewed_by_key1), b"1")
        self.assertIsNone(self.redis_conn.get(viewed_by_key2))

        self.client.force_login(self.user)
        self.client.get(self.url)
        self.assertEqual(self.redis_conn.get(views_key), b"2")
        self.assertEqual(self.redis_conn.get(viewed_by_key2), b"1")
        self.assertEqual(
            self.redis_conn.ttl(viewed_by_key2), ARTICLE_UNIQUE_VIEW_TIMEOUT
        )

        self.client.get(self.url)
        self.assertEqual(self.redis_conn.get(views_key), b"2")

        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 111)
