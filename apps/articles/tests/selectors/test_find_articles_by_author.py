from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from articles.models import Article
from articles.selectors import find_articles_by_author
from users.models import User


class TestFindArticlesByAuthor(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author1", email="author1@test.com"
        )
        self.other_author = User.objects.create_user(
            username="author2", email="author2@test.com"
        )

        self.liker1 = User.objects.create_user(
            username="liker1", email="liker1@test.com"
        )
        self.liker2 = User.objects.create_user(
            username="liker2", email="liker2@test.com"
        )

    def test_returns_only_articles_of_given_author(self):
        own_article = Article.objects.create(
            title="Own",
            slug="own",
            author=self.author,
            preview_text="p",
            content="c",
        )
        Article.objects.create(
            title="Other",
            slug="other",
            author=self.other_author,
            preview_text="p",
            content="c",
        )

        result = list(find_articles_by_author(self.author))
        self.assertEqual(result, [own_article])

    def test_orders_by_modified_at_desc_then_id_desc(self):
        older = Article.objects.create(
            title="Older",
            slug="older",
            author=self.author,
            preview_text="p",
            content="c",
        )
        newer = Article.objects.create(
            title="Newer",
            slug="newer",
            author=self.author,
            preview_text="p",
            content="c",
        )

        now = timezone.now()
        Article.objects.filter(pk=older.pk).update(modified_at=now - timedelta(days=1))
        Article.objects.filter(pk=newer.pk).update(modified_at=now)

        result = list(find_articles_by_author(self.author))
        self.assertEqual(result, [newer, older])

    def test_orders_by_id_desc_when_modified_at_is_equal(self):
        first = Article.objects.create(
            title="First",
            slug="first",
            author=self.author,
            preview_text="p",
            content="c",
        )
        second = Article.objects.create(
            title="Second",
            slug="second",
            author=self.author,
            preview_text="p",
            content="c",
        )

        same_modified_at = timezone.now()
        Article.objects.filter(pk__in=[first.pk, second.pk]).update(
            modified_at=same_modified_at
        )

        result = list(find_articles_by_author(self.author))
        self.assertEqual(result, [second, first])

    def test_prefetches_tags(self):
        article = Article.objects.create(
            title="Tagged",
            slug="tagged",
            author=self.author,
            preview_text="p",
            content="c",
        )
        article.tags.add("tag1", "tag2")

        with self.assertNumQueries(2):
            # 1 query for the queryset with annotations/select_related
            # 1 query for tag prefetch
            result = list(find_articles_by_author(self.author))
            tags = [tag.name for tag in result[0].tags.all()]

        self.assertCountEqual(tags, ["tag1", "tag2"])

    def test_returns_articles_of_all_statuses_for_author(self):
        draft = Article.objects.create(
            title="Draft",
            slug="draft",
            author=self.author,
            preview_text="p",
            content="c",
            status="draft",
        )
        rejected = Article.objects.create(
            title="Rejected",
            slug="rejected",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status="rejected",
        )
        published = Article.objects.create(
            title="Published",
            slug="published",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status="published",
            published_at=timezone.now(),
            publish_sequence=1,
        )

        result = find_articles_by_author(self.author)

        self.assertCountEqual(result, [draft, rejected, published])
