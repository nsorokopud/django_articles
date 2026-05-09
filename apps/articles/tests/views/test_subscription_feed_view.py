from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleStatus
from articles.settings import ARTICLES_PER_PAGE_COUNT
from users.models import AuthorSubscription, User


class TestSubscriptionFeedView(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.redis_patch = patch(
            "articles.cache.view_counts.get_cached_article_views", return_value=0
        )
        cls.redis_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.redis_patch.stop()
        super().tearDownClass()

    def setUp(self):
        self.subscriber = User.objects.create_user(username="sub", email="sub@test.com")
        self.author1 = User.objects.create_user(username="a1", email="a1@test.com")
        self.author2 = User.objects.create_user(username="a2", email="a2@test.com")
        self.unsubscribed_author = User.objects.create_user(
            username="unsubscribed_author", email="unsubscribed_author@test.com"
        )

        self.category = ArticleCategory.objects.create(title="cat", slug="cat")

        AuthorSubscription.objects.create(
            subscriber=self.subscriber, author=self.author1
        )
        AuthorSubscription.objects.create(
            subscriber=self.subscriber, author=self.author2
        )

        self.feed_article1 = Article.objects.create(
            title="Subscribed published article 1",
            slug="subscribed-published-article-1",
            category=self.category,
            author=self.author1,
            preview_text="Preview 1",
            content="Content 1",
            content_text="Content 1",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=100,
        )
        self.feed_article2 = Article.objects.create(
            title="Subscribed published article 2",
            slug="subscribed-published-article-2",
            category=self.category,
            author=self.author2,
            preview_text="Preview 2",
            content="Content 2",
            content_text="Content 2",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=90,
        )
        self.unsubscribed_article = Article.objects.create(
            title="Unsubscribed published article",
            slug="unsubscribed-published-article",
            category=self.category,
            author=self.unsubscribed_author,
            preview_text="Preview 3",
            content="Content 3",
            content_text="Content 3",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=80,
        )
        self.unpublished_subscribed_article = Article.objects.create(
            title="Subscribed unpublished article",
            slug="subscribed-unpublished-article",
            category=self.category,
            author=self.author1,
            preview_text="Preview 4",
            content="Content 4",
        )

    def test_requires_login(self):
        response = self.client.get(reverse("subscription-feed"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('subscription-feed')}"
        )

    def test_renders_for_authenticated_user(self):
        self.client.force_login(self.subscriber)

        response = self.client.get(reverse("subscription-feed"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "articles/article_list_page.html")

    def test_shows_only_published_articles_from_subscribed_authors(
        self,
    ):
        self.client.force_login(self.subscriber)

        response = self.client.get(reverse("subscription-feed"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.feed_article1.title)
        self.assertContains(response, self.feed_article2.title)

        self.assertNotContains(response, self.unsubscribed_article.title)
        self.assertNotContains(response, self.unpublished_subscribed_article.title)

    def test_context_values(self):
        self.client.force_login(self.subscriber)

        response = self.client.get(reverse("subscription-feed"))

        self.assertEqual(response.context["page_title"], "Subscription feed")
        self.assertEqual(
            response.context["empty_message"],
            "No matching articles from your subscriptions yet",
        )
        self.assertTrue(response.context["show_filters"])
        self.assertFalse(response.context["author_filter_ajax_enabled"])
        self.assertEqual(response.context["page_key"], "subscriptions")
        self.assertTrue(response.context["is_subscriptions_feed_page_one"])
        self.assertEqual(response.context["latest_article_publish_sequence"], 100)

    def test_author_filter_contains_only_subscribed_authors(self):
        self.client.force_login(self.subscriber)

        response = self.client.get(reverse("subscription-feed"))

        filterset = response.context["filter"]
        author_queryset = filterset.form.fields["author"].queryset

        self.assertIn(self.author1, author_queryset)
        self.assertIn(self.author2, author_queryset)
        self.assertNotIn(self.unsubscribed_author, author_queryset)
        self.assertNotIn(self.subscriber, author_queryset)

    def test_can_filter_subscription_feed_by_subscribed_author(self):
        self.client.force_login(self.subscriber)

        response = self.client.get(
            reverse("subscription-feed"), {"author": self.author1.username}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.feed_article1.title)
        self.assertNotContains(response, self.feed_article2.title)

    def test_updates_last_seen_publish_sequence_on_page_one(self):
        self.client.force_login(self.subscriber)
        self.assertEqual(self.subscriber.subscriptions_last_seen_publish_sequence, 0)

        response = self.client.get(reverse("subscription-feed"))

        self.assertEqual(response.status_code, 200)

        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.subscriptions_last_seen_publish_sequence, 100)

    def test_does_not_update_last_seen_publish_sequence_on_non_first_page(
        self,
    ):
        for i in range(ARTICLES_PER_PAGE_COUNT + 1):
            Article.objects.create(
                title=f"Extra subscribed article {i}",
                slug=f"extra-subscribed-article-{i}",
                category=self.category,
                author=self.author1,
                preview_text=f"Preview extra {i}",
                content=f"Content extra {i}",
                content_text=f"Content extra {i}",
                status=ArticleStatus.PUBLISHED,
                published_at=timezone.now(),
                publish_sequence=1000 + i,
            )

        self.client.force_login(self.subscriber)

        response = self.client.get(reverse("subscription-feed"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_subscriptions_feed_page_one"])

        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.subscriptions_last_seen_publish_sequence, 0)

    def test_empty_state_when_user_has_no_subscriptions(self):
        user = User.objects.create_user(username="u", email="u@test.com")
        self.client.force_login(user)

        response = self.client.get(reverse("subscription-feed"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No matching articles from your subscriptions yet"
        )
