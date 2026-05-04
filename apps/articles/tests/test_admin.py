from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
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

        self.change_article_permission = Permission.objects.get(
            codename="change_article"
        )
        self.review_article_permission = Permission.objects.get(
            codename="can_review_article"
        )

        self.editor_user = User.objects.create_user(
            username="editor", email="editor@test.com", is_staff=True
        )
        self.editor_user.user_permissions.add(self.change_article_permission)

        self.reviewer_user = User.objects.create_user(
            username="reviewer", email="reviewer@test.com", is_staff=True
        )
        self.reviewer_user.user_permissions.add(
            self.change_article_permission, self.review_article_permission
        )

    def _request(self, method="get", path="/admin/", user=None, data=None):
        request = getattr(self.factory, method)(path, data=data or {})
        request.user = user or self.admin_user

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

    def test_published_article_core_fields_are_readonly(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )
        request = self._request()

        readonly_fields = self.article_admin.get_readonly_fields(request, article)

        for field_name in (
            "title",
            "slug",
            "category",
            "tags",
            "preview_text",
            "preview_image",
            "content",
        ):
            self.assertIn(field_name, readonly_fields)

    def test_pending_review_article_core_fields_are_readonly(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request()

        readonly_fields = self.article_admin.get_readonly_fields(request, article)

        for field_name in (
            "title",
            "slug",
            "category",
            "tags",
            "preview_text",
            "preview_image",
            "content",
        ):
            self.assertIn(field_name, readonly_fields)

    def test_draft_article_core_fields_are_editable_except_author(self):
        article = self._article(status=ArticleStatus.DRAFT)
        request = self._request()

        readonly_fields = self.article_admin.get_readonly_fields(request, article)

        for field_name in (
            "title",
            "slug",
            "category",
            "tags",
            "preview_text",
            "preview_image",
            "content",
        ):
            self.assertNotIn(field_name, readonly_fields)

        self.assertIn("author", readonly_fields)

    def test_save_model_denies_direct_edit_for_published_article(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )
        article.title = "Changed title"

        request = self._request()

        with self.assertRaises(PermissionDenied):
            self.article_admin.save_model(request, article, form=None, change=True)

        article.refresh_from_db()
        self.assertEqual(article.title, "Test article")
        self.assertEqual(article.status, ArticleStatus.PUBLISHED)

    def test_save_model_denies_direct_edit_for_pending_review_article(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        article.title = "Changed title"

        request = self._request()

        with self.assertRaises(PermissionDenied):
            self.article_admin.save_model(request, article, form=None, change=True)

        article.refresh_from_db()
        self.assertEqual(article.title, "Test article")
        self.assertEqual(article.status, ArticleStatus.PENDING_REVIEW)

    def test_save_model_updates_content_text_through_save_article_service(self):
        article = self._article(content="<p>Old body</p>", content_text="Old body")

        article.content = "<p>New searchable body</p>"

        request = self._request()
        self.article_admin.save_model(request, article, form=None, change=True)

        article.refresh_from_db()

        self.assertIn("New searchable body", article.content_text)

    def test_admin_change_view_saves_tags_for_draft_article(self):
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

    def test_change_view_adds_review_permission_to_context_for_reviewer(self):
        self.client.force_login(self.reviewer_user)
        article = self._article(status=ArticleStatus.PENDING_REVIEW)

        response = self.client.get(
            reverse("admin:articles_article_change", args=[article.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_review_article"])

    def test_change_view_adds_false_review_permission_to_context_for_editor(self):
        self.client.force_login(self.editor_user)
        article = self._article(status=ArticleStatus.PENDING_REVIEW)

        response = self.client.get(
            reverse("admin:articles_article_change", args=[article.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_review_article"])

    def test_change_view_hides_save_buttons_for_published_article(self):
        self.client.force_login(self.admin_user)
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=20,
        )

        response = self.client.get(
            reverse("admin:articles_article_change", args=[article.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["show_save"])
        self.assertFalse(response.context["show_save_and_continue"])
        self.assertFalse(response.context["show_save_and_add_another"])
        self.assertFalse(response.context["show_save_as_new"])

    def test_change_view_hides_save_buttons_for_pending_review_article(self):
        self.client.force_login(self.admin_user)
        article = self._article(status=ArticleStatus.PENDING_REVIEW)

        response = self.client.get(
            reverse("admin:articles_article_change", args=[article.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["show_save"])
        self.assertFalse(response.context["show_save_and_continue"])
        self.assertFalse(response.context["show_save_and_add_another"])
        self.assertFalse(response.context["show_save_as_new"])

    def test_change_view_shows_save_buttons_for_draft_article(self):
        self.client.force_login(self.admin_user)
        article = self._article(status=ArticleStatus.DRAFT)

        response = self.client.get(
            reverse("admin:articles_article_change", args=[article.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_save"])
        self.assertTrue(response.context["show_save_and_continue"])
        self.assertTrue(response.context["show_save_and_add_another"])
        self.assertFalse(response.context["show_save_as_new"])

    def test_change_form_shows_workflow_buttons_for_reviewer(self):
        self.client.force_login(self.reviewer_user)
        article = self._article(status=ArticleStatus.PENDING_REVIEW)

        response = self.client.get(
            reverse("admin:articles_article_change", args=[article.pk])
        )

        self.assertContains(response, "Publish")
        self.assertContains(response, "Reject")
        self.assertContains(
            response, reverse("admin:articles_article_publish", args=[article.pk])
        )
        self.assertContains(
            response, reverse("admin:articles_article_reject", args=[article.pk])
        )

    def test_change_form_hides_workflow_buttons_without_review_permission(self):
        self.client.force_login(self.editor_user)
        article = self._article(status=ArticleStatus.PENDING_REVIEW)

        response = self.client.get(
            reverse("admin:articles_article_change", args=[article.pk])
        )

        self.assertNotContains(
            response, reverse("admin:articles_article_publish", args=[article.pk])
        )
        self.assertNotContains(
            response, reverse("admin:articles_article_reject", args=[article.pk])
        )

    def test_change_form_shows_unpublish_button_for_published_article_reviewer(self):
        self.client.force_login(self.reviewer_user)
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=20,
        )

        response = self.client.get(
            reverse("admin:articles_article_change", args=[article.pk])
        )

        self.assertContains(response, "Unpublish")
        self.assertContains(
            response, reverse("admin:articles_article_unpublish", args=[article.pk])
        )

    def test_get_actions_hides_workflow_actions_without_review_permission(self):
        request = self._request(user=self.editor_user)

        actions = self.article_admin.get_actions(request)

        self.assertNotIn("publish", actions)
        self.assertNotIn("unpublish", actions)

    def test_get_actions_keeps_workflow_actions_with_review_permission(self):
        request = self._request(user=self.reviewer_user)

        actions = self.article_admin.get_actions(request)

        self.assertIn("publish", actions)
        self.assertIn("unpublish", actions)

    def test_require_review_permission_allows_reviewer(self):
        request = self._request(user=self.reviewer_user)

        self.article_admin._require_review_permission(request)

    def test_require_review_permission_denies_editor_without_review_permission(self):
        request = self._request(user=self.editor_user)

        with self.assertRaises(PermissionDenied):
            self.article_admin._require_review_permission(request)

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

    def test_process_publish_get_requires_review_permission(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request("get", user=self.editor_user)

        with self.assertRaises(PermissionDenied):
            self.article_admin.process_publish(request, article.pk)

    @patch("articles.admin.publish_article")
    def test_process_publish_post_calls_service_and_redirects(self, mock_publish):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request("post")

        response = self.article_admin.process_publish(request, article.pk)

        mock_publish.assert_called_once_with(
            article_id=article.id, reviewer=self.admin_user
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

    def test_process_unpublish_get_requires_review_permission(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=30,
        )
        request = self._request("get", user=self.editor_user)

        with self.assertRaises(PermissionDenied):
            self.article_admin.process_unpublish(request, article.pk)

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

    def test_process_reject_get_requires_review_permission(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request("get", user=self.editor_user)

        with self.assertRaises(PermissionDenied):
            self.article_admin.process_reject(request, article.pk)

    def test_process_reject_post_invalid_form_rerenders_confirmation(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request("post", user=self.admin_user, data={"reason": "short"})

        response = self.article_admin.process_reject(request, article.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["action"], "reject")
        self.assertTrue(response.context_data["form"].errors)

    @patch("articles.admin.reject_article")
    def test_process_reject_post_calls_service_and_redirects(self, mock_reject):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request(
            "post",
            user=self.admin_user,
            data={"reason": "This article needs a clearer introduction."},
        )

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

    @patch("articles.admin.publish_article")
    def test_publish_action_requires_review_permission(self, mock_publish):
        article = self._article(slug="article-1")
        request = self._request("post", user=self.editor_user)

        with self.assertRaises(PermissionDenied):
            self.article_admin.publish(request, Article.objects.filter(pk=article.pk))

        mock_publish.assert_not_called()

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

    @patch("articles.admin.unpublish_article")
    def test_unpublish_action_requires_review_permission(self, mock_unpublish):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=101,
        )
        request = self._request("post", user=self.editor_user)

        with self.assertRaises(PermissionDenied):
            self.article_admin.unpublish(request, Article.objects.filter(pk=article.pk))

        mock_unpublish.assert_not_called()

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
            request, Article.objects.filter(pk__in=[article_1.pk, article_2.pk])
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

    def test_get_prepopulated_fields_for_new_article(self):
        request = self._request()

        result = self.article_admin.get_prepopulated_fields(request, None)
        self.assertEqual(result, {"slug": ("title",)})

    def test_get_prepopulated_fields_for_draft_article(self):
        article = self._article(status=ArticleStatus.DRAFT)
        request = self._request()

        result = self.article_admin.get_prepopulated_fields(request, article)
        self.assertEqual(result, {"slug": ("title",)})

    def test_get_prepopulated_fields_for_rejected_article(self):
        article = self._article(status=ArticleStatus.REJECTED)
        request = self._request()

        result = self.article_admin.get_prepopulated_fields(request, article)
        self.assertEqual(result, {"slug": ("title",)})

    def test_get_prepopulated_fields_for_published_article_is_empty(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=999,
        )
        request = self._request()

        result = self.article_admin.get_prepopulated_fields(request, article)
        self.assertEqual(result, {})

    def test_get_prepopulated_fields_for_pending_review_article_is_empty(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request()

        result = self.article_admin.get_prepopulated_fields(request, article)
        self.assertEqual(result, {})

    def test_slug_is_readonly_for_published_article(self):
        article = self._article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=999,
        )
        request = self._request()

        readonly_fields = self.article_admin.get_readonly_fields(request, article)
        self.assertIn("slug", readonly_fields)

    def test_slug_is_readonly_for_pending_review_article(self):
        article = self._article(status=ArticleStatus.PENDING_REVIEW)
        request = self._request()

        readonly_fields = self.article_admin.get_readonly_fields(request, article)
        self.assertIn("slug", readonly_fields)

    def test_slug_is_not_readonly_for_draft_article(self):
        article = self._article(status=ArticleStatus.DRAFT)
        request = self._request()

        readonly_fields = self.article_admin.get_readonly_fields(request, article)
        self.assertNotIn("slug", readonly_fields)


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

    def test_has_delete_permission_is_true_for_draft(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user

        self.assertTrue(self.inline.has_delete_permission(request, self.article))

    def test_has_delete_permission_is_false_for_published(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        self.article.status = ArticleStatus.PUBLISHED

        self.assertFalse(self.inline.has_delete_permission(request, self.article))

    def test_has_delete_permission_is_false_for_pending_review(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        self.article.status = ArticleStatus.PENDING_REVIEW

        self.assertFalse(self.inline.has_delete_permission(request, self.article))


class TestArticleCommentAdmin(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com"
        )
        self.client.force_login(self.admin_user)

        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.article = Article.objects.create(
            title="Article",
            slug="article",
            author=self.author,
            preview_text="Preview",
            content="<p>Body</p>",
            content_text="Body",
            status=ArticleStatus.DRAFT,
        )
        self.comment = ArticleComment.objects.create(
            article=self.article, author=self.author, text="Comment"
        )

    def test_article_comment_admin_disallows_add(self):
        url = reverse("admin:articles_articlecomment_add")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_article_comment_admin_does_not_show_save_as(self):
        url = reverse("admin:articles_articlecomment_change", args=[self.comment.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_saveasnew"')
