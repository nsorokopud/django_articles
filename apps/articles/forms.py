from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from core.exceptions import InvalidUpload
from core.validators import validate_uploaded_file

from .models import Article, ArticleComment, ArticleStatus
from .services.articles import save_article
from .services.comments import create_article_comment


ARTICLE_REJECT_REASON_MIN_LENGTH = 10
ARTICLE_REJECT_REASON_MAX_LENGTH = 2000
ARTICLE_TITLE_SLUG_HELP = (
    "Changing the title may update the article URL until publication."
)

ARTICLE_COMMENT_MIN_LENGTH = 3
ARTICLE_COMMENT_MAX_LENGTH = 2000


class ArticleAdminForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = (
            "title",
            "slug",
            "category",
            "tags",
            "author",
            "preview_text",
            "preview_image",
            "content",
        )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        slug_field = self.fields.get("slug")
        if not slug_field:
            return

        slug_field.required = False

        instance = getattr(self, "instance", None)
        if (
            not instance
            or not instance.pk
            or instance.status in {ArticleStatus.DRAFT, ArticleStatus.REJECTED}
        ):
            slug_field.help_text = (
                "Leave blank to automatically generate a new slug from the title."
            )


class ArticleRejectAdminForm(forms.Form):
    reason = forms.CharField(
        label="Rejection reason",
        required=True,
        max_length=ARTICLE_REJECT_REASON_MAX_LENGTH,
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": "Explain what should be fixed before resubmission.",
            }
        ),
        help_text="This note will be shown to the article author.",
    )

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()

        if len(reason) < ARTICLE_REJECT_REASON_MIN_LENGTH:
            raise forms.ValidationError(
                "Please provide a more detailed explanation "
                f"(at least {ARTICLE_REJECT_REASON_MIN_LENGTH} characters)."
            )

        return reason


class ArticleModelForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = [
            "title",
            "category",
            "tags",
            "preview_text",
            "preview_image",
            "content",
        ]

    def __init__(self, *args, **kwargs) -> None:
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["title"].required = False
        self.fields["preview_text"].required = False
        self.fields["content"].required = False

        if not self.instance.pk or self.instance.status in {
            ArticleStatus.DRAFT,
            ArticleStatus.REJECTED,
        }:
            existing_help = self.fields["title"].help_text or ""
            self.fields["title"].help_text = (
                f"{existing_help} {ARTICLE_TITLE_SLUG_HELP}".strip()
            )

        if self.instance.pk and self.instance.status == ArticleStatus.PENDING_REVIEW:
            for field in self.fields.values():
                field.disabled = True

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()

        if not self.instance.pk and (not self.user or not self.user.is_authenticated):
            raise ValidationError("A valid authenticated user is required.")

        if self.instance.pk:
            if self.instance.status == ArticleStatus.PUBLISHED:
                raise ValidationError("Published articles cannot be edited.")

            if self.instance.status == ArticleStatus.PENDING_REVIEW:
                raise ValidationError(
                    "Withdraw the article from review before editing."
                )

        return cleaned_data

    def save(self, commit=True) -> Article:
        if not commit:
            raise ValueError("commit=False is not supported for ArticleModelForm.")

        instance = super().save(commit=False)
        author = self.user if instance.pk is None else None

        article = save_article(article=instance, author=author)
        self.save_m2m()

        return article


class AttachedFileUploadForm(forms.Form):
    file = forms.FileField(error_messages={"required": "File is required."})

    def clean_file(self) -> Any:
        uploaded_file = self.cleaned_data["file"]
        try:
            validate_uploaded_file(uploaded_file)
        except InvalidUpload as e:
            raise ValidationError(str(e)) from e
        return uploaded_file


class ArticleCommentForm(forms.ModelForm):
    class Meta:
        model = ArticleComment
        fields = ["text"]
        labels = {
            "text": "",
        }
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "maxlength": ARTICLE_COMMENT_MAX_LENGTH,
                    "rows": 4,
                    "placeholder": "Write your comment...",
                }
            )
        }

    def __init__(self, *args, user=None, article=None, **kwargs) -> None:
        self.user = user
        self.article = article
        super().__init__(*args, **kwargs)

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if not self.user or not self.user.is_authenticated:
            raise ValidationError("User is required to save the comment.")
        if not self.article:
            raise ValidationError("Article is required to save the comment.")
        return cleaned_data

    def clean_text(self) -> str:
        text = (self.cleaned_data.get("text") or "").strip()

        if len(text) < ARTICLE_COMMENT_MIN_LENGTH:
            raise ValidationError(
                f"Comment must be at least {ARTICLE_COMMENT_MIN_LENGTH} "
                "characters long."
            )

        if len(text) > ARTICLE_COMMENT_MAX_LENGTH:
            raise ValidationError(
                f"Comment cannot exceed {ARTICLE_COMMENT_MAX_LENGTH} characters."
            )

        return text

    def save(self, commit=True) -> ArticleComment:
        if not commit:
            raise ValueError("ArticleCommentForm.save(commit=False) is not supported.")

        return create_article_comment(
            article=self.article,
            user=self.user,
            text=self.cleaned_data["text"],
        )
