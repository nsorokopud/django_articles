from django.test import TestCase

from articles.models import Article, ArticleCategory
from articles.selectors import get_article_for_author_by_id
from users.models import User


class TestGetArticleForAuthorById(TestCase):
    def setUp(self):
        self.author1 = User.objects.create_user(
            username="author1", email="author1@test.com"
        )
        self.author2 = User.objects.create_user(
            username="author2", email="author2@test.com"
        )
        self.user1 = User.objects.create_user(username="user1", email="user1@test.com")
        self.user2 = User.objects.create_user(username="user2", email="user2@test.com")

        self.category = ArticleCategory.objects.create(title="cat", slug="cat")

        self.article = Article.objects.create(
            title="a",
            slug="a",
            author=self.author1,
            category=self.category,
            preview_text="t",
            content="c",
        )

    def test_returns_article_for_matching_id_and_author(self):
        article = get_article_for_author_by_id(
            article_id=self.article.id, author_id=self.author1.id
        )

        self.assertEqual(article.id, self.article.id)
        self.assertEqual(article.slug, "a")
        self.assertEqual(article.author_id, self.author1.id)

    def test_raises_does_not_exist_for_wrong_author(self):
        with self.assertRaises(Article.DoesNotExist):
            get_article_for_author_by_id(
                article_id=self.article.id, author_id=self.author2.id
            )

    def test_raises_does_not_exist_for_wrong_article_id(self):
        with self.assertRaises(Article.DoesNotExist):
            get_article_for_author_by_id(
                article_id=self.article.id + 999, author_id=self.author1.id
            )

    def test_does_not_depend_on_slug(self):
        self.article.slug = "changed-slug"
        self.article.save(update_fields=["slug"])

        article = get_article_for_author_by_id(
            article_id=self.article.id, author_id=self.author1.id
        )

        self.assertEqual(article.id, self.article.id)
        self.assertEqual(article.slug, "changed-slug")
        self.assertEqual(article.author_id, self.author1.id)

    def test_prefetches_tags(self):
        self.article.tags.add("tag1", "tag2")

        with self.assertNumQueries(2):
            article = get_article_for_author_by_id(
                article_id=self.article.id, author_id=self.author1.id
            )
            list(article.tags.all())

    def test_selects_related_category_and_author_profile(self):
        with self.assertNumQueries(2):
            article = get_article_for_author_by_id(
                article_id=self.article.id, author_id=self.author1.id
            )

            # These should not trigger extra queries because the selector uses
            # select_related("category", "author", "author__profile").
            article.category.title
            article.author.username
            article.author.profile

    def test_returns_stored_likes_count_when_article_has_no_likes(self):
        article = get_article_for_author_by_id(
            article_id=self.article.id, author_id=self.author1.id
        )

        self.assertEqual(article.likes_count, 0)
