from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from PIL import Image
from taggit.models import Tag

from articles.forms import ArticleCommentForm, ArticleModelForm, AttachedFileUploadForm
from articles.models import Article, ArticleCategory
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

    def test_create(self):
        preview_image = self.get_preview_image()
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

        article = form.save()
        self.assertNotEqual(article.pk, self.article.pk)
        self.assertEqual(article.title, "a2")
        self.assertEqual(article.slug, "a2")
        self.assertEqual(article.author, self.user)
        self.assertEqual(article.category, self.category)
        self.assertEqual(article.preview_text, "preview2")
        self.assertEqual(article.content, "content2")
        tag1 = Tag.objects.get(name="tag1")
        tag2 = Tag.objects.get(name="tag2")
        self.assertCountEqual(article.tags.all(), [tag1, tag2])
        image_name, ext = article.preview_image.name.split(".")
        self.assertIn("articles/preview_images/test_image", image_name)
        self.assertEqual(ext, "jpg")
        expected_image = Image.open(preview_image).convert("RGB")
        with article.preview_image.open("rb") as f:
            updated_image = Image.open(f).convert("RGB")
        self.assertEqual(list(updated_image.getdata()), list(expected_image.getdata()))

    def test_update(self):
        preview_image = self.get_preview_image()
        form = ArticleModelForm(
            data={
                "title": "a2",
                "category": self.category.id,
                "tags": "tag1, tag2",
                "preview_text": "preview2",
                "content": "content2",
            },
            files={"preview_image": preview_image},
            instance=self.article,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})

        with patch("articles.services.generate_unique_article_slug") as mock_slug:
            mock_slug.return_value = "slug2"
            updated_article = form.save()
            mock_slug.assert_called_once_with("a2")

        self.assertEqual(updated_article.pk, self.article.pk)
        self.assertEqual(updated_article.author, self.user)
        self.assertEqual(updated_article.title, "a2")
        self.assertEqual(updated_article.slug, "slug2")
        self.assertEqual(updated_article.category, self.category)
        self.assertEqual(updated_article.preview_text, "preview2")
        self.assertEqual(updated_article.content, "content2")
        tag1 = Tag.objects.get(name="tag1")
        tag2 = Tag.objects.get(name="tag2")
        self.assertCountEqual(updated_article.tags.all(), [tag1, tag2])
        image_name, ext = updated_article.preview_image.name.split(".")
        self.assertIn("articles/preview_images/test_image", image_name)
        self.assertEqual(ext, "jpg")
        expected_image = Image.open(preview_image).convert("RGB")
        with updated_article.preview_image.open("rb") as f:
            updated_image = Image.open(f).convert("RGB")
        self.assertEqual(list(updated_image.getdata()), list(expected_image.getdata()))

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
