from unittest.mock import Mock, patch

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase

from articles.views.decorators import increment_article_view_counter


class TestIncrementArticleViewCounter(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("articles.views.decorators.get_cached_article_id_by_slug")
    @patch("articles.views.decorators.register_article_view")
    @patch("articles.views.decorators.get_visitor_id")
    def test_calls_wrapped_view(
        self,
        mock_get_visitor_id,
        mock_register_article_view,
        mock_get_cached_article_id,
    ):
        mock_get_cached_article_id.return_value = None

        request = self.factory.get("/articles/test-article/")
        view_func = Mock(return_value="response")

        wrapped = increment_article_view_counter(view_func)
        response = wrapped(request, article_slug="test-article")

        self.assertEqual(response, "response")
        view_func.assert_called_once_with(request, article_slug="test-article")
        mock_get_cached_article_id.assert_called_once_with("test-article")
        mock_get_visitor_id.assert_not_called()
        mock_register_article_view.assert_not_called()

    @patch("articles.views.decorators.get_visitor_id")
    @patch("articles.views.decorators.register_article_view")
    @patch("articles.views.decorators.get_cached_article_id_by_slug")
    def test_registers_article_view_when_slug_resolves_to_article_id(
        self,
        mock_get_cached_article_id,
        mock_register_article_view,
        mock_get_visitor_id,
    ):
        request = self.factory.get("/articles/test-article/")
        view_func = Mock(return_value="response")
        mock_get_cached_article_id.return_value = 123
        mock_get_visitor_id.return_value = "visitor-abc"

        wrapped = increment_article_view_counter(view_func)
        response = wrapped(request, article_slug="test-article")

        self.assertEqual(response, "response")
        mock_get_cached_article_id.assert_called_once_with("test-article")
        mock_get_visitor_id.assert_called_once_with(request)
        mock_register_article_view.assert_called_once_with(
            article_id=123,
            viewer_id="visitor-abc",
            unique_view_timeout=settings.ARTICLES_UNIQUE_VIEW_WINDOW_SECONDS,
        )
        view_func.assert_called_once_with(request, article_slug="test-article")

    @patch("articles.views.decorators.get_visitor_id")
    @patch("articles.views.decorators.register_article_view")
    @patch("articles.views.decorators.get_cached_article_id_by_slug")
    def test_does_not_register_view_when_slug_does_not_resolve(
        self,
        mock_get_cached_article_id,
        mock_register_article_view,
        mock_get_visitor_id,
    ):
        request = self.factory.get("/articles/missing/")
        view_func = Mock(return_value="response")
        mock_get_cached_article_id.return_value = None

        wrapped = increment_article_view_counter(view_func)
        response = wrapped(request, article_slug="missing")

        self.assertEqual(response, "response")
        mock_get_cached_article_id.assert_called_once_with("missing")
        mock_get_visitor_id.assert_not_called()
        mock_register_article_view.assert_not_called()
        view_func.assert_called_once_with(request, article_slug="missing")

    @patch("articles.views.decorators.get_visitor_id")
    @patch("articles.views.decorators.register_article_view")
    @patch("articles.views.decorators.get_cached_article_id_by_slug")
    def test_does_not_lookup_or_register_when_slug_missing(
        self,
        mock_get_cached_article_id,
        mock_register_article_view,
        mock_get_visitor_id,
    ):
        request = self.factory.get("/articles/")
        view_func = Mock(return_value="response")

        wrapped = increment_article_view_counter(view_func)
        response = wrapped(request)

        self.assertEqual(response, "response")
        mock_get_cached_article_id.assert_not_called()
        mock_get_visitor_id.assert_not_called()
        mock_register_article_view.assert_not_called()
        view_func.assert_called_once_with(request)

    def test_preserves_wrapped_function_metadata(self):
        def test_view(request, *args, **kwargs):
            return "response"

        wrapped = increment_article_view_counter(test_view)
        self.assertEqual(wrapped.__name__, "test_view")
