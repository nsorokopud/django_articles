from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from taggit.models import Tag

from articles.filters import ArticleFilter
from articles.models import Article, ArticleCategory
from users.models import User


class TestArticleFilter(TestCase):
    def setUp(self):
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
        )
        self.article1.created_at = timezone.now() - timedelta(days=100)
        self.article1.views_count = 5
        self.article1.save(update_fields=["created_at", "views_count"])
        self.article1.tags.add(self.tag1, self.tag2)

        self.article2 = Article.objects.create(
            title="a2",
            slug="a2",
            author=self.user2,
            category=self.category2,
            preview_text="Preview2",
            content="Content2",
        )
        self.article2.created_at = timezone.now() - timedelta(days=1)
        self.article2.views_count = 100
        self.article2.save(update_fields=["created_at", "views_count"])
        self.article2.tags.add(self.tag1)
        self.article2.users_that_liked.add(self.user1)

    def test_filter_by_author(self):
        f = ArticleFilter(data={"author": self.user1.username})
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article1])

        f = ArticleFilter(data={"author": self.user2.username})
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article2])

    def test_filter_by_author_invalid(self):
        f = ArticleFilter(data={"author": "non-existent"})
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
        f = ArticleFilter(data={"category": self.category1.slug})
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article1])

        f = ArticleFilter(data={"category": self.category2.slug})
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article2])

    def test_filter_by_category_invalid(self):
        f = ArticleFilter(data={"category": "non-existent"})
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
        today = timezone.now().date()

        data = {
            "date_after": (today - timedelta(days=2)).isoformat(),
        }
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article2])

        data = {
            "date_before": (today - timedelta(days=2)).isoformat(),
        }
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article1])

        data = {
            "date_before": (today - timedelta(days=1)).isoformat(),
            "date_after": (today - timedelta(days=1)).isoformat(),
        }
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article2])

    def test_filter_by_date_invalid(self):
        data = {
            "date_before": "abc",
            "date_after": "xyz",
        }
        f = ArticleFilter(data=data)
        self.assertFalse(f.is_valid())
        self.assertEqual(f.errors, {"date": ["Enter a valid date."]})

    def test_filter_by_tags(self):
        data = {"tags": [self.tag1.name, self.tag2.name]}
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article1])

    def test_filter_by_tags_invalid(self):
        f = ArticleFilter(data={"tags": ["non-existent-tag"]})
        self.assertFalse(f.is_valid())
        self.assertCountEqual(f.errors.keys(), ["tags"])
        self.assertEqual(len(f.errors["tags"]), 1)
        self.assertIn("Select a valid choice. ", f.errors["tags"][0])
        self.assertIn("is not one of the available choices.", f.errors["tags"][0])

    def test_filter_by_search(self):
        filtered = ArticleFilter(data={"q": "a1"}).qs
        self.assertCountEqual(filtered, [self.article1])

        filtered = ArticleFilter(data={"q": "a2"}).qs
        self.assertCountEqual(filtered, [self.article2])

        filtered = ArticleFilter(data={"q": "ent1"}).qs
        self.assertCountEqual(filtered, [self.article1])

        filtered = ArticleFilter(data={"q": "content2"}).qs
        self.assertCountEqual(filtered, [self.article2])

        filtered = ArticleFilter(data={"q": "Cat1"}).qs
        self.assertCountEqual(filtered, [self.article1])

        filtered = ArticleFilter(data={"q": "at2"}).qs
        self.assertCountEqual(filtered, [self.article2])

        filtered = ArticleFilter(data={"q": "qafwejkfb"}).qs
        self.assertCountEqual(filtered, [])

    def test_ordering(self):
        data = {"ordering": "created_at"}
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article2, self.article1])

        data = {"ordering": "-created_at"}
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article1, self.article2])

        data = {"ordering": "likes_count"}
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article1, self.article2])

        data = {"ordering": "-likes_count"}
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article2, self.article1])

        data = {"ordering": "views_count"}
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article1, self.article2])

        data = {"ordering": "-views_count"}
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article2, self.article1])

    def test_ordering_invalid(self):
        f = ArticleFilter(data={"ordering": "invalid"})
        self.assertFalse(f.is_valid())
        self.assertCountEqual(f.errors.keys(), ["ordering"])
        self.assertEqual(len(f.errors["ordering"]), 1)
        self.assertIn("Select a valid choice. ", f.errors["ordering"][0])
        self.assertIn("is not one of the available choices.", f.errors["ordering"][0])

    def test_combined_filters(self):
        data = {
            "author": self.user1.username,
            "date_after": (timezone.now() - timedelta(days=200)).isoformat(),
            "tags": [self.tag1.name],
        }
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article1])

        data = {
            "author": self.user1.username,
            "date_before": (timezone.now() - timedelta(days=10)).isoformat(),
            "tags": [self.tag2.name],
        }
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article1])

        data = {
            "author": self.user1.username,
            "date_before": (timezone.now() - timedelta(days=999)).isoformat(),
            "tags": [self.tag2.name],
        }
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article1])

        data = {
            "date_after": (timezone.now() - timedelta(days=999)).isoformat(),
            "tags": [self.tag1.name],
        }
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article1, self.article2])

        data = {
            "category": self.category2.slug,
            "tags": [self.tag1.name],
        }
        filtered = ArticleFilter(data=data).qs
        self.assertCountEqual(filtered, [self.article2])
