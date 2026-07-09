from django.urls import path

from articles.views.articles import (
    ArticleCreateDraftView,
    ArticleDeleteView,
    ArticleDetailView,
    ArticleLikeView,
    ArticleListFilterView,
    ArticleUpdateView,
    ArticleWithdrawFromReviewView,
    HomePageView,
    MyArticlesListView,
    SubscriptionFeedView,
)
from articles.views.autocomplete import (
    ArticleAuthorAutocompleteView,
    ArticleTagAutocompleteView,
)
from articles.views.comments import ArticleCommentsListView, CommentLikeView
from articles.views.uploads import AttachedFileUploadView


urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path(
        "tinymce/upload/",
        AttachedFileUploadView.as_view(),
        name="attached-file-upload",
    ),
    path(
        "articles/filter-tags-autocomplete/",
        ArticleTagAutocompleteView.as_view(),
        name="article-filter-tags-autocomplete",
    ),
    path(
        "articles/filter-authors-autocomplete/",
        ArticleAuthorAutocompleteView.as_view(),
        name="article-filter-authors-autocomplete",
    ),
    path("articles/", ArticleListFilterView.as_view(), name="articles"),
    path("subscriptions/", SubscriptionFeedView.as_view(), name="subscription-feed"),
    path("my-articles/", MyArticlesListView.as_view(), name="my-articles"),
    path(
        "articles/create-draft/",
        ArticleCreateDraftView.as_view(),
        name="article-create-draft",
    ),
    path(
        "articles/<int:pk>/edit/",
        ArticleUpdateView.as_view(),
        name="article-update",
    ),
    path(
        "articles/<int:pk>/withdraw-from-review/",
        ArticleWithdrawFromReviewView.as_view(),
        name="article-withdraw-from-review",
    ),
    path(
        "articles/<int:pk>/delete/",
        ArticleDeleteView.as_view(),
        name="article-delete",
    ),
    path(
        "articles/<slug:article_slug>/like/",
        ArticleLikeView.as_view(),
        name="article-like",
    ),
    path(
        "articles/<slug:article_slug>/comments/",
        ArticleCommentsListView.as_view(),
        name="article-comments-list",
    ),
    path(
        "articles/<slug:article_slug>/",
        ArticleDetailView.as_view(),
        name="article-details",
    ),
    path(
        "comments/<int:comment_id>/like/",
        CommentLikeView.as_view(),
        name="comment-like",
    ),
]
