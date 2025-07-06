from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Count
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article, ArticleCategory, ArticleComment
from core.exceptions import MediaSaveError
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
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "Page not found"},
        )

        user = User.objects.create_user(username="user1")
        self.client.force_login(user)
        response = self.client.post(
            reverse("article-update", kwargs={"article_slug": a.slug}),
            updated_data,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"message": "Page not found", "status": "error"},
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
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"status": "error", "message": "Internal server error"},
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
        with patch("articles.cache.get_redis_connection"):
            response = self.client.post(reverse("article-delete", args=[a.slug]))

            self.assertRedirects(
                response, reverse("articles"), status_code=302, target_status_code=200
            )

        with self.assertRaises(Article.DoesNotExist):
            Article.objects.get(pk=a.pk)

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
        self.assertEqual(response.json(), {"status": "success", "data": {"likes": 1}})
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
        self.assertEqual(response.json(), {"status": "success", "data": {"likes": 0}})
        self.assertCountEqual(list(self.test_article.users_that_liked.all()), [])
        likes_count = (
            Article.objects.filter(slug=self.test_article.slug)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 0)


class TestAttachedFileUploadView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user,
            preview_text="text1",
            content="content1",
        )
        self.client = Client()
        self.url = reverse("attached-file-upload")

    @patch("articles.views.default_storage.url")
    @patch("articles.forms.validate_uploaded_file")
    @patch("articles.views.save_media_file_attached_to_article")
    def test_successful_upload(self, mock_save_media, mock_validate, mock_url):
        mock_save_media.return_value = ("path/to/file", f"/article/{self.article.id}/")
        mock_url.return_value = f"{self.article.id}-location"

        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello")
        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "success",
                "data": {
                    "articleUrl": f"/articles/{self.article.slug}",
                    "location": mock_url.return_value,
                },
            },
        )

    def test_upload_without_login(self):
        file = SimpleUploadedFile("test.txt", b"hello")
        response = self.client.post(
            self.url,
            {"file": file, "articleId": "123"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('attached-file-upload')}",
            302,
            200,
        )

    def test_missing_article_id(self):
        file = SimpleUploadedFile("test.jpg", b"hello")
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, {"file": file}, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "Invalid or missing article ID",
            },
        )

    def test_invalid_article_id(self):
        file = SimpleUploadedFile("test.jpg", b"hello")
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {"file": file, "articleId": "abc"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "Invalid or missing article ID",
            },
        )

    def test_non_existent_article(self):
        file = SimpleUploadedFile("test.jpg", b"hello")
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {"file": file, "articleId": 9999},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "Page not found",
            },
        )

    def test_not_author(self):
        user = User.objects.create_user(username="user2", email="user2@test.com")

        self.client.force_login(user)
        file = SimpleUploadedFile("test.jpg", b"hello")
        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "No permission to edit this article",
            },
        )

    def test_no_file(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {"articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "File is required.",
            },
        )

    @patch("articles.forms.AttachedFileUploadForm.clean_file")
    def test_invalid_file(self, mock_clean):
        mock_clean.side_effect = ValidationError("Some error")

        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello")
        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "message": "Some error",
            },
        )

    @patch(
        "articles.views.base.save_media_file_attached_to_article",
        side_effect=MediaSaveError("Media save error"),
    )
    @patch("articles.views.base.logger")
    @patch("articles.forms.validate_uploaded_file")
    def test_file_save_error(self, mock_validate, mock_logger, mock_save):
        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello")

        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        mock_save.assert_called_once()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(), {"status": "error", "message": "File saving error"}
        )
        mock_logger.exception.assert_called_once_with(
            "Error while saving uploaded file."
        )

    @patch(
        "articles.views.base.save_media_file_attached_to_article",
        side_effect=ZeroDivisionError("Unexpected error"),
    )
    @patch("articles.views.base.logger")
    @patch("articles.forms.validate_uploaded_file")
    def test_unexpected_error(self, mock_validate, mock_logger, mock_save):
        self.client.force_login(self.user)
        file = SimpleUploadedFile("test.jpg", b"hello")

        self.client.raise_request_exception = False
        response = self.client.post(
            self.url,
            {"file": file, "articleId": self.article.id},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        mock_save.assert_called_once()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(), {"status": "error", "message": "Internal server error"}
        )


class TestArticleCommentView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user,
            preview_text="text1",
            content="content1",
        )
        self.url = reverse("article-comment", args=[self.article.slug])

    def test_anonymous_user(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={self.url}",
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(ArticleComment.objects.count(), 0)

    def test_non_existent_article(self):
        url = reverse("article-comment", args=["non-existent-article"])
        comment_data = {"text": "text"}

        self.client.force_login(self.user)
        response = self.client.post(url, comment_data)
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "error.html")
        self.assertEqual(ArticleComment.objects.count(), 0)

    def test_form_error(self):
        comment_data = {"text": ""}

        self.client.force_login(self.user)
        with (
            patch("articles.cache.get_redis_connection"),
            patch("articles.views.decorators.get_redis_connection"),
        ):
            response = self.client.post(self.url, comment_data)
            self.assertRedirects(
                response,
                reverse("article-details", args=[self.article.slug]),
                status_code=302,
                target_status_code=200,
            )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, 40)  # ERROR level
        self.assertEqual(messages[0].message, "Your comment could not be posted.")
        self.assertEqual(ArticleComment.objects.count(), 0)

    def test_correct_case(self):
        comment_data = {"text": "text"}

        self.client.force_login(self.user)
        with (
            patch("articles.cache.get_redis_connection"),
            patch("articles.views.decorators.get_redis_connection"),
        ):
            response = self.client.post(self.url, comment_data)
            self.assertRedirects(
                response,
                reverse("article-details", args=[self.article.slug]),
                status_code=302,
                target_status_code=200,
            )

        self.assertEqual(ArticleComment.objects.count(), 1)
        last_comment = ArticleComment.objects.last()
        self.assertEqual(last_comment.text, comment_data["text"])
        self.assertEqual(last_comment.article, self.article)
        self.assertEqual(last_comment.author, self.user)


class TestCommentLikeView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user,
            preview_text="text1",
            content="content1",
        )
        self.comment = ArticleComment.objects.create(
            article=self.article, author=self.user, text="text"
        )
        self.url = reverse("comment-like", args=[self.comment.id])

    def test_get(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_post_anonymous_user(self):
        response = self.client.post(self.url)
        self.assertRedirects(
            response,
            f"/login/?next={self.url}",
            status_code=302,
            target_status_code=200,
        )

    def test_post(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"likes": 1}},
        )
        self.assertCountEqual(list(self.comment.users_that_liked.all()), [self.user])
        likes_count = (
            ArticleComment.objects.filter(id=self.comment.id)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 1)

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"likes": 0}},
        )
        self.assertCountEqual(list(self.comment.users_that_liked.all()), [])
        likes_count = (
            ArticleComment.objects.filter(id=self.comment.id)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 0)
