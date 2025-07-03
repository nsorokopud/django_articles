from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from articles.forms import ArticleCommentForm, AttachedFileUploadForm
from articles.models import Article
from core.exceptions import InvalidUpload
from users.models import User


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

    def test_valid_form(self):
        form = ArticleCommentForm(
            data={"text": "abc"}, user=self.user, article=self.article
        )
        self.assertTrue(form.is_valid())
        comment = form.save()
        self.assertEqual(comment.text, "abc")
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.article, self.article)

    def test_no_user(self):
        form = ArticleCommentForm(data={"text": "abc"}, article=self.article)
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValueError):
            form.save()
        self.assertEqual(
            form.errors, {"__all__": ["User is required to save the comment."]}
        )

    def test_no_article(self):
        form = ArticleCommentForm(data={"text": "abc"}, user=self.user)
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValueError):
            form.save()
        self.assertEqual(
            form.errors, {"__all__": ["Article is required to save the comment."]}
        )

    def test_no_text(self):
        form = ArticleCommentForm(
            data={"text": ""}, user=self.user, article=self.article
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"text": ["This field is required."]})
