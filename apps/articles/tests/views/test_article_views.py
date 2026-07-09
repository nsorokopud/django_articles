from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse


class TestArticleViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_homepage_view(self):
        with patch("articles.cache.view_counts.get_redis_connection"):
            response = self.client.get(reverse("home"))

            self.assertRedirects(
                response,
                reverse("articles"),
                status_code=302,
                target_status_code=200,
            )

    def test_article_list_filter_view(self):
        with patch("articles.cache.view_counts.get_redis_connection"):
            response = self.client.get(reverse("articles"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_list_page.html")
        self.assertEqual(response.context["page_title"], "Articles matching your query")
        self.assertEqual(
            response.context["empty_message"], "No articles matching your query"
        )
        self.assertTrue(response.context["show_filters"])
        self.assertTrue(response.context["author_filter_ajax_enabled"])
