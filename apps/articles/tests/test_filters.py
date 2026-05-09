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
        self.draft_only_user = User.objects.create(
            username="draft_only_user", email="draft_only_user@test.com"
        )

        self.category1 = ArticleCategory.objects.create(title="Cat1", slug="cat1")
        self.category2 = ArticleCategory.objects.create(title="Cat2", slug="cat2")
        self.draft_only_category = ArticleCategory.objects.create(
            title="Draft Only Cat", slug="draft-only-cat"
        )

        self.tag1 = Tag.objects.create(name="tag1")
        self.tag2 = Tag.objects.create(name="tag2")
        self.draft_only_tag = Tag.objects.create(name="draft-only-tag")

        self.article1 = Article.objects.create(
            title="Article1",
            slug="a1",
            author=self.user1,
            category=self.category1,
            preview_text="Preview 1",
            content="Content 1",
            content_text="Content 1",
            status=ArticleStatus.PUBLISHED,
            published_at=self.now - timedelta(days=100),
            publish_sequence=1,
            views_count=5,
        )
        self.article1.created_at = self.article1.published_at
        self.article1.save(update_fields=["created_at"])
        self.article1.tags.add(self.tag1, self.tag2)

        self.article2 = Article.objects.create(
            title="Article2",
            slug="a2",
            author=self.user2,
            category=self.category2,
            preview_text="Preview 2",
            content="Content 2",
            content_text="Content 2",
            status=ArticleStatus.PUBLISHED,
            published_at=self.now - timedelta(days=1),
            publish_sequence=2,
            views_count=100,
            likes_count=1,
        )
        self.article2.created_at = self.article2.published_at
        self.article2.save(update_fields=["created_at"])
        self.article2.tags.add(self.tag1)
        self.article2.users_that_liked.add(self.user1)

        self.draft_article = Article.objects.create(
            title="Draft Article",
            slug="draft-article",
            author=self.draft_only_user,
            category=self.draft_only_category,
            preview_text="Draft preview",
            content="Draft content",
            content_text="Draft content",
            status=ArticleStatus.DRAFT,
        )
        self.draft_article.tags.add(self.draft_only_tag)

    def get_base_queryset(self):
        return find_published_articles()

    def test_unbound_filter_does_not_load_author_or_tag_choices(self):
        f = ArticleFilter(data=None, queryset=self.get_base_queryset())

        self.assertFalse(f.is_bound)
        self.assertCountEqual(f.filters["author"].queryset, [])
        self.assertCountEqual(f.filters["tags"].queryset, [])

    def test_bound_filter_without_author_or_tags_does_not_load_author_or_tag_choices(
        self,
    ):
        f = ArticleFilter(data={}, queryset=self.get_base_queryset())

        self.assertTrue(f.is_bound)
        self.assertCountEqual(f.filters["author"].queryset, [])
        self.assertCountEqual(f.filters["tags"].queryset, [])

    def test_bound_filter_loads_only_selected_author_choice(self):
        f = ArticleFilter(
            data={"author": self.user1.username}, queryset=self.get_base_queryset()
        )

        self.assertCountEqual(f.filters["author"].queryset, [self.user1])
        self.assertCountEqual(f.filters["tags"].queryset, [])

    def test_bound_filter_loads_only_selected_tag_choices(self):
        f = ArticleFilter(
            data={"tags": [self.tag1.name, self.tag2.name]},
            queryset=self.get_base_queryset(),
        )

        self.assertCountEqual(f.filters["author"].queryset, [])
        self.assertCountEqual(f.filters["tags"].queryset, [self.tag1, self.tag2])

    def test_author_queryset_does_not_include_draft_only_author(self):
        f = ArticleFilter(
            data={"author": self.draft_only_user.username},
            queryset=self.get_base_queryset(),
        )

        self.assertCountEqual(f.filters["author"].queryset, [])
        self.assertFalse(f.is_valid())
        self.assertIn("author", f.errors)

    def test_tags_queryset_does_not_include_draft_only_tag(self):
        f = ArticleFilter(
            data={"tags": [self.draft_only_tag.name]}, queryset=self.get_base_queryset()
        )

        self.assertCountEqual(f.filters["tags"].queryset, [])
        self.assertFalse(f.is_valid())
        self.assertIn("tags", f.errors)

    def test_category_queryset_contains_only_categories_with_published_articles(self):
        f = ArticleFilter(data={}, queryset=self.get_base_queryset())

        self.assertCountEqual(
            f.filters["category"].queryset, [self.category1, self.category2]
        )
        self.assertNotIn(self.draft_only_category, list(f.filters["category"].queryset))

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

    def test_filter_by_author_rejects_draft_only_author(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(
            data={"author": self.draft_only_user.username}, queryset=base_qs
        )

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

    def test_filter_by_category_rejects_draft_only_category(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(
            data={"category": self.draft_only_category.slug}, queryset=base_qs
        )

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

        data = {"date_after": (self.today - timedelta(days=2)).isoformat()}
        filtered = ArticleFilter(data=data, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article2])

        data = {"date_before": (self.today - timedelta(days=2)).isoformat()}
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

        data = {"date_before": "abc", "date_after": "xyz"}
        f = ArticleFilter(data=data, queryset=base_qs)
        self.assertFalse(f.is_valid())
        self.assertEqual(f.errors, {"date": ["Enter a valid date."]})

    def test_filter_by_tags(self):
        base_qs = self.get_base_queryset()

        data = {"tags": [self.tag1.name, self.tag2.name]}
        f = ArticleFilter(data=data, queryset=base_qs)

        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article1])

    def test_filter_by_single_tag(self):
        base_qs = self.get_base_queryset()

        data = {"tags": [self.tag1.name]}
        f = ArticleFilter(data=data, queryset=base_qs)

        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article1, self.article2])

    def test_filter_by_tags_invalid(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(data={"tags": ["non-existent-tag"]}, queryset=base_qs)
        self.assertFalse(f.is_valid())
        self.assertCountEqual(f.errors.keys(), ["tags"])
        self.assertEqual(len(f.errors["tags"]), 1)
        self.assertIn("Select a valid choice. ", f.errors["tags"][0])
        self.assertIn("is not one of the available choices.", f.errors["tags"][0])

    def test_filter_by_tags_rejects_draft_only_tag(self):
        base_qs = self.get_base_queryset()

        f = ArticleFilter(data={"tags": [self.draft_only_tag.name]}, queryset=base_qs)

        self.assertFalse(f.is_valid())
        self.assertCountEqual(f.errors.keys(), ["tags"])
        self.assertEqual(len(f.errors["tags"]), 1)
        self.assertIn("Select a valid choice. ", f.errors["tags"][0])
        self.assertIn("is not one of the available choices.", f.errors["tags"][0])

    def test_filter_by_search(self):
        base_qs = self.get_base_queryset()

        filtered = ArticleFilter(data={"q": "article"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1, self.article2])

        filtered = ArticleFilter(data={"q": "ticle2"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article2])

        filtered = ArticleFilter(data={"q": "preview"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1, self.article2])

        filtered = ArticleFilter(data={"q": "Content"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1, self.article2])

        filtered = ArticleFilter(data={"q": "Content 1"}, queryset=base_qs).qs
        self.assertCountEqual(filtered, [self.article1])

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
        f = ArticleFilter(data=data, queryset=base_qs)
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article1])

        data = {
            "author": self.user1.username,
            "date_before": (self.today - timedelta(days=10)).isoformat(),
            "tags": [self.tag2.name],
        }
        f = ArticleFilter(data=data, queryset=base_qs)
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article1])

        data = {
            "author": self.user1.username,
            "date_before": (self.today - timedelta(days=999)).isoformat(),
            "tags": [self.tag2.name],
        }
        f = ArticleFilter(data=data, queryset=base_qs)
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [])

        data = {
            "date_after": (self.today - timedelta(days=999)).isoformat(),
            "tags": [self.tag1.name],
        }
        f = ArticleFilter(data=data, queryset=base_qs)
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article1, self.article2])

        data = {"category": self.category2.slug, "tags": [self.tag1.name]}
        f = ArticleFilter(data=data, queryset=base_qs)
        self.assertTrue(f.is_valid())
        self.assertCountEqual(f.qs, [self.article2])


class TestSubscriptionFeedFilter(TestCase):
    def setUp(self):
        self.subscriber = User.objects.create(
            username="subscriber", email="subscriber@test.com"
        )
        self.subscribed_author = User.objects.create(
            username="subscribed_author", email="subscribed_author@test.com"
        )
        self.subscribed_author_without_published_articles = User.objects.create(
            username="no_published", email="no_published@test.com"
        )
        self.other_author = User.objects.create(
            username="other_author", email="other_author@test.com"
        )
        Article.objects.create(
            author=self.subscribed_author,
            title="Published",
            slug="published",
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )
        Article.objects.create(
            author=self.subscribed_author_without_published_articles,
            title="Draft",
            slug="draft",
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.DRAFT,
        )
        AuthorSubscription.objects.create(
            subscriber=self.subscriber, author=self.subscribed_author
        )
        AuthorSubscription.objects.create(
            subscriber=self.subscriber,
            author=self.subscribed_author_without_published_articles,
        )

    def test_limits_authors_to_subscribed_to_with_published_articles(self):
        filterset = SubscriptionFeedFilter(
            data={}, queryset=Article.objects.none(), user=self.subscriber
        )

        authors = filterset.filters["author"].queryset
        self.assertCountEqual(authors, [self.subscribed_author])

    def test_excludes_subscribed_authors_without_published_articles(self):
        filterset = SubscriptionFeedFilter(
            data={}, queryset=Article.objects.none(), user=self.subscriber
        )

        authors = filterset.filters["author"].queryset
        self.assertNotIn(self.subscribed_author_without_published_articles, authors)

    def test_returns_no_authors_when_no_user_passed(self):
        filterset = SubscriptionFeedFilter(data={}, queryset=Article.objects.none())

        authors = filterset.filters["author"].queryset
        self.assertCountEqual(authors, [])
