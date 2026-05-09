from django.urls import path

from articles import views


urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path(
        "tinymce/upload/",
        views.AttachedFileUploadView.as_view(),
        name="attached-file-upload",
    ),
    path(
        "articles/filter-tags-autocomplete/",
        views.ArticleTagAutocompleteView.as_view(),
        name="article-filter-tags-autocomplete",
    ),
    path(
        "articles/filter-authors-autocomplete/",
        views.ArticleAuthorAutocompleteView.as_view(),
        name="article-filter-authors-autocomplete",
    ),
    path("articles/", views.ArticleListFilterView.as_view(), name="articles"),
    path(
        "subscriptions/", views.SubscriptionFeedView.as_view(), name="subscription-feed"
    ),
    path("my-articles/", views.MyArticlesListView.as_view(), name="my-articles"),
    path(
        "articles/create-draft/",
        views.ArticleCreateDraftView.as_view(),
        name="article-create-draft",
    ),
    path(
        "articles/<slug:article_slug>/edit/",
        views.ArticleUpdateView.as_view(),
        name="article-update",
    ),
    path(
        "articles/<slug:article_slug>/withdraw-from-review/",
        views.ArticleWithdrawFromReviewView.as_view(),
        name="article-withdraw-from-review",
    ),
    path(
        "articles/<slug:article_slug>/delete/",
        views.ArticleDeleteView.as_view(),
        name="article-delete",
    ),
    path(
        "articles/<slug:article_slug>/",
        views.ArticleDetailView.as_view(),
        name="article-details",
    ),
    path(
        "articles/<slug:article_slug>/like/",
        views.ArticleLikeView.as_view(),
        name="article-like",
    ),
    path(
        "articles/<slug:article_slug>/comments/",
        views.ArticleCommentsListView.as_view(),
        name="article-comments-list",
    ),
    path(
        "comments/<int:comment_id>/like/",
        views.CommentLikeView.as_view(),
        name="comment-like",
    ),
]
