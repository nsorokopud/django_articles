from django.urls import path

from . import views


urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("articles/create", views.ArticleCreateView.as_view(), name="article-create"),
    path(
        "articles/<slug:article_slug>/update",
        views.ArticleUpdateView.as_view(),
        name="article-update",
    ),
    path(
        "articles/<slug:article_slug>/delete",
        views.ArticleDeleteView.as_view(),
        name="article-delete",
    ),
    path(
        "articles/<slug:article_slug>", views.ArticleDetailView.as_view(), name="article-details"
    ),
    path(
        "articles/<slug:article_slug>/comment",
        views.ArticleCommentView.as_view(),
        name="article-comment",
    ),
]
