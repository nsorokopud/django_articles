from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from core.exceptions import InvalidUpload
from core.validators import validate_uploaded_file

from .models import Article, ArticleComment
from .services.articles import save_article
from .services.comments import create_article_comment


class ArticleAdminForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = "__all__"
        help_texts = {
            "slug": "Leave blank to automatically generate a new slug from the title.",
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


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

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if not self.instance.pk and (not self.user or not self.user.is_authenticated):
            raise ValidationError("A valid authenticated user is required.")
        return cleaned_data

    def save(self, commit=True, *, publish=False) -> Article:
        instance = super().save(commit=False)

        if not commit:
            return instance

        author = self.user if instance.pk is None else None

        return save_article(
            article=instance,
            author=author,
            save_m2m=self.save_m2m,
            publish=publish,
        )


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

    def __init__(self, *args, user=None, article=None, **kwargs) -> None:
        self.user = user
        self.article = article
        super().__init__(*args, **kwargs)

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if not self.user:
            raise ValidationError("User is required to save the comment.")
        if not self.article:
            raise ValidationError("Article is required to save the comment.")
        return cleaned_data

    def save(self, commit=True) -> ArticleComment:
        if not commit:
            raise ValueError("ArticleCommentForm.save(commit=False) is not supported.")

        return create_article_comment(
            article=self.article,
            user=self.user,
            text=self.cleaned_data["text"],
        )
