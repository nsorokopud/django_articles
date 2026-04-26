from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from articles.admin import ArticleAdmin, CommentInline
from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus


User = get_user_model()


class TestArticleAdmin(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.article_admin = ArticleAdmin(Article, self.site)

        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com"
        )
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.category = ArticleCategory.objects.create(title="Cat", slug="cat")

    def _request(self, method="get", path="/admin/"):
        request = getattr(self.factory, method)(path)
        request.user = self.admin_user

        setattr(request, "session", self.client.session)
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        return request

    def _article(self, **overrides):
        data = {
            "title": "Test article",
            "slug": "test-article",
            "category": self.category,
            "author": self.author,
            "preview_text": "Preview text",
            "content": "<p>Article body</p>",
            "content_text": "Article body",
            "status": ArticleStatus.DRAFT,
        }
        data.update(overrides)
        return Article.objects.create(**data)

    def test_existing_article_author_is_readonly(self):
        article = self._article()
        request = self._request()

        readonly_fields = self.article_admin.get_readonly_fields(request, article)

        self.assertIn("author", readonly_fields)

    def test_new_article_author_is_not_readonly(self):
        request = self._request()

        readonly_fields = self.article_admin.get_readonly_fields(request, None)

        self.assertNotIn("author", readonly_fields)

    def test_save_model_preserves_workflow_fields_on_regular_admin_save(self):
        published_at = timezone.now()
        reviewed_at = timezone.now()

        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=published_at,
            publish_sequence=123,
            reviewed_at=reviewed_at,
            reviewed_by=self.admin_user,
            review_note="Original review note",
        )

        article.title = "Changed title"
        article.status = ArticleStatus.DRAFT
        article.published_at = None
        article.publish_sequence = None
        article.reviewed_at = None
        article.reviewed_by = None
        article.review_note = ""

        request = self._request()
        self.article_admin.save_model(request, article, form=None, change=True)

        article.refresh_from_db()

        self.assertEqual(article.title, "Changed title")
        self.assertEqual(article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(article.published_at, published_at)
        self.assertEqual(article.publish_sequence, 123)
        self.assertEqual(article.reviewed_at, reviewed_at)
        self.assertEqual(article.reviewed_by, self.admin_user)
        self.assertEqual(article.review_note, "Original review note")

    def test_save_model_updates_content_text_through_save_article_service(self):
        article = self._article(content="<p>Old body</p>", content_text="Old body")

        article.content = "<p>New searchable body</p>"

        request = self._request()
        self.article_admin.save_model(request, article, form=None, change=True)

        article.refresh_from_db()

        self.assertIn("New searchable body", article.content_text)

    def test_admin_change_view_saves_tags(self):
        self.client.force_login(self.admin_user)

        article = self._article()
        url = reverse("admin:articles_article_change", args=[article.pk])

        response = self.client.post(
            url,
            {
                "title": article.title,
                "slug": article.slug,
                "category": self.category.pk,
                "author": self.author.pk,
                "preview_text": article.preview_text,
                "content": article.content,
                "tags": "django, postgres",
                "articlecomment_set-TOTAL_FORMS": "0",
                "articlecomment_set-INITIAL_FORMS": "0",
                "articlecomment_set-MIN_NUM_FORMS": "0",
                "articlecomment_set-MAX_NUM_FORMS": "1000",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)

        article.refresh_from_db()
        self.assertEqual(set(article.tags.names()), {"django", "postgres"})

    def test_pub_seq_returns_dash_when_empty(self):
        article = self._article(publish_sequence=None)

        self.assertEqual(self.article_admin.pub_seq(article), "-")

    def test_pub_seq_returns_publish_sequence(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=10,
        )

        self.assertEqual(self.article_admin.pub_seq(article), 10)

    def test_workflow_buttons_for_unsaved_article(self):
        article = Article(title="Unsaved")

        result = self.article_admin.workflow_buttons(article)

        self.assertEqual(result, "Save the article first to use workflow actions.")

    def test_workflow_buttons_for_draft_article(self):
        article = self._article(status=ArticleStatus.DRAFT)

        result = self.article_admin.workflow_buttons(article)

        self.assertEqual(result, "-")

    def test_workflow_buttons_for_pending_review_article(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)

        result = str(self.article_admin.workflow_buttons(article))

        self.assertIn("Publish", result)
        self.assertIn("Reject", result)
        self.assertIn(
            reverse("admin:articles_article_publish", args=[article.pk]), result
        )
        self.assertIn(
            reverse("admin:articles_article_reject", args=[article.pk]), result
        )

    def test_workflow_buttons_for_published_article(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=20,
        )

        result = str(self.article_admin.workflow_buttons(article))

        self.assertIn("Unpublish", result)
        self.assertIn(
            reverse("admin:articles_article_unpublish", args=[article.pk]), result
        )

    def test_get_article_or_404_raises_404_for_missing_article(self):
        request = self._request()

        with self.assertRaises(Http404):
            self.article_admin._get_article_or_404(request, 999999)

    def test_get_article_or_404_raises_permission_denied_without_change_permission(
        self,
    ):
        article = self._article()
        request = self._request()

        with patch.object(
            self.article_admin, "has_change_permission", return_value=False
        ):
            with self.assertRaises(PermissionDenied):
                self.article_admin._get_article_or_404(request, article.pk)

    def test_process_publish_get_renders_confirmation(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request("get")

        response = self.article_admin.process_publish(request, article.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.template_name, "articles/admin/workflow_confirm.html")
        self.assertEqual(response.context_data["action"], "publish")
        self.assertEqual(response.context_data["confirm_label"], "Publish")

    @patch("articles.admin.publish_article")
    def test_process_publish_post_calls_service_and_redirects(self, mock_publish):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request("post")

        response = self.article_admin.process_publish(request, article.pk)

        mock_publish.assert_called_once_with(
            article_id=article.id, actor=self.admin_user
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("admin:articles_article_change", args=[article.pk])
        )

    @patch("articles.admin.publish_article", side_effect=ValueError("Not ready"))
    def test_process_publish_post_handles_service_error(self, mock_publish):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request("post")

        response = self.article_admin.process_publish(request, article.pk)

        self.assertEqual(response.status_code, 302)
        mock_publish.assert_called_once()

    def test_process_unpublish_get_renders_confirmation(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=30,
        )
        request = self._request("get")

        response = self.article_admin.process_unpublish(request, article.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["action"], "unpublish")
        self.assertEqual(response.context_data["confirm_label"], "Unpublish")

    @patch("articles.admin.unpublish_article")
    def test_process_unpublish_post_calls_service_and_redirects(self, mock_unpublish):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=40,
        )
        request = self._request("post")

        response = self.article_admin.process_unpublish(request, article.pk)

        mock_unpublish.assert_called_once_with(
            article_id=article.id, actor=self.admin_user
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("admin:articles_article_change", args=[article.pk])
        )

    def test_process_reject_get_renders_confirmation_with_form(self):
        article = self._article(
            status=ArticleStatus.PENDING_REVIEW, review_note="Needs more detail"
        )
        request = self._request("get")

        response = self.article_admin.process_reject(request, article.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["action"], "reject")
        self.assertEqual(response.context_data["confirm_label"], "Reject")
        self.assertEqual(
            response.context_data["form"].initial["reason"], "Needs more detail"
        )

    def test_process_reject_post_invalid_form_rerenders_confirmation(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self.factory.post("/admin/", {"reason": "short"})
        request.user = self.admin_user
        setattr(request, "session", self.client.session)
        setattr(request, "_messages", FallbackStorage(request))

        response = self.article_admin.process_reject(request, article.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["action"], "reject")
        self.assertTrue(response.context_data["form"].errors)

    @patch("articles.admin.reject_article")
    def test_process_reject_post_calls_service_and_redirects(self, mock_reject):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self.factory.post(
            "/admin/", {"reason": "This article needs a clearer introduction."}
        )
        request.user = self.admin_user
        setattr(request, "session", self.client.session)
        setattr(request, "_messages", FallbackStorage(request))

        response = self.article_admin.process_reject(request, article.pk)

        mock_reject.assert_called_once_with(
            article_id=article.id,
            reason="This article needs a clearer introduction.",
            reviewer=self.admin_user,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("admin:articles_article_change", args=[article.pk])
        )

    @patch("articles.admin.publish_article")
    def test_publish_action_calls_service_for_each_article(self, mock_publish):
        article_1 = self._article(slug="article-1")
        article_2 = self._article(slug="article-2")
        request = self._request("post")

        self.article_admin.publish(
            request, Article.objects.filter(pk__in=[article_1.pk, article_2.pk])
        )

        self.assertEqual(mock_publish.call_count, 2)

    @patch("articles.admin.unpublish_article")
    def test_unpublish_action_calls_service_for_each_article(self, mock_unpublish):
        article_1 = self._article(
            slug="article-1",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=101,
        )
        article_2 = self._article(
            slug="article-2",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=102,
        )
        request = self._request("post")

        self.article_admin.unpublish(
            request, Article.objects.filter(pk__in=[article_1.pk, article_2.pk])
        )

        self.assertEqual(mock_unpublish.call_count, 2)

    @patch("articles.admin.delete_article")
    def test_delete_model_calls_delete_service(self, mock_delete):
        article = self._article()
        request = self._request("post")

        self.article_admin.delete_model(request, article)

        mock_delete.assert_called_once_with(article_id=article.id)

    @patch("articles.admin.delete_article", side_effect=ValueError("Cannot delete"))
    def test_delete_model_raises_permission_denied_on_service_error(self, mock_delete):
        article = self._article()
        request = self._request("post")

        with self.assertRaises(PermissionDenied):
            self.article_admin.delete_model(request, article)

        mock_delete.assert_called_once_with(article_id=article.id)

    def test_has_delete_permission_false_for_published_article(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=999,
        )
        request = self._request()

        self.assertFalse(self.article_admin.has_delete_permission(request, article))

    def test_has_delete_permission_false_for_pending_review_article(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request()

        self.assertFalse(self.article_admin.has_delete_permission(request, article))

    def test_has_delete_permission_true_for_draft_article(self):
        article = self._article(status=ArticleStatus.DRAFT)
        request = self._request()

        self.assertTrue(self.article_admin.has_delete_permission(request, article))

    @patch("articles.admin.delete_article")
    def test_delete_queryset_calls_delete_service_for_each_article(self, mock_delete):
        article_1 = self._article(slug="delete-1")
        article_2 = self._article(slug="delete-2")
        request = self._request("post")

        self.article_admin.delete_queryset(
            request,
            Article.objects.filter(pk__in=[article_1.pk, article_2.pk]),
        )

        self.assertEqual(mock_delete.call_count, 2)
        mock_delete.assert_any_call(article_id=article_1.id)
        mock_delete.assert_any_call(article_id=article_2.id)

    @patch("articles.admin.delete_article")
    def test_delete_queryset_reports_partial_failures(self, mock_delete):
        article_1 = self._article(slug="delete-ok")
        article_2 = self._article(slug="delete-fail")

        mock_delete.side_effect = [
            None,
            ValueError("published or pending-review articles cannot be deleted"),
        ]

        request = self._request("post")

        self.article_admin.delete_queryset(
            request,
            Article.objects.filter(pk__in=[article_1.pk, article_2.pk]).order_by("pk"),
        )

        messages_list = [str(m) for m in get_messages(request)]

        self.assertEqual(mock_delete.call_count, 2)
        self.assertTrue(any("1 article was deleted" in msg for msg in messages_list))
        self.assertTrue(
            any("1 selected article was not deleted" in msg for msg in messages_list)
        )
        self.assertTrue(any(f"#{article_2.id}" in msg for msg in messages_list))


class TestCommentInlineAdmin(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.inline = CommentInline(Article, self.site)

        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com"
        )
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.liker = User.objects.create_user(username="liker", email="liker@test.com")
        self.article = Article.objects.create(
            title="Article",
            slug="article",
            author=self.author,
            preview_text="Preview",
            content="<p>Body</p>",
            content_text="Body",
            status=ArticleStatus.DRAFT,
        )

    def test_has_add_permission_is_false(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user

        self.assertFalse(self.inline.has_add_permission(request, self.article))

    def test_get_queryset_annotates_likes_count(self):
        comment = ArticleComment.objects.create(
            article=self.article, author=self.author, text="Nice article"
        )
        comment.users_that_liked.add(self.liker)

        request = self.factory.get("/admin/")
        request.user = self.admin_user

        queryset = self.inline.get_queryset(request)
        annotated_comment = queryset.get(pk=comment.pk)

        self.assertEqual(annotated_comment._likes_count, 1)
        self.assertEqual(self.inline.likes_count(annotated_comment), 1)

    def test_likes_count_defaults_to_zero_without_annotation(self):
        comment = ArticleComment.objects.create(
            article=self.article, author=self.author, text="Nice article"
        )

        self.assertEqual(self.inline.likes_count(comment), 0)
