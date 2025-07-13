from django.test import TestCase
from taggit.models import Tag

from articles.models import Article, ArticleCategory, ArticleComment
from articles.selectors import (
    find_article_comments_liked_by_user,
    find_articles_by_query,
    find_articles_with_all_tags,
    find_comments_to_article,
    find_published_articles,
    get_all_categories,
    get_all_tags,
    get_article_by_slug,
    get_comment_by_id,
)
from users.models import User


class TestSelectors(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test_user@test.com"
        )
        self.test_category = ArticleCategory.objects.create(
            title="test_cat", slug="test_cat"
        )

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

    def test_find_articles_with_all_tags(self):
        a1 = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text",
            content="content",
            is_published=True,
        )
        a1.tags.add("tag1", "tag2")
        a1.save()

        a2 = Article.objects.create(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text",
            content="content",
            is_published=True,
        )
        a2.tags.add("tag3")
        a2.save()

        a3 = Article.objects.create(
            title="a3",
            slug="a3",
            category=self.test_category,
            author=self.test_user,
            preview_text="text",
            content="content",
            is_published=True,
        )
        a3.tags.add("tag2", "tag7")
        a3.save()

        with self.assertRaises(TypeError):
            find_articles_with_all_tags(None)

        self.assertCountEqual(find_articles_with_all_tags([]), [])

        tags = Tag.objects.filter(name__in=["ehjnrkhn"])
        self.assertCountEqual(find_articles_with_all_tags(tags), [])

        tags = Tag.objects.filter(name__in=["tag2"])
        self.assertCountEqual(find_articles_with_all_tags(tags), [a1, a3])

        tags = Tag.objects.filter(name__in=["tag2", "tag2"])
        self.assertCountEqual(find_articles_with_all_tags(tags), [a1, a3])

        tags = Tag.objects.filter(name__in=["tag7", "tag2"])
        self.assertCountEqual(find_articles_with_all_tags(tags), [a3])

        tags = Tag.objects.filter(name__in=["tag2"])
        queryset = Article.objects.filter(id__in=[a1.id, a2.id])
        self.assertCountEqual(find_articles_with_all_tags(tags, queryset), [a1])

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

        self.assertCountEqual(find_articles_by_query("a"), [a1, a2, a3, a4])  # By title
        self.assertCountEqual(
            find_articles_by_query("content"), [a1, a2, a3, a4]
        )  # By content
        self.assertCountEqual(find_articles_by_query("test_"), [a1, a2])  # By category
        self.assertCountEqual(
            find_articles_by_query("cat1"), [a1, a3, a4]
        )  # By category + tag
        self.assertCountEqual(find_articles_by_query("tag1"), [a1, a4])  # By tag
        self.assertCountEqual(find_articles_by_query("agrj"), [])  # Not found

        # With queryset
        queryset = Article.objects.filter(id__in=[a1.id, a4.id])
        self.assertCountEqual(find_articles_by_query("a", queryset), [a1, a4])
        self.assertCountEqual(find_articles_by_query("content", queryset), [a1, a4])
        self.assertCountEqual(find_articles_by_query("test_", queryset), [a1])
        self.assertCountEqual(find_articles_by_query("cat1", queryset), [a1, a4])

        queryset = Article.objects.filter(id__in=[a1.id, a2.id, a3.id])
        self.assertCountEqual(find_articles_by_query("tag1", queryset), [a1])
        self.assertCountEqual(find_articles_by_query("agrj", queryset), [])

    def test_find_comments_to_article(self):
        a1 = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        a2 = Article.objects.create(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )
        comment1 = ArticleComment.objects.create(
            article=a1, author=self.test_user, text="text"
        )
        ArticleComment.objects.create(article=a2, author=self.test_user, text="text")
        comment3 = ArticleComment.objects.create(
            article=a1, author=self.test_user, text="text"
        )
        self.assertCountEqual(find_comments_to_article(a1), [comment1, comment3])

    def test_get_all_categories(self):
        cat1 = ArticleCategory.objects.create(title="cat1", slug="cat1")
        cat2 = ArticleCategory.objects.create(title="cat2", slug="cat2")
        self.assertCountEqual(get_all_categories(), [cat1, cat2, self.test_category])

    def test_get_all_tags(self):
        a1 = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )
        a2 = Article.objects.create(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text2",
            content="content2",
        )

        res = get_all_tags()
        self.assertCountEqual(res, [])

        a1.tags.add("tag1", "tag2")
        res = [tag.name for tag in get_all_tags()]
        self.assertCountEqual(res, ["tag1", "tag2"])

        a2.tags.add("tag2", "tag3")
        res = [tag.name for tag in get_all_tags()]
        self.assertCountEqual(res, ["tag1", "tag2", "tag3"])

    def test_get_article_by_slug(self):
        with self.assertRaises(Article.DoesNotExist):
            get_article_by_slug("a1")

        a = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )

        res = get_article_by_slug("a1")
        self.assertEqual(res, a)

        a.delete()
        with self.assertRaises(Article.DoesNotExist):
            get_article_by_slug("a1")

    def test_find_article_comments_liked_by_user(self):
        a1 = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
            is_published=True,
        )

        comment1 = ArticleComment.objects.create(
            article=a1, author=self.test_user, text="text"
        )
        ArticleComment.objects.create(article=a1, author=self.test_user, text="text")
        comment3 = ArticleComment.objects.create(
            article=a1, author=self.test_user, text="text"
        )

        comment1.users_that_liked.add(self.test_user)
        comment3.users_that_liked.add(self.test_user)

        self.assertCountEqual(
            find_article_comments_liked_by_user(a1, self.test_user),
            [comment1.id, comment3.id],
        )

    def test_get_comment_by_id(self):
        a = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )

        c1 = ArticleComment.objects.create(article=a, author=self.test_user, text="")
        c1_id = c1.id
        c2 = ArticleComment.objects.create(article=a, author=self.test_user, text="")
        c2_id = c2.id

        self.assertEqual(get_comment_by_id(c1_id), c1)
        self.assertEqual(get_comment_by_id(c2_id), c2)

        c2.delete()
        with self.assertRaises(ArticleComment.DoesNotExist):
            get_comment_by_id(c2_id)

        c1.delete()
        with self.assertRaises(ArticleComment.DoesNotExist):
            get_comment_by_id(c1_id)
