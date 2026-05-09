from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleStatus
from config.settings import CACHES
from users.models import User


class TestArticleUpdateView(TestCase):
    def setUp(self):
        self.client = Client()

        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com"
        )

        self.category = ArticleCategory.objects.create(title="cat1", slug="cat1")
        self.other_category = ArticleCategory.objects.create(title="cat2", slug="cat2")

        self.published_article = Article.objects.create(
            title="article",
            slug="test-article",
            category=self.category,
            author=self.author,
            preview_text="text1",
            content="content1",
            content_text="content1",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )
        self.published_article.tags.add("tag1")

        self.draft_article = Article.objects.create(
            title="draft article",
            slug="draft-article",
            category=self.category,
            author=self.author,
            preview_text="draft text",
            content="draft content",
            content_text="draft content",
        )
        self.draft_article.tags.add("draft-tag")

        self.published_url = reverse(
            "article-update", kwargs={"article_slug": self.published_article.slug}
        )
        self.draft_url = reverse(
            "article-update", kwargs={"article_slug": self.draft_article.slug}
        )

    def test_get_anonymous_user_redirects_to_login(self):
        redirect_url = f"{reverse('login')}?next={self.draft_url}"
        response = self.client.get(self.draft_url)
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_get_not_author_returns_404(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.published_url)
        self.assertEqual(response.status_code, 404)

    def test_get_non_existent_article_returns_404(self):
        self.client.force_login(self.author)
        url = reverse("article-update", kwargs={"article_slug": "non-existent-article"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_get_form_disabled_for_pending_review_article(self):
        self.draft_article.status = ArticleStatus.PENDING_REVIEW
        self.draft_article.save(update_fields=["status"])

        self.client.force_login(self.author)
        response = self.client.get(self.draft_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_form.html")
        self.assertEqual(response.context["object"], self.draft_article)
        self.assertTrue(response.context["update"])

        form = response.context["form"]
        self.assertTrue(form.fields["title"].disabled)
        self.assertTrue(form.fields["category"].disabled)
        self.assertTrue(form.fields["tags"].disabled)
        self.assertTrue(form.fields["preview_text"].disabled)
        self.assertTrue(form.fields["preview_image"].disabled)
        self.assertTrue(form.fields["content"].disabled)

    @override_settings(CACHES=CACHES)
    def test_get_for_published_article_redirects_to_detail_page(self):
        redirect_url = reverse(
            "article-details", kwargs={"article_slug": self.published_article.slug}
        )
        self.client.force_login(self.author)
        response = self.client.get(self.published_url)

        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_get_correct_for_draft_article(self):
        self.client.force_login(self.author)
        response = self.client.get(self.draft_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_form.html")
        self.assertEqual(response.context["object"], self.draft_article)
        self.assertTrue(response.context["update"])

    @override_settings(
        MEDIA_URL="/media/",
        MEDIA_ALLOWED_ROOT_URLS=[
            "https://cdn.test.com/media",
            "https://media.test.com/uploads/",
            "",
            "   ",
        ],
    )
    def test_get_draft_includes_media_allowed_root_urls(self):
        self.client.force_login(self.author)

        response = self.client.get(self.draft_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["media_allowed_root_urls"],
            [
                "https://cdn.test.com/media/",
                "https://media.test.com/uploads/",
            ],
        )

    @override_settings(
        MEDIA_URL="/media/",
        MEDIA_ALLOWED_ROOT_URLS=["https://cdn.test.com/media/"],
    )
    def test_get_pending_review_does_not_render_media_allowed_root_urls_script(self):
        self.draft_article.status = ArticleStatus.PENDING_REVIEW
        self.draft_article.save(update_fields=["status"])

        self.client.force_login(self.author)
        response = self.client.get(self.draft_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="mediaAllowedRootUrls"')

    def test_post_anonymous_user_redirects_to_login(self):
        redirect_url = f"{reverse('login')}?next={self.published_url}"
        response = self.client.post(
            self.published_url,
            {"title": "new title"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_post_not_author_returns_404(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            self.published_url,
            {"title": "new title"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 404)

    def test_post_non_existent_article_returns_404(self):
        self.client.force_login(self.author)
        url = reverse("article-update", kwargs={"article_slug": "non-existent-article"})
        response = self.client.post(
            url, {"title": "new title"}, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 404)

    def test_post_invalid_data_returns_validation_errors(self):
        invalid_data = {"title": "a" * 300}

        self.client.force_login(self.author)
        response = self.client.post(self.draft_url, invalid_data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "status": "fail",
                "data": {
                    "title": [
                        "Ensure this value has at most 200 characters (it has 300)."
                    ],
                },
            },
        )

    def test_post_correct_for_draft_article_regenerates_slug_and_returns_edit_url(self):
        updated_data = {
            "title": "updated draft title",
            "category": self.other_category.id,
            "preview_text": "updated draft preview text",
            "content": "updated draft content",
            "tags": "tag2, tag3",
            "action": "save_draft",
        }

        self.client.force_login(self.author)
        response = self.client.post(self.draft_url, updated_data)

        self.assertEqual(response.status_code, 200)

        self.draft_article.refresh_from_db()

        self.assertEqual(
            response.json(),
            {
                "status": "success",
                "data": {
                    "articleUrl": reverse(
                        "article-update",
                        kwargs={"article_slug": self.draft_article.slug},
                    ),
                },
            },
        )

        self.assertEqual(self.draft_article.author, self.author)
        self.assertEqual(self.draft_article.title, "updated draft title")
        self.assertEqual(self.draft_article.slug, "updated-draft-title")
        self.assertEqual(self.draft_article.category, self.other_category)
        self.assertEqual(self.draft_article.preview_text, "updated draft preview text")
        self.assertEqual(self.draft_article.content, "updated draft content")
        self.assertEqual(self.draft_article.status, ArticleStatus.DRAFT)
        self.assertIsNone(self.draft_article.published_at)
        self.assertIsNone(self.draft_article.publish_sequence)
        self.assertCountEqual(
            [tag.name for tag in self.draft_article.tags.all()], ["tag2", "tag3"]
        )

    def test_post_submit_for_review_saves_changes_then_submits_article(self):
        updated_data = {
            "title": "ready for review",
            "category": self.other_category.id,
            "preview_text": "updated preview before review",
            "content": "<p>updated content before review</p>",
            "tags": "review-tag, django",
            "action": "submit_for_review",
        }

        self.client.force_login(self.author)
        response = self.client.post(self.draft_url, updated_data)

        self.assertEqual(response.status_code, 200)

        self.draft_article.refresh_from_db()

        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(self.draft_article.title, "ready for review")
        self.assertEqual(self.draft_article.slug, "ready-for-review")
        self.assertEqual(self.draft_article.category, self.other_category)
        self.assertEqual(
            self.draft_article.preview_text, "updated preview before review"
        )
        self.assertEqual(
            self.draft_article.content, "<p>updated content before review</p>"
        )
        self.assertEqual(self.draft_article.status, ArticleStatus.PENDING_REVIEW)
        self.assertIsNone(self.draft_article.published_at)
        self.assertIsNone(self.draft_article.publish_sequence)
        self.assertCountEqual(
            [tag.name for tag in self.draft_article.tags.all()],
            ["review-tag", "django"],
        )

    def test_post_submit_for_review_returns_error_when_article_is_not_ready(self):
        updated_data = {
            "title": "",
            "category": self.category.id,
            "preview_text": "preview exists",
            "content": "<p>content exists</p>",
            "action": "submit_for_review",
        }

        self.client.force_login(self.author)
        response = self.client.post(self.draft_url, updated_data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "status": "fail",
                "data": {
                    "__all__": ["Title is required before submission for review."],
                },
            },
        )

        self.draft_article.refresh_from_db()
        self.assertEqual(self.draft_article.status, ArticleStatus.DRAFT)

    def test_post_submit_for_review_from_rejected_article_saves_and_resubmits(self):
        self.draft_article.status = ArticleStatus.REJECTED
        self.draft_article.review_note = "Please improve the article."
        self.draft_article.reviewed_at = timezone.now()
        self.draft_article.reviewed_by = self.other_user
        self.draft_article.save(
            update_fields=["status", "review_note", "reviewed_at", "reviewed_by"]
        )

        updated_data = {
            "title": "fixed rejected article",
            "category": self.category.id,
            "preview_text": "fixed preview text",
            "content": "<p>fixed content</p>",
            "action": "submit_for_review",
        }

        self.client.force_login(self.author)
        response = self.client.post(self.draft_url, updated_data)

        self.assertEqual(response.status_code, 200)

        self.draft_article.refresh_from_db()

        self.assertEqual(self.draft_article.status, ArticleStatus.PENDING_REVIEW)
        self.assertEqual(self.draft_article.title, "fixed rejected article")
        self.assertEqual(self.draft_article.review_note, "")
        self.assertIsNone(self.draft_article.reviewed_at)
        self.assertIsNone(self.draft_article.reviewed_by)

    def test_post_correct_does_not_change_author(self):
        updated_data = {
            "title": "author unchanged",
            "category": self.category.id,
            "preview_text": "preview unchanged author",
            "content": "content unchanged author",
            "action": "save_draft",
        }

        self.client.force_login(self.author)
        response = self.client.post(self.draft_url, updated_data)

        self.assertEqual(response.status_code, 200)
        self.draft_article.refresh_from_db()
        self.assertEqual(self.draft_article.author_id, self.author.id)

    def test_post_not_author_does_not_modify_article(self):
        original_title = self.published_article.title
        original_preview_text = self.published_article.preview_text
        original_content = self.published_article.content
        original_slug = self.published_article.slug

        self.client.force_login(self.other_user)
        response = self.client.post(
            self.published_url,
            {
                "title": "hacked title",
                "category": self.other_category.id,
                "preview_text": "hacked preview",
                "content": "hacked content",
                "action": "submit_for_review",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 404)

        self.published_article.refresh_from_db()
        self.assertEqual(self.published_article.title, original_title)
        self.assertEqual(self.published_article.preview_text, original_preview_text)
        self.assertEqual(self.published_article.content, original_content)
        self.assertEqual(self.published_article.slug, original_slug)
        self.assertEqual(self.published_article.author, self.author)
