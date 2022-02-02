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
