from django.http import Http404
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from articles.models import Article, ArticleCategory


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

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

    def test_homepage_view(self):
        response = self.client.get(reverse("home"))

        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed("articles/home_page.html")

    def test_article_details_page_view(self):
        response = self.client.get(reverse("article-details", args=[self.test_article.slug]))

        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed("articles/article.html")

    def test_article_creation_page_view_unauthorized(self):
        url = reverse("article-create")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={url}",
            status_code=302,
            target_status_code=200,
        )
        self.assertTemplateUsed("articles/article.html")

    def test_article_creation_page_view_authorized(self):
        self.client.login(username="test_user", password="12345")
        response = self.client.get(reverse("article-create"))
        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed("articles/article.html")

    def test_article_update_view_unauthorized(self):
        url = reverse("article-update", args=[self.test_article.slug])
        self.client.get(url)
        self.assertRaises(Http404)

    def test_article_update_view_authorized(self):
        updated_data = {
            "title": "new title",
            "preview_text": "new preview text",
            "content": "new content",
            "tags": "tag1,tag2",
            "is_published": True,
            "author": self.test_user,
        }

        a = Article.objects.create(
            title="title",
            slug="slug",
            category=self.test_category,
            preview_text="text",
            content="content",
            author=self.test_user,
        )

        self.client.login(username="test_user", password="12345")
        response = self.client.post(reverse("article-update", args=[a.slug]), updated_data)

        a.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("article-details", args=[a.slug]),
            status_code=302,
            target_status_code=200,
        )
        self.assertTemplateUsed("articles/article_update.html")

        self.assertEquals(a.author.username, "test_user")
        self.assertEquals(a.title, "new title")
        self.assertEquals(a.slug, "new-title")
        self.assertEquals(a.preview_text, "new preview text")
        self.assertEquals(a.content, "new content")
        new_tags = [tag.name for tag in a.tags.all()]
        self.assertCountEqual(new_tags, ["tag1", "tag2"])

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

        self.client.login(username="test_user", password="12345")
        response = self.client.post(reverse("article-delete", args=[a.slug]))

        with self.assertRaises(Article.DoesNotExist):
            Article.objects.get(pk=a.pk)

        self.assertRedirects(response, reverse("home"), status_code=302, target_status_code=200)
        self.assertTemplateUsed("articles/home_page.html")
