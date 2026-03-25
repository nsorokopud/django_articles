from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from taggit.models import Tag

from articles.filters import ArticleFilter, SubscriptionFeedFilter
from articles.models import Article, ArticleCategory, ArticleStatus
from articles.selectors import find_published_articles
from users.models import AuthorSubscription, User


class TestArticleFilter(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.today = self.now.date()

        self.user1 = User.objects.create(username="user1", email="user1@test.com")
        self.user2 = User.objects.create(username="user2", email="user2@test.com")

        self.category1 = ArticleCategory.objects.create(title="Cat1", slug="cat1")
        self.category2 = ArticleCategory.objects.create(title="Cat2", slug="cat2")

        self.tag1 = Tag.objects.create(name="tag1")
        self.tag2 = Tag.objects.create(name="tag2")

        self.article1 = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user1,
            category=self.category1,
            preview_text="Preview1",
            content="Content1",
            status=ArticleStatus.PUBLISHED,
            published_at=self.now - timedelta(days=100),
            publish_sequence=1,
            views_count=5,
        )
        self.article1.created_at = self.article1.published_at
        self.article1.save(update_fields=["created_at"])
        self.article1.tags.add(self.tag1, self.tag2)

        self.article2 = Article.objects.create(
            title="a2",
            slug="a2",
            author=self.user2,
            category=self.category2,
            preview_text="Preview2",
            content="Content2",
            status=ArticleStatus.PUBLISHED,
            published_at=self.now - timedelta(days=1),
            publish_sequence=2,
            views_count=100,
        )
        self.article2.created_at = self.article2.published_at
        self.article2.save(update_fields=["created_at"])
        self.article2.tags.add(self.tag1)
        self.article2.users_that_liked.add(self.user1)

    def get_base_queryset(self):
        return find_published_articles()

    def test_filter_by_author(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(data={"author": self.user1.username}, queryset=base_qs)
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article1])

        f = ArticleFilter(data={"author": self.user2.username}, queryset=base_qs)
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article2])

    def test_filter_by_author_invalid(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(data={"author": "non-existent"}, queryset=base_qs)
        self.assertFalse(f.is_valid())
        self.assertEqual(
            f.errors,
            {
                "author": [
                    "Select a valid choice. That choice is not one "
                    "of the available choices."
                ]
            },
        )

    def test_filter_by_category(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(data={"category": self.category1.slug}, queryset=base_qs)
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article1])

        f = ArticleFilter(data={"category": self.category2.slug}, queryset=base_qs)
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article2])

    def test_filter_by_category_invalid(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(data={"category": "non-existent"}, queryset=base_qs)
        self.assertFalse(f.is_valid())
        self.assertEqual(
            f.errors,
            {
                "category": [
                    "Select a valid choice. That choice is not one "
                    "of the available choices."
                ]
            },
        )

    def test_filter_by_date(self):
        base_qs = self.get_base_queryset()

        data = {
            "date_after": (self.today - timedelta(days=2)).isoformat(),
        }
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article2])

        data = {
            "date_before": (self.today - timedelta(days=2)).isoformat(),
        }
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1])

        data = {
            "date_before": (self.today - timedelta(days=1)).isoformat(),
            "date_after": (self.today - timedelta(days=1)).isoformat(),
        }
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article2])

    def test_filter_by_date_invalid(self):
        base_qs = self.get_base_queryset()

        data = {
            "date_before": "abc",
            "date_after": "xyz",
        }
        f = ArticleFilter(data=data, queryset=base_qs)
        self.assertFalse(f.is_valid())
        self.assertEqual(f.errors, {"date": ["Enter a valid date."]})

    def test_filter_by_tags(self):
        base_qs = self.get_base_queryset()

        data = {"tags": [self.tag1.name, self.tag2.name]}
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1])

    def test_filter_by_tags_invalid(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(data={"tags": ["non-existent-tag"]}, queryset=base_qs)
        self.assertFalse(f.is_valid())
        self.assertCountEqual(f.errors.keys(), ["tags"])
        self.assertEqual(len(f.errors["tags"]), 1)
        self.assertIn("Select a valid choice. ", f.errors["tags"][0])
        self.assertIn("is not one of the available choices.", f.errors["tags"][0])

    def test_filter_by_search(self):
        base_qs = self.get_base_queryset()

        filtered = ArticleFilter(data={"q": "a1"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1])

        filtered = ArticleFilter(data={"q": "a2"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article2])

        filtered = ArticleFilter(data={"q": "ent1"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1])

        filtered = ArticleFilter(data={"q": "content2"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article2])

        filtered = ArticleFilter(data={"q": "Cat1"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1])

        filtered = ArticleFilter(data={"q": "at2"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article2])

        filtered = ArticleFilter(data={"q": "qafwejkfb"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [])

    def test_ordering(self):
        base_qs = self.get_base_queryset()

        data = {"ordering": "published_at"}
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertEqual(list(filtered), [self.article1, self.article2])

        data = {"ordering": "-published_at"}
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertEqual(list(filtered), [self.article2, self.article1])

        data = {"ordering": "likes_count"}
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertEqual(list(filtered), [self.article1, self.article2])

        data = {"ordering": "-likes_count"}
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertEqual(list(filtered), [self.article2, self.article1])

        data = {"ordering": "views_count"}
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertEqual(list(filtered), [self.article1, self.article2])

        data = {"ordering": "-views_count"}
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertEqual(list(filtered), [self.article2, self.article1])

    def test_ordering_invalid(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(data={"ordering": "invalid"}, queryset=base_qs)
        self.assertFalse(f.is_valid())
        self.assertCountEqual(f.errors.keys(), ["ordering"])
        self.assertEqual(len(f.errors["ordering"]), 1)
        self.assertIn("Select a valid choice. ", f.errors["ordering"][0])
        self.assertIn("is not one of the available choices.", f.errors["ordering"][0])

    def test_combined_filters(self):
        base_qs = self.get_base_queryset()

        data = {
            "author": self.user1.username,
            "date_after": (self.today - timedelta(days=200)).isoformat(),
            "tags": [self.tag1.name],
        }
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1])

        data = {
            "author": self.user1.username,
            "date_before": (self.today - timedelta(days=10)).isoformat(),
            "tags": [self.tag2.name],
        }
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1])

        data = {
            "author": self.user1.username,
            "date_before": (self.today - timedelta(days=999)).isoformat(),
            "tags": [self.tag2.name],
        }
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [])

        data = {
            "date_after": (self.today - timedelta(days=999)).isoformat(),
            "tags": [self.tag1.name],
        }
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1, self.article2])

        data = {
            "category": self.category2.slug,
            "tags": [self.tag1.name],
        }
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article2])


class TestSubscriptionFeedFilter(TestCase):
    def setUp(self):
        self.subscriber = User.objects.create(
            username="subscriber", email="subscriber@test.com"
        )
        self.subscribed_author = User.objects.create(
            username="subscribed_author", email="subscribed_author@test.com"
        )
        self.other_author = User.objects.create(
            username="other_author", email="other_author@test.com"
        )
        AuthorSubscription.objects.create(
            subscriber=self.subscriber,
            author=self.subscribed_author,
        )

    def test_limits_authors_to_subscribed_to(self):
        filterset = SubscriptionFeedFilter(
            data={},
            queryset=Article.objects.none(),
            user=self.subscriber,
        )

        authors = filterset.filters["author"].queryset
        self.assertCountEqual(authors, [self.subscribed_author])

    def test_returns_no_authors_when_no_user_passed(self):
        filterset = SubscriptionFeedFilter(data={}, queryset=Article.objects.none())

        authors = filterset.filters["author"].queryset
        self.assertCountEqual(authors, [])
