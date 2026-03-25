from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleStatus
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
        self.other_category = ArticleCategory.objects.create(
            title="cat2",
            slug="cat2",
        )

        self.published_article = Article.objects.create(
            title="article",
            slug="test-article",
            category=self.category,
            author=self.author,
            preview_text="text1",
            content="content1",
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
        )
        self.draft_article.tags.add("draft-tag")

        self.published_url = reverse(
            "article-update",
            kwargs={"article_slug": self.published_article.slug},
        )
        self.draft_url = reverse(
            "article-update",
            kwargs={"article_slug": self.draft_article.slug},
        )

    def test_get_anonymous_user_returns_404(self):
        response = self.client.get(self.published_url)
        self.assertEqual(response.status_code, 404)

    def test_get_not_author_returns_404(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.published_url)
        self.assertEqual(response.status_code, 404)

    def test_get_non_existent_article_returns_404(self):
        self.client.force_login(self.author)
        url = reverse(
            "article-update",
            kwargs={"article_slug": "non-existent-article"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_get_correct_for_published_article(self):
        self.client.force_login(self.author)
        response = self.client.get(self.published_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_form.html")
        self.assertEqual(response.context["object"], self.published_article)
        self.assertTrue(response.context["update"])

    def test_get_correct_for_draft_article(self):
        self.client.force_login(self.author)
        response = self.client.get(self.draft_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_form.html")
        self.assertEqual(response.context["object"], self.draft_article)
        self.assertTrue(response.context["update"])

    def test_post_anonymous_user_returns_404(self):
        response = self.client.post(
            self.published_url,
            {"title": "new title"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 404)

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
        url = reverse(
            "article-update",
            kwargs={"article_slug": "non-existent-article"},
        )
        response = self.client.post(
            url,
            {"title": "new title"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 404)

    def test_post_invalid_data_returns_validation_errors(self):
        invalid_data = {
            "title": "",
            "content": "",
        }

        self.client.force_login(self.author)
        response = self.client.post(self.published_url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "fail",
                "data": {
                    "title": ["This field is required."],
                    "preview_text": ["This field is required."],
                    "content": ["This field is required."],
                },
            },
        )

    def test_post_correct_for_published_article_keeps_slug_and_returns_public_url(self):
        updated_data = {
            "title": "new title",
            "category": self.other_category.id,
            "preview_text": "new preview text",
            "content": "new content",
            "tags": "tag2, tag3",
        }

        self.client.force_login(self.author)
        response = self.client.post(self.published_url, updated_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "success",
                "data": {
                    "articleUrl": reverse(
                        "article-details",
                        kwargs={"article_slug": self.published_article.slug},
                    ),
                    "isPublished": True,
                },
            },
        )

        self.published_article.refresh_from_db()
        self.assertEqual(self.published_article.author, self.author)
        self.assertEqual(self.published_article.title, "new title")
        self.assertEqual(self.published_article.slug, "test-article")
        self.assertEqual(self.published_article.category, self.other_category)
        self.assertEqual(self.published_article.preview_text, "new preview text")
        self.assertEqual(self.published_article.content, "new content")
        self.assertIsNotNone(self.published_article.published_at)
        self.assertEqual(self.published_article.publish_sequence, 1)
        self.assertCountEqual(
            [tag.name for tag in self.published_article.tags.all()],
            ["tag2", "tag3"],
        )

    def test_post_correct_for_draft_article_regenerates_slug_and_returns_edit_url(self):
        updated_data = {
            "title": "updated draft title",
            "category": self.other_category.id,
            "preview_text": "updated draft preview text",
            "content": "updated draft content",
            "tags": "tag2, tag3",
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
                    "isPublished": False,
                },
            },
        )

        self.assertEqual(self.draft_article.author, self.author)
        self.assertEqual(self.draft_article.title, "updated draft title")
        self.assertEqual(self.draft_article.slug, "updated-draft-title")
        self.assertEqual(self.draft_article.category, self.other_category)
        self.assertEqual(
            self.draft_article.preview_text,
            "updated draft preview text",
        )
        self.assertEqual(self.draft_article.content, "updated draft content")
        self.assertIsNone(self.draft_article.published_at)
        self.assertIsNone(self.draft_article.publish_sequence)
        self.assertCountEqual(
            [tag.name for tag in self.draft_article.tags.all()],
            ["tag2", "tag3"],
        )

    def test_post_correct_does_not_change_author(self):
        updated_data = {
            "title": "author unchanged",
            "category": self.category.id,
            "preview_text": "preview unchanged author",
            "content": "content unchanged author",
        }

        self.client.force_login(self.author)
        response = self.client.post(self.published_url, updated_data)

        self.assertEqual(response.status_code, 200)
        self.published_article.refresh_from_db()
        self.assertEqual(self.published_article.author_id, self.author.id)

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
