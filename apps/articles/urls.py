from django.urls import path

from articles import views


urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("articles/", views.ArticleListFilterView.as_view(), name="articles"),
    path(
        "category/<slug:category_slug>",
        views.ArticleCategoryView.as_view(),
        name="article-category",
    ),
    path("tag/<str:tag>", views.ArticleTagView.as_view(), name="article-tag"),
    path("articles/search", views.ArticleSearchView.as_view(), name="article-search"),
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
    path(
        "articles/<slug:article_slug>/like", views.ArticleLikeView.as_view(), name="article-like"
    ),
    path("comments/<int:comment_id>/like", views.CommentLikeView.as_view(), name="comment-like"),
]
