from io import BytesIO
from unittest.mock import ANY, patch

from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from PIL import Image

from articles.forms import ArticleCommentForm, ArticleModelForm, AttachedFileUploadForm
from articles.models import Article, ArticleCategory, ArticleComment
from core.exceptions import InvalidUpload
from users.models import User


class TestArticleModelForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user,
            preview_text="preview1",
            content="content1",
        )
        self.category = ArticleCategory.objects.create(title="cat1", slug="cat1")

    def get_preview_image(self) -> SimpleUploadedFile:
        image = Image.new("RGB", (1, 1), color="white")
        image_file = BytesIO()
        image.save(image_file, format="JPEG")
        image_file.seek(0)
        return SimpleUploadedFile(
            "test_image.jpg", image_file.read(), content_type="image/jpeg"
        )

    @patch("articles.forms.save_article")
    def test_create_delegates_to_save_article_with_default_publish_false(
        self, mock_save_article
    ):
        preview_image = self.get_preview_image()

        unsaved_result = Article(
            title="a2",
            slug="a2",
            category=self.category,
            preview_text="preview2",
            content="content2",
        )
        mock_save_article.return_value = unsaved_result

        form = ArticleModelForm(
            user=self.user,
            data={
                "title": "a2",
                "category": self.category.id,
                "tags": "tag1, tag2",
                "preview_text": "preview2",
                "content": "content2",
            },
            files={"preview_image": preview_image},
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

        result = form.save()

        self.assertEqual(result, unsaved_result)
        mock_save_article.assert_called_once_with(
            article=ANY,
            author=self.user,
            save_m2m=form.save_m2m,
            publish=False,
        )

        passed_article = mock_save_article.call_args.kwargs["article"]
        self.assertIsNone(passed_article.pk)
        self.assertEqual(passed_article.title, "a2")
        self.assertEqual(passed_article.category, self.category)
        self.assertEqual(passed_article.preview_text, "preview2")
        self.assertEqual(passed_article.content, "content2")
        self.assertTrue(passed_article.preview_image.name.endswith("test_image.jpg"))

    @patch("articles.forms.save_article")
    def test_create_passes_publish_true_when_requested(self, mock_save_article):
        mock_save_article.return_value = self.article

        form = ArticleModelForm(
            user=self.user,
            data={
                "title": "a2",
                "preview_text": "preview2",
                "content": "content2",
            },
        )

        self.assertTrue(form.is_valid())

        form.save(publish=True)

        mock_save_article.assert_called_once_with(
            article=ANY,
            author=self.user,
            save_m2m=form.save_m2m,
            publish=True,
        )

    @patch("articles.forms.save_article")
    def test_update_delegates_to_save_article_with_author_none(self, mock_save_article):
        mock_save_article.return_value = self.article

        form = ArticleModelForm(
            data={
                "title": "a2",
                "category": self.category.id,
                "tags": "tag1, tag2",
                "preview_text": "preview2",
                "content": "content2",
            },
            instance=self.article,
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

        result = form.save()

        self.assertEqual(result, self.article)
        mock_save_article.assert_called_once_with(
            article=ANY,
            author=None,
            save_m2m=form.save_m2m,
            publish=False,
        )

        passed_article = mock_save_article.call_args.kwargs["article"]
        self.assertEqual(passed_article.pk, self.article.pk)
        self.assertEqual(passed_article.title, "a2")
        self.assertEqual(passed_article.preview_text, "preview2")
        self.assertEqual(passed_article.content, "content2")

    def test_save_with_commit_false_returns_unsaved_instance(self):
        form = ArticleModelForm(
            user=self.user,
            data={
                "title": "a2",
                "preview_text": "preview2",
                "content": "content2",
            },
        )

        self.assertTrue(form.is_valid())

        article = form.save(commit=False)

        self.assertIsNone(article.pk)
        self.assertIsNone(article.author_id)
        self.assertEqual(article.title, "a2")
        self.assertEqual(article.preview_text, "preview2")
        self.assertEqual(article.content, "content2")

    def test_missing_fields(self):
        form = ArticleModelForm(data={}, instance=self.article)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "title": ["This field is required."],
                "preview_text": ["This field is required."],
                "content": ["This field is required."],
            },
        )

    def test_user_not_provided_when_creating(self):
        form = ArticleModelForm(
            data={
                "title": "a2",
                "preview_text": "preview2",
                "content": "content2",
            },
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors, {"__all__": ["A valid authenticated user is required."]}
        )

    def test_anonymous_user_provided_when_creating(self):
        form = ArticleModelForm(
            data={
                "title": "a2",
                "preview_text": "preview2",
                "content": "content2",
            },
            user=AnonymousUser(),
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors, {"__all__": ["A valid authenticated user is required."]}
        )


class TestAttachedFileUploadForm(SimpleTestCase):
    @patch("articles.forms.validate_uploaded_file")
    def test_valid_form(self, mock_validate):
        file = SimpleUploadedFile("img.jpg", b"jpg content")
        form = AttachedFileUploadForm(
            files={"file": file},
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

    @patch("articles.forms.validate_uploaded_file")
    def test_invalid_form(self, mock_validate):
        mock_validate.side_effect = InvalidUpload("Invalid upload")
        file = SimpleUploadedFile("img.jpg", b"jpg content")
        form = AttachedFileUploadForm(
            files={"file": file},
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"file": ["Invalid upload"]})


class TestArticleCommentForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user,
            preview_text="text",
            content="content",
        )

    @patch("articles.forms.create_article_comment")
    def test_valid_form(self, mock_create_article_comment):
        comment = ArticleComment(
            text="abc",
            author=self.user,
            article=self.article,
        )
        mock_create_article_comment.return_value = comment

        form = ArticleCommentForm(
            data={"text": "abc"},
            user=self.user,
            article=self.article,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

        result = form.save()

        mock_create_article_comment.assert_called_once_with(
            article=self.article,
            user=self.user,
            text="abc",
        )
        self.assertEqual(result, comment)

    def test_no_user(self):
        form = ArticleCommentForm(
            data={"text": "abc"},
            article=self.article,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {"__all__": ["User is required to save the comment."]},
        )

    def test_no_article(self):
        form = ArticleCommentForm(
            data={"text": "abc"},
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {"__all__": ["Article is required to save the comment."]},
        )

    def test_no_text(self):
        form = ArticleCommentForm(
            data={"text": ""},
            user=self.user,
            article=self.article,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {"text": ["This field is required."]},
        )

    def test_commit_false_is_not_supported(self):
        form = ArticleCommentForm(
            data={"text": "abc"},
            user=self.user,
            article=self.article,
        )
        self.assertTrue(form.is_valid())

        with self.assertRaises(ValueError):
            form.save(commit=False)
