from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleStatus
from articles.selectors import (
    ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT,
    find_article_filter_author_suggestions,
    find_article_filter_authors,
    find_article_filter_categories,
    find_article_filter_tag_suggestions,
    find_article_filter_tags,
)


User = get_user_model()


class TestArticleFilterSelectors(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author_with_published = User.objects.create_user(
            username="published_author", email="published@test.com"
        )
        cls.author_with_draft_only = User.objects.create_user(
            username="draft_author", email="draft@test.com"
        )
        cls.author_with_pending_only = User.objects.create_user(
            username="pending_author", email="pending@test.com"
        )
        cls.author_without_articles = User.objects.create_user(
            username="empty_author", email="empty@test.com"
        )

        cls.public_category = ArticleCategory.objects.create(
            title="Public Category", slug="public-category"
        )
        cls.draft_only_category = ArticleCategory.objects.create(
            title="Draft Only Category", slug="draft-only-category"
        )
        cls.empty_category = ArticleCategory.objects.create(
            title="Empty Category", slug="empty-category"
        )

        cls.published_article = cls.create_article(
            title="Published Article",
            slug="published-article",
            author=cls.author_with_published,
            category=cls.public_category,
            status=ArticleStatus.PUBLISHED,
        )
        cls.published_article.tags.add("django", "python", "public-tag")

        cls.second_published_article = cls.create_article(
            title="Second Published Article",
            slug="second-published-article",
            author=cls.author_with_published,
            category=cls.public_category,
            status=ArticleStatus.PUBLISHED,
        )
        cls.second_published_article.tags.add("django", "postgres")

        cls.draft_article = cls.create_article(
            title="Draft Article",
            slug="draft-article",
            author=cls.author_with_draft_only,
            category=cls.draft_only_category,
            status=ArticleStatus.DRAFT,
        )
        cls.draft_article.tags.add("draft-tag", "private-tag")

        cls.pending_article = cls.create_article(
            title="Pending Article",
            slug="pending-article",
            author=cls.author_with_pending_only,
            category=cls.draft_only_category,
            status=ArticleStatus.PENDING_REVIEW,
        )
        cls.pending_article.tags.add("pending-tag")

    @classmethod
    def create_article(
        cls,
        *,
        title: str,
        slug: str,
        author,
        category=None,
        status=ArticleStatus.DRAFT,
    ) -> Article:
        is_published = status == ArticleStatus.PUBLISHED

        return Article.objects.create(
            title=title,
            slug=slug,
            author=author,
            category=category,
            preview_text="Preview text",
            content="<p>Article content</p>",
            content_text="Article content",
            status=status,
            published_at=timezone.now() if is_published else None,
        )

    def test_find_article_filter_categories_returns_only_cats_with_published_articles(
        self,
    ):
        categories = list(find_article_filter_categories())

        self.assertEqual(categories, [self.public_category])
        self.assertNotIn(self.draft_only_category, categories)
        self.assertNotIn(self.empty_category, categories)

    def test_find_article_filter_tags_returns_only_tags_from_published_articles(self):
        tag_names = set(find_article_filter_tags().values_list("name", flat=True))

        self.assertEqual(tag_names, {"django", "python", "postgres", "public-tag"})

        self.assertNotIn("draft-tag", tag_names)
        self.assertNotIn("private-tag", tag_names)
        self.assertNotIn("pending-tag", tag_names)

    def test_find_article_filter_authors_returns_only_authors_with_published_articles(
        self,
    ):
        authors = list(find_article_filter_authors())

        self.assertEqual(authors, [self.author_with_published])
        self.assertNotIn(self.author_with_draft_only, authors)
        self.assertNotIn(self.author_with_pending_only, authors)
        self.assertNotIn(self.author_without_articles, authors)

    def test_find_article_filter_tag_suggestions_filters_by_query(self):
        tag_names = set(
            find_article_filter_tag_suggestions("djan").values_list("name", flat=True)
        )

        self.assertEqual(tag_names, {"django"})

    def test_find_article_filter_tag_suggestions_ignores_draft_and_pending_tags(self):
        draft_tag_names = set(
            find_article_filter_tag_suggestions("draft").values_list("name", flat=True)
        )
        pending_tag_names = set(
            find_article_filter_tag_suggestions("pending").values_list(
                "name", flat=True
            )
        )

        self.assertEqual(draft_tag_names, set())
        self.assertEqual(pending_tag_names, set())

    def test_find_article_filter_tag_suggestions_strips_query(self):
        tag_names = set(
            find_article_filter_tag_suggestions("  djan  ").values_list(
                "name", flat=True
            )
        )

        self.assertEqual(tag_names, {"django"})

    def test_find_article_filter_tag_suggestions_returns_limited_results(self):
        for index in range(ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT + 5):
            article = self.create_article(
                title=f"Tag Limit Article {index}",
                slug=f"tag-limit-article-{index}",
                author=self.author_with_published,
                category=self.public_category,
                status=ArticleStatus.PUBLISHED,
            )
            article.tags.add(f"limit-tag-{index:02d}")

        suggestions = list(find_article_filter_tag_suggestions("limit-tag"))

        self.assertEqual(len(suggestions), ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT)

    def test_find_article_filter_author_suggestions_filters_by_username(self):
        authors = list(find_article_filter_author_suggestions("published"))

        self.assertEqual(authors, [self.author_with_published])

    # pylint: disable-next=line-too-long
    def test_find_article_filter_author_suggestions_ignores_authors_without_published_articles(  # noqa: E501
        self,
    ):
        draft_authors = list(find_article_filter_author_suggestions("draft"))
        pending_authors = list(find_article_filter_author_suggestions("pending"))
        empty_authors = list(find_article_filter_author_suggestions("empty"))

        self.assertEqual(draft_authors, [])
        self.assertEqual(pending_authors, [])
        self.assertEqual(empty_authors, [])

    def test_find_article_filter_author_suggestions_strips_query(self):
        authors = list(find_article_filter_author_suggestions("  published  "))

        self.assertEqual(authors, [self.author_with_published])

    def test_find_article_filter_author_suggestions_returns_limited_results(self):
        for index in range(ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT + 5):
            author = User.objects.create_user(
                username=f"limit_author_{index:02d}",
                email=f"limit-author-{index}@test.com",
            )
            self.create_article(
                title=f"Author Limit Article {index}",
                slug=f"author-limit-article-{index}",
                author=author,
                category=self.public_category,
                status=ArticleStatus.PUBLISHED,
            )

        suggestions = list(find_article_filter_author_suggestions("limit_author"))

        self.assertEqual(len(suggestions), ARTICLE_FILTER_AUTOCOMPLETE_RESULT_LIMIT)
