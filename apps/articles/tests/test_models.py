from django.test import TestCase
from django.contrib.auth.models import User

from articles.models import Article, ArticleCategory


class TestModels(TestCase):
    def setUp(self):
        self.test_user = User(username="test_user", email="test@test.com")
        self.test_user.set_password("12345")
        self.test_user.save()

        self.test_category = ArticleCategory.objects.create(title="cat1", slug="cat1")
        self.test_article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

    def test_article__get_likes_count(self):
        likes_count = self.test_article.get_likes_count()
        self.assertEquals(likes_count, 0)
        self.test_article.users_that_liked.add(self.test_user)
        likes_count = self.test_article.get_likes_count()
        self.assertEquals(likes_count, 1)
        self.test_article.users_that_liked.remove(self.test_user)
        likes_count = self.test_article.get_likes_count()
        self.assertEquals(likes_count, 0)

    def test_article_category__get_articles_count(self):
        cat2 = ArticleCategory.objects.create(title="cat2", slug="cat2")

        Article.objects.create(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        Article.objects.create(
            title="a3",
            slug="a3",
            category=cat2,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        Article.objects.create(
            title="a4",
            slug="a4",
            category=cat2,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=False,
        )

        self.assertEquals(self.test_category.get_articles_count(), 2)
        self.assertEquals(cat2.get_articles_count(), 1)
