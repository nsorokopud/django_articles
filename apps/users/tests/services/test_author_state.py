from django.test import TestCase
from django.utils import timezone

from articles.models import Article, ArticleStatus
from users.models import User
from users.services.author_state import (
    advance_latest_article_publish_sequence,
    recompute_latest_article_publish_sequence,
)


class TestAdvanceLatestArticlePublishSequence(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@test.com", latest_article_publish_sequence=10
        )

    def test_updates_sequence_when_new_value_is_greater(self):
        advance_latest_article_publish_sequence(
            user_id=self.user.id, publish_sequence=15
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 15)

    def test_does_not_update_sequence_when_new_value_is_equal(self):
        advance_latest_article_publish_sequence(
            user_id=self.user.id, publish_sequence=10
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 10)

    def test_does_not_update_sequence_when_new_value_is_smaller(self):
        advance_latest_article_publish_sequence(
            user_id=self.user.id, publish_sequence=5
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 10)

    def test_does_nothing_when_user_does_not_exist(self):
        advance_latest_article_publish_sequence(user_id=999999, publish_sequence=20)

        self.user.refresh_from_db()
        self.assertEqual(self.user.latest_article_publish_sequence, 10)


class TestRecomputeLatestArticlePublishSequence(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author",
            email="author@test.com",
            latest_article_publish_sequence=999,
        )

    def create_published_article(self, *, slug: str, sequence: int) -> Article:
        return Article.objects.create(
            author=self.user,
            title=slug,
            slug=slug,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=sequence,
        )

    def test_recomputes_to_latest_currently_published_article(self):
        self.create_published_article(slug="older", sequence=10)
        self.create_published_article(slug="newer", sequence=25)

        result = recompute_latest_article_publish_sequence(user_id=self.user.id)

        self.user.refresh_from_db()
        self.assertEqual(result, 25)
        self.assertEqual(self.user.latest_article_publish_sequence, 25)

    def test_recomputes_to_zero_when_author_has_no_published_articles(self):
        result = recompute_latest_article_publish_sequence(user_id=self.user.id)

        self.user.refresh_from_db()
        self.assertEqual(result, 0)
        self.assertEqual(self.user.latest_article_publish_sequence, 0)

    def test_ignores_draft_articles_with_no_publish_sequence(self):
        self.create_published_article(slug="published", sequence=10)
        Article.objects.create(
            author=self.user,
            title="Draft",
            slug="draft",
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.DRAFT,
        )

        result = recompute_latest_article_publish_sequence(user_id=self.user.id)

        self.user.refresh_from_db()
        self.assertEqual(result, 10)
        self.assertEqual(self.user.latest_article_publish_sequence, 10)
