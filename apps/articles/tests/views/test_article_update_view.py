from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article, ArticleCategory
from users.models import User


class TestArticleUpdateView(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.category = ArticleCategory.objects.create(title="cat1", slug="cat1")
        self.article = Article.objects.create(
            title="article",
            slug="test-article",
            category=self.category,
            author=self.user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        self.article.tags.add("tag1")
        self.article.save()
        self.url = reverse("article-update", kwargs={"article_slug": self.article.slug})

    def test_get_anonymous_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_not_author(self):
        user = User.objects.create_user("user1")
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_non_existent_article(self):
        url = reverse("article-update", kwargs={"article_slug": "non-existent-article"})

        with self.assertRaises(Article.DoesNotExist):
            response = self.client.get(url)

        self.client.raise_request_exception = False
        response = self.client.get(url)
        self.assertEqual(response.status_code, 500)
        self.assertTemplateUsed(response, "error.html")
        self.assertEqual(response.context["error_code"], 500)
        self.assertEqual(response.context["error_message"], "Internal server error")
        self.client.raise_request_exception = True

    def test_get_correct(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_form.html")

    def test_post_anonymous_user(self):
        response = self.client.post(
            reverse("article-update", kwargs={"article_slug": self.article.slug}),
            {"title": "new title"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "Page not found"},
        )

    def test_post_not_author(self):
        user = User.objects.create_user(username="user2")
        self.client.force_login(user)
        response = self.client.post(
            reverse("article-update", kwargs={"article_slug": self.article.slug}),
            {"title": "new title"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"message": "Page not found", "status": "error"},
        )

    def test_post_non_existent_article(self):
        url = reverse("article-update", kwargs={"article_slug": "non-existent-article"})

        self.client.force_login(self.user)
        with self.assertRaises(Article.DoesNotExist):
            response = self.client.post(
                url,
                {"title": "new title"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )

        self.client.raise_request_exception = False
        response = self.client.post(
            url, {"title": "new title"}, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "Internal server error"},
        )
        self.client.raise_request_exception = True

    def test_post_invalid_data(self):
        invalid_data = {
            "title": "",
            "content": "",
        }

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("article-update", args=[self.article.slug]), invalid_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "fail",
                "data": {
                    "title": ["This field is required."],
                    "preview_text": ["This field is required."],
                    "content": ["This field is required."],
                },
            },
        )

    def test_post_correct(self):
        cat = ArticleCategory.objects.create(title="new category", slug="new-category")
        updated_data = {
            "title": "new title",
            "category": cat.id,
            "preview_text": "new preview text",
            "content": "new content",
            "tags": "tag2, tag3",
        }

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("article-update", args=[self.article.slug]), updated_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"articleUrl": "/articles/new-title"}},
        )

        a = self.article
        a.refresh_from_db()
        self.assertEqual(a.author.username, "user")
        self.assertEqual(a.title, "new title")
        self.assertEqual(a.slug, "new-title")
        self.assertEqual(a.category.title, "new category")
        self.assertEqual(a.preview_text, "new preview text")
        self.assertEqual(a.content, "new content")
        new_tags = [tag.name for tag in a.tags.all()]
        self.assertCountEqual(new_tags, ["tag2", "tag3"])
