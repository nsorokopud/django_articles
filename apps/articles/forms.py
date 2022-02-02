from django import forms

from .models import Article
from .services import create_article


class ArticleCreateForm(forms.ModelForm):
    preview_text = forms.TextInput()

    class Meta:
        model = Article
        fields = ["title", "category", "tags", "preview_text", "preview_image", "content"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super(ArticleCreateForm, self).__init__(*args, **kwargs)

    def save(self, **kwargs):
        super(ArticleCreateForm, self).save(commit=False, **kwargs)

        article = create_article(
            self.cleaned_data["title"],
            self.cleaned_data["category"],
            self.request.user,
            self.cleaned_data["preview_text"],
            self.cleaned_data["content"],
            self.cleaned_data["tags"],
            self.cleaned_data["preview_image"],
        )
        return article
