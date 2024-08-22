from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse, resolve

from articles.models import Article, ArticleCategory, ArticleComment
from articles.views import (
    ArticleListFilterView,
    ArticleCategoryView,
    ArticleCommentView,
    ArticleCreateView,
    ArticleDeleteView,
    ArticleDetailView,
    ArticleLikeView,
    ArticleSearchView,
    ArticleUpdateView,
    CommentLikeView,
    HomePageView,
)


class TestURLs(TestCase):
    def setUp(self):
        self.test_user = User(username="test_user", email="test@test.com")
        self.test_user.set_password("12345")
        self.test_user.save()

        self.test_category = ArticleCategory.objects.create(title="cat1", slug="cat1")
        self.test_article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

        self.test_comment = ArticleComment.objects.create(
            article=self.test_article, author=self.test_user, text="text"
        )

    def test_homepage_url_is_resolved(self):
        url = reverse("home")
        self.assertEqual(resolve(url).func.view_class, HomePageView)

    def test_articles_list_page_url_is_resolved(self):
        url = reverse("articles")
        self.assertEqual(resolve(url).func.view_class, ArticleListFilterView)

    def test_article_details_page_url_is_resolved(self):
        url = reverse("article-details", args=[self.test_article.slug])
        self.assertEqual(resolve(url).func.view_class, ArticleDetailView)

    def test_article_creation_page_url_is_resolved(self):
        url = reverse("article-create")
        self.assertEqual(resolve(url).func.view_class, ArticleCreateView)

    def test_article_update_page_url_is_resolved(self):
        url = reverse("article-update", args=[self.test_article.slug])
        self.assertEqual(resolve(url).func.view_class, ArticleUpdateView)

    def test_article_delete_page_url_is_resolved(self):
        url = reverse("article-delete", args=[self.test_article.slug])
        self.assertEqual(resolve(url).func.view_class, ArticleDeleteView)

    def test_article_comment_url_is_resolved(self):
        url = reverse("article-comment", args=[self.test_article.slug])
        self.assertEqual(resolve(url).func.view_class, ArticleCommentView)

    def test_article_like_url_is_resolved(self):
        url = reverse("article-like", args=[self.test_article.slug])
        self.assertEqual(resolve(url).func.view_class, ArticleLikeView)

    def test_comment_like_url_is_resolved(self):
        url = reverse("comment-like", args=[self.test_comment.id])
        self.assertEqual(resolve(url).func.view_class, CommentLikeView)

    def test_article_category_url_is_resolved(self):
        url = reverse("article-category", args=[self.test_article.slug])
        self.assertEqual(resolve(url).func.view_class, ArticleCategoryView)

    def test_article_search_url_is_resolved(self):
        url = reverse("article-search")
        self.assertEqual(resolve(url).func.view_class, ArticleSearchView)
