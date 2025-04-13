from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Count
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
        response = self.client.get(reverse("home"))

        self.assertRedirects(
            response,
            reverse("articles"),
            status_code=302,
            target_status_code=200,
        )

    def test_article_list_filter_view(self):
        response = self.client.get(reverse("articles"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/home_page.html")

    def test_article_details_page_view(self):
        response = self.client.get(
            reverse("article-details", args=[self.test_article.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article.html")

        self.test_article.refresh_from_db()
        self.assertEqual(self.test_article.views_count, 1)

    def test_article_details_page_view__views_counter_increments_once_per_session(self):
        url = reverse("article-details", args=[self.test_article.slug])
        user2 = User.objects.create_user(
            username="user2", email="user2@test.com"
        )
        self.assertEqual(self.test_article.views_count, 0)

        self.client.get(url)
        self.test_article.refresh_from_db()
        self.assertEqual(self.test_article.views_count, 1)

        self.client.force_login(self.test_user)
        self.client.get(url)
        self.test_article.refresh_from_db()
        self.assertEqual(self.test_article.views_count, 1)

        self.client.force_login(user2)
        self.client.get(url)
        self.test_article.refresh_from_db()
        self.assertEqual(self.test_article.views_count, 2)

        self.client.get(url)
        self.test_article.refresh_from_db()
        self.assertEqual(self.test_article.views_count, 2)

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

    def test_article_update_view_get(self):
        url = reverse("article-update", kwargs={"article_slug": self.test_article.slug})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        user = User.objects.create_user("user1")
        self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.test_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_form.html")

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

    def test_article_update_view_post_unauthorized(self):
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

        response = self.client.post(
            reverse("article-update", kwargs={"article_slug": a.slug}),
            updated_data,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "HTTP Error 404: Page not found"},
        )

        user = User.objects.create_user(username="user1")
        self.client.force_login(user)
        response = self.client.post(
            reverse("article-update", kwargs={"article_slug": a.slug}),
            updated_data,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"message": "HTTP Error 404: Page not found", "status": "error"},
        )

    def test_article_update_view_post_authorized(self):
        invalid_updated_data = {
            "title": "",
            "content": "",
        }

        cat = ArticleCategory.objects.create(title="new category", slug="new-category")

        updated_data = {
            "title": "new title",
            "category": cat.id,
            "preview_text": "new preview text",
            "content": "new content",
            "tags": "tag2, tag3",
        }

        a = Article.objects.create(
            title="title",
            slug="slug",
            category=self.test_category,
            preview_text="text",
            content="content",
            author=self.test_user,
        )
        a.tags.add("tag1")

        url = reverse("article-update", kwargs={"article_slug": "non-existent-article"})

        self.client.force_login(self.test_user)
        with self.assertRaises(Article.DoesNotExist):
            response = self.client.post(
                url, updated_data, headers={"X-Requested-With": "XMLHttpRequest"}
            )

        self.client.raise_request_exception = False
        response = self.client.post(
            url, updated_data, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "HTTP Error 500: Internal server error"},
        )
        self.client.raise_request_exception = True

        response = self.client.post(
            reverse("article-update", args=[a.slug]), invalid_updated_data
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

        response = self.client.post(
            reverse("article-update", args=[a.slug]), updated_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"articleUrl": "/articles/new-title"}},
        )

        a.refresh_from_db()
        self.assertEqual(a.author.username, "test_user")
        self.assertEqual(a.title, "new title")
        self.assertEqual(a.slug, "new-title")
        self.assertEqual(a.category.title, "new category")
        self.assertEqual(a.preview_text, "new preview text")
        self.assertEqual(a.content, "new content")
        new_tags = [tag.name for tag in a.tags.all()]
        self.assertCountEqual(new_tags, ["tag2", "tag3"])

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
        response = self.client.post(reverse("article-delete", args=[a.slug]))

        with self.assertRaises(Article.DoesNotExist):
            Article.objects.get(pk=a.pk)

        self.assertRedirects(
            response, reverse("articles"), status_code=302, target_status_code=200
        )

    def test_article_comment_view_unauthorized(self):
        url = reverse("article-comment", args=[self.test_article.slug])
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={url}",
            status_code=302,
            target_status_code=200,
        )

    def test_article_comment_view_authorized(self):
        url = reverse("article-comment", args=[self.test_article.slug])
        comment_data = {"text": "text"}

        self.client.force_login(self.test_user)
        response = self.client.post(url, comment_data)
        self.assertRedirects(
            response,
            reverse("article-details", args=[self.test_article.slug]),
            status_code=302,
            target_status_code=200,
        )

        article_comments = ArticleComment.objects.filter(article=self.test_article)
        self.assertEqual(len(article_comments), 2)
        last_comment = article_comments.last()
        self.assertEqual(last_comment.text, comment_data["text"])
        self.assertEqual(last_comment.article, self.test_article)
        self.assertEqual(last_comment.author, self.test_user)

    def test_article_like_view_get(self):
        url = reverse("article-like", args=[self.test_article.slug])
        response = self.client.get(url)
        self.assertRedirects(
            response,
            "/login/?next=/articles/test-article/like",
            status_code=302,
            target_status_code=200,
        )

        self.client.force_login(self.test_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_article_like_view_post(self):
        url = reverse("article-like", args=[self.test_article.slug])

        response = self.client.post(url)
        self.assertRedirects(
            response,
            "/login/?next=/articles/test-article/like",
            status_code=302,
            target_status_code=200,
        )

        self.client.force_login(self.test_user)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            list(self.test_article.users_that_liked.all()), [self.test_user]
        )
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
        self.assertRedirects(
            response,
            f"/login/?next=/comments/{self.test_comment.id}/like",
            status_code=302,
            target_status_code=200,
        )

        self.client.force_login(self.test_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_comment_like_view_post(self):
        url = reverse("comment-like", args=[self.test_comment.id])

        response = self.client.post(url)
        self.assertRedirects(
            response,
            f"/login/?next=/comments/{self.test_comment.id}/like",
            status_code=302,
            target_status_code=200,
        )

        self.client.force_login(self.test_user)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            list(self.test_comment.users_that_liked.all()), [self.test_user]
        )
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

    def test_attached_file_upload_view_unauthorized(self):
        url = reverse("attached-file-upload")
        response = self.client.post(url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={url}",
            status_code=302,
            target_status_code=200,
        )

    def test_attached_file_upload_view_incorrect_post_data(self):
        url = reverse("attached-file-upload")
        self.client.force_login(self.test_user)

        with self.assertRaises(Article.DoesNotExist):
            response = self.client.post(url)

        self.client.raise_request_exception = False

        response = self.client.post(url)
        self.assertEqual(response.status_code, 500)

        response = self.client.post(
            url, {}, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json["status"], "error")
        self.assertEqual(
            response_json["message"], "HTTP Error 500: Internal server error"
        )

        self.client.raise_request_exception = True

    def test_attached_file_upload_view_correct(self):
        file_name = "file.jpg"
        self.client.force_login(self.test_user)

        with (
            patch(
                "django.core.files.storage.default_storage.save",
                side_effect=[file_name],
            ),
            patch(
                "django.core.files.storage.default_storage.url", side_effect=[file_name]
            ),
        ):
            file = SimpleUploadedFile(
                file_name, b"file_content", content_type="image/jpg"
            )
            response = self.client.post(
                reverse("attached-file-upload"),
                {"articleId": self.test_article.id, "file": file},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            self.assertEqual(response.status_code, 200)
            response_json = response.json()
            self.assertEqual(response_json["status"], "success")
            self.assertEqual(
                response_json["data"],
                {"location": "file.jpg", "articleUrl": "/articles/test-article"},
            )
