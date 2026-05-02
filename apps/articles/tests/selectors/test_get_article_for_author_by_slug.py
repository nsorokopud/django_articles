from django.test import TestCase

from articles.models import Article, ArticleCategory
from articles.selectors import get_article_for_author_by_slug
from users.models import User


class TestGetArticleForAuthorBySlug(TestCase):
    def setUp(self):
        self.author1 = User.objects.create_user(
            username="author1", email="author1@test.com"
        )
        self.author2 = User.objects.create_user(
            username="author2", email="author2@test.com"
        )
        self.user1 = User.objects.create_user(username="user1", email="user1@test.com")
        self.user2 = User.objects.create_user(username="user2", email="user2@test.com")

        self.category = ArticleCategory.objects.create(
            title="cat",
            slug="cat",
        )

        self.article = Article.objects.create(
            title="a",
            slug="a",
            author=self.author1,
            category=self.category,
            preview_text="t",
            content="c",
        )

    def test_returns_article_for_matching_slug_and_author(self):
        article = get_article_for_author_by_slug(
            article_slug="a",
            author_id=self.author1.id,
        )

        self.assertEqual(article.id, self.article.id)
        self.assertEqual(article.slug, "a")
        self.assertEqual(article.author_id, self.author1.id)

    def test_raises_does_not_exist_for_wrong_author(self):
        with self.assertRaises(Article.DoesNotExist):
            get_article_for_author_by_slug(
                article_slug="a",
                author_id=self.author2.id,
            )

    def test_raises_does_not_exist_for_wrong_slug(self):
        with self.assertRaises(Article.DoesNotExist):
            get_article_for_author_by_slug(
                article_slug="does-not-exist",
                author_id=self.author1.id,
            )

    def test_prefetches_tags(self):
        self.article.tags.add("tag1", "tag2")

        with self.assertNumQueries(2):
            article = get_article_for_author_by_slug(
                article_slug="a",
                author_id=self.author1.id,
            )
            list(article.tags.all())

    def test_annotates_zero_likes_count_when_article_has_no_likes(self):
        article = get_article_for_author_by_slug(
            article_slug="a",
            author_id=self.author1.id,
        )

        self.assertEqual(article.likes_count, 0)
