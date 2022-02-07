from django.test import TestCase
from django.contrib.auth.models import User

from articles.models import Article, ArticleCategory
from articles.services import (
    find_published_articles,
    find_articles_of_category,
    find_articles_by_query,
    get_all_categories,
    create_article,
    toggle_article_like,
    get_all_users_that_liked_article,
)


class TestServices(TestCase):
    def setUp(self):
        self.test_user = User(username="test_user", email="test@test.com")
        self.test_user.set_password("12345")
        self.test_user.save()

        self.test_category = ArticleCategory.objects.create(title="test_cat", slug="test_cat")

    def test_find_published_articles(self):
        a1 = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        Article.objects.create(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text2",
            content="content2",
            is_published=False,
        )
        a3 = Article.objects.create(
            title="a3",
            slug="a3",
            category=self.test_category,
            author=self.test_user,
            preview_text="text3",
            content="content3",
            is_published=True,
        )
        self.assertCountEqual(find_published_articles(), [a1, a3])

    def test_find_articles_of_category(self):
        a1 = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        Article.objects.create(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text2",
            content="content2",
            is_published=False,
        )

        cat1 = ArticleCategory.objects.create(title="cat1", slug="cat1")

        Article.objects.create(
            title="a3",
            slug="a3",
            category=cat1,
            author=self.test_user,
            preview_text="text3",
            content="content3",
            is_published=True,
        )
        self.assertCountEqual(find_articles_of_category(self.test_category.slug), [a1])

    def test_find_articles_by_query(self):
        cat1 = ArticleCategory.objects.create(title="cat1", slug="cat1")

        a1 = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        a1.tags.add("cat1", "tag1")
        a2 = Article.objects.create(
            title="a2",
            slug="a2",
            category=self.test_category,
            tags="tag2,cat1",
            author=self.test_user,
            preview_text="text2",
            content="content2",
            is_published=True,
        )
        a3 = Article.objects.create(
            title="a3",
            slug="a3",
            category=cat1,
            author=self.test_user,
            preview_text="text3",
            content="content3",
            is_published=True,
        )
        a4 = Article.objects.create(
            title="a4",
            slug="a4",
            category=cat1,
            author=self.test_user,
            preview_text="text4",
            content="content4",
            is_published=True,
        )
        a4.tags.add("tag", "tag1", "tag2")
        Article.objects.create(
            title="a5",
            slug="a5",
            category=cat1,
            author=self.test_user,
            preview_text="text5",
            content="content5",
            is_published=False,
        )

        self.assertCountEqual(list(find_articles_by_query("a")), [a1, a2, a3, a4])  # By title
        self.assertCountEqual(
            list(find_articles_by_query("content")), [a1, a2, a3, a4]
        )  # By content
        self.assertCountEqual(list(find_articles_by_query("test_")), [a1, a2])  # By category
        self.assertCountEqual(
            list(find_articles_by_query("cat1")), [a1, a3, a4]
        )  # By category + tag
        self.assertCountEqual(list(find_articles_by_query("tag1")), [a1, a4])  # By tag
        self.assertCountEqual(list(find_articles_by_query("agrj")), [])  # Not found

    def test_get_all_categories(self):
        cat1 = ArticleCategory.objects.create(title="cat1", slug="cat1")
        cat2 = ArticleCategory.objects.create(title="cat2", slug="cat2")
        self.assertCountEqual(get_all_categories(), [cat1, cat2, self.test_category])

    def test_create_article(self):
        a1 = create_article(
            title="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            tags=["tag1", "tag2"],
        )

        last_article = Article.objects.last()

        self.assertEquals(last_article.pk, a1.pk)
        self.assertEquals(last_article.slug, "a1")
        self.assertEquals(last_article.author.username, "test_user")

        expected_tags = ["tag1", "tag2"]
        actual_tags = [tag.name for tag in last_article.tags.all()]
        self.assertCountEqual(actual_tags, expected_tags)

    def test_get_all_users_that_liked_article(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        self.assertEquals(list(get_all_users_that_liked_article(a.slug)), [])
        a.users_that_liked.add(self.test_user)
        self.assertCountEqual(get_all_users_that_liked_article(a.slug), [self.test_user])

    def test_toggle_article_like(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

        user = User(username="user1", email="test@test.com")
        user.set_password("12345")
        user.save()

        likes_count = toggle_article_like(a.slug, self.test_user.id)
        self.assertEquals(likes_count, 1)
        likes_count = toggle_article_like(a.slug, self.test_user.id)
        self.assertEquals(likes_count, 0)

        likes_count = toggle_article_like(a.slug, self.test_user.id)
        self.assertEquals(likes_count, 1)
        likes_count = toggle_article_like(a.slug, user.id)
        self.assertEquals(likes_count, 2)
        likes_count = toggle_article_like(a.slug, self.test_user.id)
        self.assertEquals(likes_count, 1)
        likes_count = toggle_article_like(a.slug, user.id)
        self.assertEquals(likes_count, 0)
