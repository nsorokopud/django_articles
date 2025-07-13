from django import forms
from django.core.exceptions import ValidationError

from core.exceptions import InvalidUpload
from core.validators import validate_uploaded_file

from .models import Article, ArticleComment


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

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk and (not self.user or not self.user.is_authenticated):
            raise ValidationError("A valid authenticated user is required.")
        return cleaned_data

    def save(self, commit=True) -> Article:
        instance = super().save(commit=False)
        if not instance.pk:
            instance.author = self.user
            instance.is_published = True
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class AttachedFileUploadForm(forms.Form):
    file = forms.FileField(error_messages={"required": "File is required."})

    def clean_file(self):
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

    def clean(self):
        cleaned_data = super().clean()
        if not self.user:
            raise ValidationError("User is required to save the comment.")
        if not self.article:
            raise ValidationError("Article is required to save the comment.")
        return cleaned_data

    def save(self, commit=True):
        comment = super().save(commit=False)
        comment.author = self.user
        comment.article = self.article
        if commit:
            comment.save()
        return comment
