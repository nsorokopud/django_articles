from django.contrib import admin

from articles.models import Article, ArticleCategory, ArticleComment


admin.site.register(Article)
admin.site.register(ArticleCategory)
admin.site.register(ArticleComment)
