from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from articles.models import Article, ArticleStatus
from articles.settings import ARTICLES_PER_PAGE_COUNT
from users.models import User


class TestMyArticlesListView(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.redis_patch = patch(
            "articles.cache.view_counts.get_cached_article_views", return_value=0
        )
        cls.redis_patch.start()
        cls.addClassCleanup(cls.redis_patch.stop)

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="author1", email="author1@test.com"
        )
        cls.other_user = User.objects.create_user(
            username="author2", email="author2@test.com"
        )

    def test_login_required(self):
        response = self.client.get(reverse("my-articles"))

        login_url = reverse("login")
        expected_redirect = f"{login_url}?next={reverse('my-articles')}"
        self.assertRedirects(response, expected_redirect)

    def test_shows_only_articles_of_logged_in_user(self):
        own_article_1 = Article.objects.create(
            title="Draft",
            slug="draft",
            author=self.user,
            preview_text="p",
            content="c",
            status=ArticleStatus.DRAFT,
        )
        own_article_2 = Article.objects.create(
            title="Rejected",
            slug="rejected",
            author=self.user,
            preview_text="p",
            content="c",
            status=ArticleStatus.REJECTED,
        )
        other_article = Article.objects.create(
            title="Other",
            slug="other",
            author=self.other_user,
            preview_text="p",
            content="c",
            status=ArticleStatus.DRAFT,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("my-articles"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_article_1.title)
        self.assertContains(response, own_article_2.title)
        self.assertNotContains(response, other_article.title)

        articles = list(response.context["articles"])
        self.assertIn(own_article_1, articles)
        self.assertIn(own_article_2, articles)
        self.assertNotIn(other_article, articles)

    def test_uses_expected_template(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("my-articles"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_list_page.html")

    def test_context_contains_expected_values(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("my-articles"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_title"], "Your articles")
        self.assertEqual(
            response.context["empty_message"],
            "You have not created any articles yet",
        )
        self.assertFalse(response.context["show_filters"])
        self.assertEqual(response.context["reset_url"], reverse("my-articles"))
        self.assertEqual(
            response.context["category_filter_url"], reverse("my-articles")
        )
        self.assertEqual(response.context["tag_filter_url"], reverse("my-articles"))
        self.assertTrue(response.context["show_views"])
        self.assertTrue(response.context["show_likes"])
        self.assertTrue(response.context["show_comments"])
        self.assertEqual(response.context["draft_edit_url_name"], "article-update")
        self.assertEqual(response.context["page_key"], "my-articles")
        self.assertFalse(response.context["is_subscriptions_feed_page_one"])
        self.assertEqual(response.context["latest_article_publish_sequence"], 0)

    def test_empty_articles_list(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("my-articles"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["articles"])
        self.assertContains(response, "You have not created any articles yet")

    def test_paginates_articles(self):
        for i in range(ARTICLES_PER_PAGE_COUNT + 1):
            Article.objects.create(
                title=f"Article {i}",
                slug=f"article-{i}",
                author=self.user,
                preview_text=f"Preview {i}",
                content=f"Content {i}",
                status=ArticleStatus.DRAFT,
            )

        self.client.force_login(self.user)

        response_page_1 = self.client.get(reverse("my-articles"))
        response_page_2 = self.client.get(reverse("my-articles"), {"page": 2})

        self.assertEqual(response_page_1.context["page_obj"].number, 1)
        self.assertEqual(response_page_2.context["page_obj"].number, 2)
        self.assertEqual(response_page_1.status_code, 200)
        self.assertEqual(response_page_2.status_code, 200)

        self.assertTrue(response_page_1.context["is_paginated"])
        self.assertEqual(
            len(response_page_1.context["articles"]),
            ARTICLES_PER_PAGE_COUNT,
        )
        self.assertEqual(len(response_page_2.context["articles"]), 1)
