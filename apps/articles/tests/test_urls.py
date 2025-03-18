from django.test import SimpleTestCase
from django.urls import resolve, reverse

from articles.views import (
    ArticleCommentView,
    ArticleCreateView,
    ArticleDeleteView,
    ArticleDetailView,
    ArticleLikeView,
    ArticleListFilterView,
    ArticleUpdateView,
    AttachedFileUploadView,
    CommentLikeView,
    HomePageView,
)


class TestURLs(SimpleTestCase):
    def test_homepage_url_is_resolved(self):
        url = reverse("home")
        self.assertEqual(resolve(url).func.view_class, HomePageView)

    def test_articles_list_page_url_is_resolved(self):
        url = reverse("articles")
        self.assertEqual(resolve(url).func.view_class, ArticleListFilterView)

    def test_article_details_page_url_is_resolved(self):
        url = reverse("article-details", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleDetailView)

    def test_article_creation_page_url_is_resolved(self):
        url = reverse("article-create")
        self.assertEqual(resolve(url).func.view_class, ArticleCreateView)

    def test_article_update_page_url_is_resolved(self):
        url = reverse("article-update", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleUpdateView)

    def test_article_delete_page_url_is_resolved(self):
        url = reverse("article-delete", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleDeleteView)

    def test_article_comment_url_is_resolved(self):
        url = reverse("article-comment", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleCommentView)

    def test_article_like_url_is_resolved(self):
        url = reverse("article-like", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleLikeView)

    def test_comment_like_url_is_resolved(self):
        url = reverse("comment-like", args=[1])
        self.assertEqual(resolve(url).func.view_class, CommentLikeView)

    def test_attached_file_upload_url_is_resolved(self):
        url = reverse("attached-file-upload")
        self.assertEqual(resolve(url).func.view_class, AttachedFileUploadView)
