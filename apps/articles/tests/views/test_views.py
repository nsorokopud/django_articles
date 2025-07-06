from unittest.mock import patch

from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article, ArticleCategory, ArticleComment
from users.models import User


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.test_user = User.objects.create_user(
            username="test_user", email="test@test.com"
        )
        self.test_category = ArticleCategory.objects.create(title="cat1", slug="cat1")
        self.test_article = Article.objects.create(
            title="test_article",
            slug="test-article",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        self.test_article.tags.add("tag1")
        self.test_article.save()
        self.test_comment = ArticleComment.objects.create(
            article=self.test_article, author=self.test_user, text="text"
        )

    def test_homepage_view(self):
        with patch("articles.cache.get_redis_connection"):
            response = self.client.get(reverse("home"))

            self.assertRedirects(
                response,
                reverse("articles"),
                status_code=302,
                target_status_code=200,
            )

    def test_article_list_filter_view(self):
        with patch("articles.cache.get_redis_connection"):
            response = self.client.get(reverse("articles"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/home_page.html")

    def test_article_creation_page_view_unauthorized(self):
        url = reverse("article-create")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={url}",
            status_code=302,
            target_status_code=200,
        )

    def test_article_creation_page_view_authorized(self):
        self.client.force_login(self.test_user)
        response = self.client.get(reverse("article-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_form.html")

    def test_article_create_view_post_unauthorized(self):
        url = reverse("article-create")
        response = self.client.post(url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={url}",
            status_code=302,
            target_status_code=200,
        )

    def test_article_create_view_post_authorized(self):
        article_data = {"title": "a1", "preview_text": "1", "content": "1"}
        invalid_article_data = {"title": "a1"}

        with self.assertRaises(Article.DoesNotExist):
            Article.objects.get(slug="a1")

        self.client.force_login(self.test_user)

        url = reverse("article-create")

        response = self.client.post(
            url, invalid_article_data, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json["status"], "fail")
        self.assertEqual(
            response_json["data"],
            {
                "preview_text": ["This field is required."],
                "content": ["This field is required."],
            },
        )

        self.assertEqual(Article.objects.count(), 1)

        response = self.client.post(
            url, article_data, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json["status"], "success")
        self.assertEqual(
            response_json["data"],
            {
                "articleId": self.test_article.id + 1,
                "articleSlug": article_data["title"],
                "articleUrl": "/articles/a1",
            },
        )

        self.assertEqual(Article.objects.count(), 2)

        a = Article.objects.get(slug="a1")
        self.assertEqual(a.title, article_data["title"])
        self.assertEqual(a.slug, article_data["title"])
        self.assertEqual(a.author, self.test_user)
        self.assertEqual(a.category, None)
        self.assertCountEqual(a.tags.all(), [])
        self.assertEqual(a.preview_text, article_data["preview_text"])
        self.assertEqual(a.content, article_data["content"])
        with self.assertRaises(ValueError):
            a.preview_image.url
        self.assertEqual(a.is_published, True)

    def test_article_delete_view_unauthorized(self):
        url = reverse("article-delete", args=[self.test_article.slug])
        self.client.get(url)
        self.assertRaises(Http404)

    def test_article_delete_view_authorized(self):
        a = Article.objects.create(
            title="title",
            slug="slug",
            category=self.test_category,
            preview_text="text",
            content="content",
            author=self.test_user,
        )

        self.client.force_login(self.test_user)
        with patch("articles.cache.get_redis_connection"):
            response = self.client.post(reverse("article-delete", args=[a.slug]))

            self.assertRedirects(
                response, reverse("articles"), status_code=302, target_status_code=200
            )

        with self.assertRaises(Article.DoesNotExist):
            Article.objects.get(pk=a.pk)
