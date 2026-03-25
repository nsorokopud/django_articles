from django.test import TestCase
from django.utils import timezone
from taggit.models import Tag

from articles.models import Article, ArticleCategory, ArticleComment, ArticleStatus
from articles.selectors import (
    find_article_comments_liked_by_user,
    find_articles_by_query,
    find_articles_with_all_tags,
    find_comments_to_article,
    find_published_articles,
    find_subscription_feed_articles,
    get_all_categories,
    get_all_tags,
    get_article_by_slug,
    get_comment_by_id,
)
from users.models import AuthorSubscription, User


class TestSelectors(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(
            username="test_user", email="test_user@test.com"
        )
        self.test_category = ArticleCategory.objects.create(
            title="test_cat", slug="test_cat"
        )
        self._publish_sequence = 0

    def create_article(self, **kwargs) -> Article:
        defaults = {
            "title": "article",
            "slug": "article",
            "category": self.test_category,
            "author": self.test_user,
            "preview_text": "text",
            "content": "content",
            "status": ArticleStatus.DRAFT,
            "published_at": None,
            "publish_sequence": None,
        }
        defaults.update(kwargs)
        return Article.objects.create(**defaults)

    def create_published_article(self, **kwargs) -> Article:
        self._publish_sequence += 1
        defaults = {
            "status": ArticleStatus.PUBLISHED,
            "published_at": timezone.now(),
            "publish_sequence": self._publish_sequence,
        }
        defaults.update(kwargs)
        return self.create_article(**defaults)

    def test_find_published_articles(self):
        a1 = self.create_published_article(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )
        self.create_article(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text2",
            content="content2",
        )
        a3 = self.create_published_article(
            title="a3",
            slug="a3",
            category=self.test_category,
            author=self.test_user,
            preview_text="text3",
            content="content3",
        )
        self.assertCountEqual(find_published_articles(), [a1, a3])

    def test_find_articles_with_all_tags(self):
        a1 = self.create_published_article(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text",
            content="content",
        )
        a1.tags.add("tag1", "tag2")
        a1.save()

        a2 = self.create_published_article(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text",
            content="content",
        )
        a2.tags.add("tag3")
        a2.save()

        a3 = self.create_published_article(
            title="a3",
            slug="a3",
            category=self.test_category,
            author=self.test_user,
            preview_text="text",
            content="content",
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

        a1 = self.create_published_article(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )
        a1.tags.add("cat1", "tag1")

        a2 = self.create_published_article(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text2",
            content="content2",
        )

        a3 = self.create_published_article(
            title="a3",
            slug="a3",
            category=cat1,
            author=self.test_user,
            preview_text="text3",
            content="content3",
        )
        a4 = self.create_published_article(
            title="a4",
            slug="a4",
            category=cat1,
            author=self.test_user,
            preview_text="text4",
            content="content4",
        )
        a4.tags.add("tag", "tag1", "tag2")
        self.create_article(
            title="a5",
            slug="a5",
            category=cat1,
            author=self.test_user,
            preview_text="text5",
            content="content5",
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
        a1 = self.create_published_article(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )
        a2 = self.create_published_article(
            title="a2",
            slug="a2",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
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
        a1 = self.create_article(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
        )
        a2 = self.create_article(
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

        a = self.create_article(
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
        a1 = self.create_published_article(
            title="a1",
            slug="a1",
            category=self.test_category,
            author=self.test_user,
            preview_text="text1",
            content="content1",
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

    def test_find_published_articles_ordered_by_publish_sequence_desc(self):
        a1 = self.create_published_article(title="a1", slug="a1", publish_sequence=10)
        a2 = self.create_published_article(title="a2", slug="a2", publish_sequence=30)
        a3 = self.create_published_article(title="a3", slug="a3", publish_sequence=20)

        result = list(find_published_articles())
        self.assertEqual(result, [a2, a3, a1])

    def test_get_comment_by_id(self):
        a = self.create_article(
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


class TestFindSubscriptionFeedArticles(TestCase):
    def setUp(self):
        self.subscriber = User.objects.create_user(
            username="subscriber", email="subscriber@test.com"
        )
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.other_author = User.objects.create_user(
            username="other_author", email="other_author@test.com"
        )
        AuthorSubscription.objects.create(
            subscriber=self.subscriber, author=self.author
        )
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.author,
            preview_text="text1",
            content="content1",
            status=ArticleStatus.PUBLISHED,
            publish_sequence=1,
            published_at=timezone.now(),
        )

    def test_returns_subscribed_to_authors_articles(self):
        qs = find_subscription_feed_articles(self.subscriber)
        self.assertCountEqual(qs, [self.article])

    def test_excludes_non_subscribed_to_authors(self):
        Article.objects.create(
            title="a2",
            slug="a2",
            author=self.other_author,
            preview_text="text2",
            content="content2",
            status=ArticleStatus.PUBLISHED,
            publish_sequence=2,
            published_at=timezone.now(),
        )

        qs = find_subscription_feed_articles(self.subscriber)
        self.assertCountEqual(qs, [self.article])

    def test_excludes_unpublished_articles(self):
        Article.objects.create(
            title="a2",
            slug="a2",
            author=self.author,
            preview_text="text2",
            content="content2",
        )

        qs = find_subscription_feed_articles(self.subscriber)
        self.assertCountEqual(qs, [self.article])
