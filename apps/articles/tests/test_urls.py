from django.test import SimpleTestCase
from django.urls import resolve, reverse

from articles.views.articles import (
    ArticleCreateDraftView,
    ArticleDeleteView,
    ArticleDetailView,
    ArticleLikeView,
    ArticleListFilterView,
    ArticleUpdateView,
    ArticleWithdrawFromReviewView,
    MyArticlesListView,
    SubscriptionFeedView,
)
from articles.views.base import AttachedFileUploadView, HomePageView
from articles.views.comments import ArticleCommentsListView, CommentLikeView


class TestURLs(SimpleTestCase):
    def test_homepage_url_is_resolved(self):
        url = reverse("home")
        self.assertEqual(resolve(url).func.view_class, HomePageView)

    def test_articles_list_page_url_is_resolved(self):
        url = reverse("articles")
        self.assertEqual(resolve(url).func.view_class, ArticleListFilterView)

    def test_subscription_feed_page_url_is_resolved(self):
        url = reverse("subscription-feed")
        self.assertEqual(resolve(url).func.view_class, SubscriptionFeedView)

    def test_my_articles_list_page_url_is_resolved(self):
        url = reverse("my-articles")
        self.assertEqual(resolve(url).func.view_class, MyArticlesListView)

    def test_article_details_page_url_is_resolved(self):
        url = reverse("article-details", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleDetailView)

    def test_draft_creation_url_is_resolved(self):
        url = reverse("article-create-draft")
        self.assertEqual(resolve(url).func.view_class, ArticleCreateDraftView)

    def test_article_update_page_url_is_resolved(self):
        url = reverse("article-update", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleUpdateView)

    def test_article_withdraw_from_review_url_is_resolved(self):
        url = reverse("article-withdraw-from-review", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleWithdrawFromReviewView)

    def test_article_delete_page_url_is_resolved(self):
        url = reverse("article-delete", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleDeleteView)

    def test_article_like_url_is_resolved(self):
        url = reverse("article-like", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleLikeView)

    def test_article_comments_list_view_url_is_resolved(self):
        url = reverse("article-comments-list", args=[1])
        self.assertEqual(resolve(url).func.view_class, ArticleCommentsListView)

    def test_comment_like_url_is_resolved(self):
        url = reverse("comment-like", args=[1])
        self.assertEqual(resolve(url).func.view_class, CommentLikeView)

    def test_attached_file_upload_url_is_resolved(self):
        url = reverse("attached-file-upload")
        self.assertEqual(resolve(url).func.view_class, AttachedFileUploadView)
