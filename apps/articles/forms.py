from django import forms

from articles.models import Article, ArticleComment
from articles.services import _generate_unique_article_slug, create_article


class ArticleCreateForm(forms.ModelForm):
    preview_text = forms.TextInput()

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
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

    def save(self, **kwargs):
        super().save(commit=False, **kwargs)

        article = create_article(
            title=self.cleaned_data["title"],
            author=self.request.user,
            preview_text=self.cleaned_data["preview_text"],
            content=self.cleaned_data["content"],
            category=self.cleaned_data["category"],
            tags=self.cleaned_data["tags"],
            preview_image=self.cleaned_data["preview_image"],
        )
        return article


class ArticleUpdateForm(forms.ModelForm):
    preview_text = forms.TextInput()

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

    def save(self, **kwargs):
        instance = super().save(commit=False, **kwargs)
        instance.slug = _generate_unique_article_slug(instance.title)
        instance.save()
        self.save_m2m()
        return instance


class ArticleCommentForm(forms.ModelForm):
    class Meta:
        model = ArticleComment
        fields = ["text"]
