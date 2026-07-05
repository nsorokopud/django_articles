import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleStatus
from articles.selectors import ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT


User = get_user_model()


class TestArticleAutocompleteViews(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.public_category = ArticleCategory.objects.create(
            title="Public Category", slug="public-category"
        )

        cls.published_author = User.objects.create_user(
            username="published_author", email="published@test.com"
        )
        cls.second_published_author = User.objects.create_user(
            username="django_writer", email="django-writer@test.com"
        )
        cls.draft_only_author = User.objects.create_user(
            username="draft_author", email="draft@test.com"
        )
        cls.pending_only_author = User.objects.create_user(
            username="pending_author", email="pending@test.com"
        )
        cls.empty_author = User.objects.create_user(
            username="empty_author", email="empty@test.com"
        )

        cls.published_article = cls.create_article(
            title="Published Article",
            slug="published-article",
            author=cls.published_author,
            status=ArticleStatus.PUBLISHED,
        )
        cls.published_article.tags.add("django", "python", "public-tag")

        cls.second_published_article = cls.create_article(
            title="Second Published Article",
            slug="second-published-article",
            author=cls.second_published_author,
            status=ArticleStatus.PUBLISHED,
        )
        cls.second_published_article.tags.add("django-rest", "postgres")

        cls.draft_article = cls.create_article(
            title="Draft Article",
            slug="draft-article",
            author=cls.draft_only_author,
            status=ArticleStatus.DRAFT,
        )
        cls.draft_article.tags.add("draft-tag", "private-tag")

        cls.pending_article = cls.create_article(
            title="Pending Article",
            slug="pending-article",
            author=cls.pending_only_author,
            status=ArticleStatus.PENDING_REVIEW,
        )
        cls.pending_article.tags.add("pending-tag")

    @classmethod
    def create_article(cls, *, title: str, slug: str, author, status: str) -> Article:
        is_published = status == ArticleStatus.PUBLISHED

        return Article.objects.create(
            title=title,
            slug=slug,
            author=author,
            category=cls.public_category,
            preview_text="Preview text",
            content="<p>Article content</p>",
            content_text="Article content",
            status=status,
            published_at=timezone.now() if is_published else None,
        )

    def test_tag_autocomplete_returns_matching_published_tags(self):
        response = self.client.get(
            reverse("article-filter-tags-autocomplete"), {"q": "djan"}
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(
            payload,
            {
                "results": [
                    {"id": "django", "text": "django"},
                    {"id": "django-rest", "text": "django-rest"},
                ]
            },
        )

    def test_tag_autocomplete_excludes_draft_and_pending_only_tags(self):
        response = self.client.get(
            reverse("article-filter-tags-autocomplete"), {"q": "tag"}
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()
        result_ids = {item["id"] for item in payload["results"]}

        self.assertIn("public-tag", result_ids)
        self.assertNotIn("draft-tag", result_ids)
        self.assertNotIn("private-tag", result_ids)
        self.assertNotIn("pending-tag", result_ids)

    def test_tag_autocomplete_without_query_returns_published_tags_only(self):
        response = self.client.get(reverse("article-filter-tags-autocomplete"))

        self.assertEqual(response.status_code, 200)

        payload = response.json()
        result_ids = {item["id"] for item in payload["results"]}

        self.assertEqual(
            result_ids,
            {"django", "django-rest", "postgres", "public-tag", "python"},
        )

    def test_tag_autocomplete_respects_result_limit(self):
        for index in range(ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT + 5):
            article = self.create_article(
                title=f"Limit Tag Article {index}",
                slug=f"limit-tag-article-{index}",
                author=self.published_author,
                status=ArticleStatus.PUBLISHED,
            )
            article.tags.add(f"limit-tag-{index:02d}")

        response = self.client.get(
            reverse("article-filter-tags-autocomplete"), {"q": "limit-tag"}
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(
            len(payload["results"]), ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT
        )

    def test_author_autocomplete_returns_matching_published_authors(self):
        response = self.client.get(
            reverse("article-filter-authors-autocomplete"), {"q": "published"}
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(
            payload,
            {"results": [{"id": "published_author", "text": "published_author"}]},
        )

    def test_author_autocomplete_excludes_authors_without_published_articles(self):
        response = self.client.get(
            reverse("article-filter-authors-autocomplete"), {"q": "author"}
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()
        result_ids = {item["id"] for item in payload["results"]}

        self.assertIn("published_author", result_ids)
        self.assertNotIn("draft_author", result_ids)
        self.assertNotIn("pending_author", result_ids)
        self.assertNotIn("empty_author", result_ids)

    def test_author_autocomplete_without_query_returns_published_authors_only(self):
        response = self.client.get(reverse("article-filter-authors-autocomplete"))

        self.assertEqual(response.status_code, 200)

        payload = response.json()
        result_ids = {item["id"] for item in payload["results"]}

        self.assertEqual(
            result_ids,
            {"published_author", "django_writer"},
        )

    def test_author_autocomplete_respects_result_limit(self):
        for index in range(ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT + 5):
            author = User.objects.create_user(
                username=f"limit_author_{index:02d}",
                email=f"limit-author-{index}@test.com",
            )
            self.create_article(
                title=f"Limit Author Article {index}",
                slug=f"limit-author-article-{index}",
                author=author,
                status=ArticleStatus.PUBLISHED,
            )

        response = self.client.get(
            reverse("article-filter-authors-autocomplete"), {"q": "limit_author"}
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(
            len(payload["results"]), ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT
        )

    def test_autocomplete_responses_are_json(self):
        tag_response = self.client.get(reverse("article-filter-tags-autocomplete"))
        author_response = self.client.get(
            reverse("article-filter-authors-autocomplete")
        )

        self.assertEqual(tag_response["Content-Type"], "application/json")
        self.assertEqual(author_response["Content-Type"], "application/json")

        json.loads(tag_response.content.decode("utf-8"))
        json.loads(author_response.content.decode("utf-8"))
