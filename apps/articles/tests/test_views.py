from django.contrib.auth.models import User
from django.db.models import Count
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article, ArticleCategory, ArticleComment


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.test_user = User(username="test_user", email="test@test.com")
        self.test_user.set_password("12345")
        self.test_user.save()

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
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("articles/home_page.html")

    def test_article_list_filter_view(self):
        response = self.client.get(reverse("articles"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("articles/home_page.html")

    def test_article_category_view(self):
        response = self.client.get(reverse("article-category", args=["gherngjre"]))
        self.assertRaises(Http404)

        response = self.client.get(reverse("article-category", args=[self.test_category.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("articles/home_page.html")

    def test_article_tag_view(self):
        response = self.client.get(reverse("article-tag", args=["dadcsds"]))
        self.assertRaises(Http404)

        response = self.client.get(
            reverse("article-tag", args=[self.test_article.tags.all()[0].name])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("articles/home_page.html")

    def test_article_search_view(self):
        response = self.client.get(reverse("article-search"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("articles/home_page.html")

    def test_article_details_page_view(self):
        response = self.client.get(reverse("article-details", args=[self.test_article.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("articles/article.html")

        self.test_article.refresh_from_db()
        self.assertEqual(self.test_article.views_count, 1)

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
        self.assertEqual(response.status_code, 200)
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

        self.assertEqual(a.author.username, "test_user")
        self.assertEqual(a.title, "new title")
        self.assertEqual(a.slug, "new-title")
        self.assertEqual(a.preview_text, "new preview text")
        self.assertEqual(a.content, "new content")
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

    def test_article_comment_view_unauthorized(self):
        url = reverse("article-comment", args=[self.test_article.slug])
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={url}",
            status_code=302,
            target_status_code=200,
        )
        self.assertTemplateUsed("articles/article.html")

    def test_article_comment_view_authorized(self):
        url = reverse("article-comment", args=[self.test_article.slug])
        comment_data = {"text": "text"}

        self.client.login(username="test_user", password="12345")
        response = self.client.post(url, comment_data)
        self.assertRedirects(
            response,
            reverse("article-details", args=[self.test_article.slug]),
            status_code=302,
            target_status_code=200,
        )
        self.assertTemplateUsed("articles/article.html")

        article_comments = ArticleComment.objects.filter(article=self.test_article)
        self.assertEqual(len(article_comments), 2)
        last_comment = article_comments.last()
        self.assertEqual(last_comment.text, comment_data["text"])
        self.assertEqual(last_comment.article, self.test_article)
        self.assertEqual(last_comment.author, self.test_user)

    def test_article_like_view_get(self):
        url = reverse("article-like", args=[self.test_article.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_article_like_view_post(self):
        url = reverse("article-like", args=[self.test_article.slug])
        self.client.login(username="test_user", password="12345")

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(list(self.test_article.users_that_liked.all()), [self.test_user])
        likes_count = (
            Article.objects.filter(slug=self.test_article.slug)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 1)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(list(self.test_article.users_that_liked.all()), [])
        likes_count = (
            Article.objects.filter(slug=self.test_article.slug)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 0)

    def test_comment_like_view_get(self):
        url = reverse("comment-like", args=[self.test_comment.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_comment_like_view_post(self):
        url = reverse("comment-like", args=[self.test_comment.id])
        self.client.login(username="test_user", password="12345")

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(list(self.test_comment.users_that_liked.all()), [self.test_user])
        likes_count = (
            ArticleComment.objects.filter(id=self.test_comment.id)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 1)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(list(self.test_comment.users_that_liked.all()), [])
        likes_count = (
            ArticleComment.objects.filter(id=self.test_comment.id)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 0)
