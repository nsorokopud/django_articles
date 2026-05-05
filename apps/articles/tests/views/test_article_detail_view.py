from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_redis import get_redis_connection

from articles.cache.view_counts import (
    ARTICLE_UNIQUE_VIEW_KEY,
    ARTICLE_UNSYNCED_VIEWS_KEY,
    VIEWED_ARTICLES_SET_KEY,
)
from articles.forms import ArticleCommentForm
from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
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
            content_text="1",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
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

        views_key = ARTICLE_UNSYNCED_VIEWS_KEY.format(id=self.article.id)
        viewed_by_key1 = ARTICLE_UNIQUE_VIEW_KEY.format(
            article_id=self.article.id, viewer_id="user:anonymous"
        )

        self.assertEqual(self.redis_conn.smembers(VIEWED_ARTICLES_SET_KEY), set())
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
        ttl1 = self.redis_conn.ttl(viewed_by_key1)
        self.assertGreater(ttl1, 0)
        self.assertLessEqual(ttl1, ARTICLE_UNIQUE_VIEW_TIMEOUT)

        viewed_by_key2 = ARTICLE_UNIQUE_VIEW_KEY.format(
            article_id=self.article.id, viewer_id="user:test_user"
        )
        self.assertEqual(self.redis_conn.get(viewed_by_key1), b"1")
        self.assertIsNone(self.redis_conn.get(viewed_by_key2))

        self.client.force_login(self.user)
        self.client.get(self.url)
        self.assertEqual(self.redis_conn.get(views_key), b"2")
        self.assertEqual(self.redis_conn.get(viewed_by_key2), b"1")
        ttl2 = self.redis_conn.ttl(viewed_by_key2)
        self.assertGreater(ttl2, 0)
        self.assertLessEqual(ttl2, ARTICLE_UNIQUE_VIEW_TIMEOUT)

        self.client.get(self.url)
        self.assertEqual(self.redis_conn.get(views_key), b"2")

        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 111)

    def test_unpublished_article_returns_404(self):
        unpublished_article = Article.objects.create(
            title="draft",
            slug="draft",
            category=self.category,
            author=self.user,
            preview_text="draft preview",
            content="draft content",
            published_at=None,
            publish_sequence=None,
        )

        url = reverse("article-details", args=[unpublished_article.slug])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_nonexistent_article_returns_404(self):
        response = self.client.get(reverse("article-details", args=["missing-slug"]))
        self.assertEqual(response.status_code, 404)

    def test_authenticated_user_can_post_valid_comment(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url, {"text": "New valid comment"})

        self.assertRedirects(response, self.url)
        self.assertTrue(
            ArticleComment.objects.filter(
                article=self.article,
                author=self.user,
                text="New valid comment",
            ).exists()
        )

    def test_authenticated_user_sees_form_errors_for_invalid_comment(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url, {"text": "x"})

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "articles/article.html")
        self.assertIsInstance(response.context["form"], ArticleCommentForm)
        self.assertTrue(response.context["form"].errors)
        self.assertIn("text", response.context["form"].errors)
        self.assertEqual(ArticleComment.objects.count(), 1)

    def test_authenticated_user_cannot_post_comment_to_unpublished_article(self):
        self.client.force_login(self.user)

        draft = Article.objects.create(
            title="draft",
            slug="draft",
            category=self.category,
            author=self.user,
            preview_text="draft preview",
            content="draft content",
            status=ArticleStatus.DRAFT,
        )

        response = self.client.post(
            reverse("article-details", args=[draft.slug]), {"text": "New valid comment"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(ArticleComment.objects.count(), 1)

    def test_anonymous_user_cannot_post_comment(self):
        response = self.client.post(self.url, {"text": "New comment"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)
        self.assertEqual(ArticleComment.objects.count(), 1)

    @patch("articles.services.comments.ARTICLE_COMMENTS_PER_PAGE", 2)
    def test_shows_only_first_comments_page(self):
        ArticleComment.objects.all().delete()

        comment1 = ArticleComment.objects.create(
            article=self.article,
            author=self.user,
            text="comment 1",
        )
        comment2 = ArticleComment.objects.create(
            article=self.article,
            author=self.user,
            text="comment 2",
        )
        comment3 = ArticleComment.objects.create(
            article=self.article,
            author=self.user,
            text="comment 3",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["comments_count"], 3)
        self.assertEqual(len(response.context["comments"]), 2)
        self.assertContains(response, "Load more comments")
        self.assertContains(
            response, reverse("article-comments-list", args=[self.article.slug])
        )

        visible_comment_ids = [comment.id for comment in response.context["comments"]]

        self.assertIn(comment3.id, visible_comment_ids)
        self.assertIn(comment2.id, visible_comment_ids)
        self.assertNotIn(comment1.id, visible_comment_ids)
