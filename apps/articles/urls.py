from django.urls import path

from . import views


urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("articles/<slug:article_slug>", views.ArticleDetailView.as_view(), name="article-details")
]
