from io import BytesIO
from unittest.mock import ANY, patch

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from PIL import Image

from articles.forms import (
    ARTICLE_COMMENT_MAX_LENGTH,
    ARTICLE_REJECT_REASON_MAX_LENGTH,
    ARTICLE_REJECT_REASON_MIN_LENGTH,
    ArticleAdminForm,
    ArticleCommentForm,
    ArticleModelForm,
    ArticleRejectAdminForm,
    AttachedFileUploadForm,
)
from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
from core.exceptions import InvalidUpload
from users.models import User


class TestArticleAdminForm(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )

    def test_slug_is_not_required(self):
        form = ArticleAdminForm()

        self.assertFalse(form.fields["slug"].required)

    def test_slug_help_text_shown_for_new_article(self):
        form = ArticleAdminForm()

        self.assertEqual(
            form.fields["slug"].help_text,
            "Leave blank to automatically generate a new slug from the title.",
        )

    def test_slug_help_text_shown_for_draft_article(self):
        article = Article.objects.create(
            title="Draft",
            slug="draft",
            author=self.author,
            status=ArticleStatus.DRAFT,
        )

        form = ArticleAdminForm(instance=article)

        self.assertEqual(
            form.fields["slug"].help_text,
            "Leave blank to automatically generate a new slug from the title.",
        )

    def test_slug_help_text_shown_for_rejected_article(self):
        article = Article.objects.create(
            title="Rejected",
            slug="rejected",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.REJECTED,
            reviewed_at=timezone.now(),
            review_note="Fix grammar.",
        )

        form = ArticleAdminForm(instance=article)

        self.assertEqual(
            form.fields["slug"].help_text,
            "Leave blank to automatically generate a new slug from the title.",
        )


class TestArticleRejectAdminForm(SimpleTestCase):
    def test_form_is_valid_with_reason_at_min_length(self):
        reason = "a" * ARTICLE_REJECT_REASON_MIN_LENGTH

        form = ArticleRejectAdminForm(data={"reason": reason})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["reason"], reason)

    def test_form_is_valid_with_reason_longer_than_min_length(self):
        reason = "This article needs clearer sourcing and a stronger conclusion."

        form = ArticleRejectAdminForm(data={"reason": reason})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["reason"], reason)

    def test_reason_is_stripped_in_clean_reason(self):
        raw_reason = "   This article needs clearer sourcing.   "
        expected_reason = "This article needs clearer sourcing."

        form = ArticleRejectAdminForm(data={"reason": raw_reason})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["reason"], expected_reason)

    def test_form_is_invalid_when_reason_is_missing(self):
        form = ArticleRejectAdminForm(data={})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["reason"], ["This field is required."])

    def test_form_is_invalid_when_reason_is_blank(self):
        form = ArticleRejectAdminForm(data={"reason": ""})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["reason"], ["This field is required."])

    def test_form_is_invalid_when_reason_is_only_whitespace(self):
        form = ArticleRejectAdminForm(data={"reason": "   "})

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["reason"],
            ["This field is required."],
        )

    def test_form_is_invalid_when_reason_is_shorter_than_min_length(self):
        reason = "a" * (ARTICLE_REJECT_REASON_MIN_LENGTH - 1)

        form = ArticleRejectAdminForm(data={"reason": reason})

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["reason"],
            [
                "Please provide a more detailed explanation "
                f"(at least {ARTICLE_REJECT_REASON_MIN_LENGTH} characters)."
            ],
        )

    def test_form_is_invalid_when_trimmed_reason_is_shorter_than_min_length(self):
        core = "a" * (ARTICLE_REJECT_REASON_MIN_LENGTH - 1)
        reason = f"   {core}   "

        form = ArticleRejectAdminForm(data={"reason": reason})

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["reason"],
            [
                "Please provide a more detailed explanation "
                f"(at least {ARTICLE_REJECT_REASON_MIN_LENGTH} characters)."
            ],
        )

    def test_form_is_invalid_when_reason_exceeds_max_length(self):
        reason = "a" * (ARTICLE_REJECT_REASON_MAX_LENGTH + 1)

        form = ArticleRejectAdminForm(data={"reason": reason})

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["reason"],
            [
                f"Ensure this value has at most "
                f"{ARTICLE_REJECT_REASON_MAX_LENGTH} characters "
                f"(it has {ARTICLE_REJECT_REASON_MAX_LENGTH + 1})."
            ],
        )

    def test_reason_field_configuration(self):
        form = ArticleRejectAdminForm()
        field = form.fields["reason"]

        self.assertTrue(field.required)
        self.assertEqual(field.label, "Rejection reason")
        self.assertEqual(field.max_length, ARTICLE_REJECT_REASON_MAX_LENGTH)
        self.assertEqual(
            field.help_text,
            "This note will be shown to the article author.",
        )
        self.assertIsInstance(field.widget, forms.Textarea)
        self.assertEqual(field.widget.attrs["rows"], 6)
        self.assertEqual(
            field.widget.attrs["placeholder"],
            "Explain what should be fixed before resubmission.",
        )


class TestArticleModelForm(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user,
            preview_text="preview1",
            content="content1",
            content_text="content1",
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
    def test_create_delegates_to_save_article_with_author(self, mock_save_article):
        preview_image = self.get_preview_image()

        saved_result = Article.objects.create(
            author=self.user,
            title="a2",
            slug="a2",
            category=self.category,
            preview_text="preview2",
            content="content2",
        )
        mock_save_article.return_value = saved_result

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

        self.assertTrue(form.is_valid(), form.errors)

        with patch.object(form, "_save_m2m") as mock_save_m2m:
            result = form.save()

        self.assertEqual(result, saved_result)
        mock_save_article.assert_called_once_with(article=ANY, author=self.user)
        mock_save_m2m.assert_called_once()

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

        self.assertTrue(form.is_valid(), form.errors)

        with patch.object(form, "_save_m2m") as mock_save_m2m:
            result = form.save()

        self.assertEqual(result, self.article)
        mock_save_article.assert_called_once_with(article=ANY, author=None)
        mock_save_m2m.assert_called_once()

        passed_article = mock_save_article.call_args.kwargs["article"]
        self.assertEqual(passed_article.pk, self.article.pk)
        self.assertEqual(passed_article.title, "a2")
        self.assertEqual(passed_article.preview_text, "preview2")
        self.assertEqual(passed_article.content, "content2")

    def test_save_with_commit_false_raises_error(self):
        form = ArticleModelForm(
            user=self.user,
            data={"title": "commit-false", "preview_text": "p", "content": "c"},
        )

        self.assertTrue(form.is_valid())

        with self.assertRaises(ValueError) as context:
            form.save(commit=False)

        self.assertFalse(Article.objects.filter(title="commit-false").exists())
        self.assertEqual(
            str(context.exception),
            "commit=False is not supported for ArticleModelForm.",
        )

    def test_save_persists_tags(self):
        form = ArticleModelForm(
            user=self.user,
            data={
                "title": "a2",
                "category": self.category.id,
                "tags": "tag1, tag2",
                "preview_text": "preview2",
                "content": "content2",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

        article = form.save()

        self.assertEqual(article.author, self.user)
        self.assertEqual(article.category, self.category)
        self.assertSetEqual(set(article.tags.names()), {"tag1", "tag2"})

    def test_core_fields_are_not_required(self):
        form = ArticleModelForm(instance=self.article)

        self.assertFalse(form.fields["title"].required)
        self.assertFalse(form.fields["preview_text"].required)
        self.assertFalse(form.fields["content"].required)

    def test_create_form_allows_blank_core_fields(self):
        form = ArticleModelForm(
            user=self.user,
            data={
                "title": "",
                "preview_text": "",
                "content": "",
            },
        )
        self.assertTrue(form.is_valid())

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

    def test_published_article_cannot_be_edited(self):
        self.article.status = ArticleStatus.PUBLISHED
        self.article.published_at = timezone.now()
        self.article.publish_sequence = 1
        self.article.save(update_fields=["status", "published_at", "publish_sequence"])

        form = ArticleModelForm(
            instance=self.article,
            data={
                "title": "updated title",
                "preview_text": "updated preview",
                "content": "updated content",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
        self.assertEqual(
            form.errors["__all__"],
            ["Published articles cannot be edited."],
        )

    def test_pending_review_article_cannot_be_edited(self):
        self.article.status = ArticleStatus.PENDING_REVIEW
        self.article.save(update_fields=["status"])

        form = ArticleModelForm(
            instance=self.article,
            data={
                "title": "updated title",
                "preview_text": "updated preview",
                "content": "updated content",
            },
        )

        self.assertTrue(form.fields["title"].disabled)
        self.assertTrue(form.fields["category"].disabled)
        self.assertTrue(form.fields["tags"].disabled)
        self.assertTrue(form.fields["preview_text"].disabled)
        self.assertTrue(form.fields["preview_image"].disabled)
        self.assertTrue(form.fields["content"].disabled)

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
        self.assertEqual(
            form.errors["__all__"],
            ["Withdraw the article from review before editing."],
        )

    @patch("articles.forms.save_article")
    def test_rejected_article_can_be_edited(self, mock_save_article):
        self.article.status = ArticleStatus.REJECTED
        self.article.review_note = "Fix grammar."
        self.article.save(update_fields=["status", "review_note"])
        mock_save_article.return_value = self.article

        form = ArticleModelForm(
            instance=self.article,
            data={
                "title": "updated title",
                "category": self.category.id,
                "tags": "tag1, tag2",
                "preview_text": "updated preview",
                "content": "updated content",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

        with patch.object(form, "_save_m2m") as mock_save_m2m:
            result = form.save()

        self.assertEqual(result, self.article)
        mock_save_article.assert_called_once_with(article=ANY, author=None)
        mock_save_m2m.assert_called_once()

        passed_article = mock_save_article.call_args.kwargs["article"]
        self.assertEqual(passed_article.pk, self.article.pk)
        self.assertEqual(passed_article.title, "updated title")
        self.assertEqual(passed_article.category, self.category)
        self.assertEqual(passed_article.preview_text, "updated preview")
        self.assertEqual(passed_article.content, "updated content")


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

    def test_anonymous_user(self):
        form = ArticleCommentForm(
            data={"text": "abc"},
            user=AnonymousUser(),
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

    def test_text_too_short(self):
        form = ArticleCommentForm(
            data={"text": "x"}, user=self.user, article=self.article
        )
        self.assertFalse(form.is_valid())
        self.assertIn("text", form.errors)

    def test_text_too_long(self):
        form = ArticleCommentForm(
            data={"text": "x" * (ARTICLE_COMMENT_MAX_LENGTH + 1)},
            user=self.user,
            article=self.article,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("text", form.errors)

    @patch("articles.forms.create_article_comment")
    def test_text_is_trimmed_before_save(self, mock_create_article_comment):
        comment = ArticleComment(
            text="abc",
            author=self.user,
            article=self.article,
        )
        mock_create_article_comment.return_value = comment

        form = ArticleCommentForm(
            data={"text": "  abc  "}, user=self.user, article=self.article
        )
        self.assertTrue(form.is_valid())
        form.save()

        mock_create_article_comment.assert_called_once_with(
            article=self.article, user=self.user, text="abc"
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
