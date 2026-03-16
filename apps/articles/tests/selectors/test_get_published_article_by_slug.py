from django.test import TestCase

from articles.models import Article, ArticleCategory
from articles.selectors import get_published_article_by_slug
from users.models import User


class TestGetPublishedArticleBySlug(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="a", email="a@test.com")
        self.user = User.objects.create_user(username="u", email="u@test.com")
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")

    def create_article(
        self,
        *,
        title="Test article",
        slug="test-article",
        published=False,
    ) -> Article:
        article = Article.objects.create(
            title=title,
            slug=slug,
            category=self.category,
            author=self.author,
            preview_text="Preview text",
            content="<p>Article content</p>",
        )

        if published:
            article.published_at = article.created_at
            article.publish_sequence = 1
            article.save(update_fields=["published_at", "publish_sequence"])

        return article

    def test_returns_published_article_by_slug(self):
        article = self.create_article(
            title="Published article",
            slug="published-article",
            published=True,
        )

        result = get_published_article_by_slug("published-article")

        self.assertEqual(result.id, article.id)
        self.assertEqual(result.slug, article.slug)
        self.assertEqual(result.author, self.author)
        self.assertEqual(result.category, self.category)

    def test_raises_does_not_exist_for_unpublished_article(self):
        self.create_article(
            title="Draft article",
            slug="draft-article",
            published=False,
        )

        with self.assertRaises(Article.DoesNotExist):
            get_published_article_by_slug("draft-article")

    def test_raises_does_not_exist_for_missing_slug(self):
        with self.assertRaises(Article.DoesNotExist):
            get_published_article_by_slug("missing-slug")

    def test_returns_article_with_related_objects_loaded(self):
        self.create_article(
            title="Published article",
            slug="published-article",
            published=True,
        )

        result = get_published_article_by_slug("published-article")

        self.assertEqual(result.author.id, self.author.id)
        self.assertEqual(result.category.id, self.category.id)
        self.assertEqual(result.category.title, "cat")

    def test_annotates_likes_count(self):
        article = self.create_article(
            title="Liked article",
            slug="liked-article",
            published=True,
        )
        article.users_that_liked.add(self.user)

        result = get_published_article_by_slug("liked-article")

        self.assertEqual(result.likes_count, 1)

    def test_annotates_likes_count_with_multiple_users(self):
        other_user = User.objects.create_user(username="u2", email="u2@test.com")
        article = self.create_article(
            title="Popular article",
            slug="popular-article",
            published=True,
        )
        article.users_that_liked.add(self.user, other_user)

        result = get_published_article_by_slug("popular-article")
        self.assertEqual(result.likes_count, 2)
