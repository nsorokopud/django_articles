# pylint: disable=C0302
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from articles.constants import DEFAULT_DRAFT_ARTICLE_TITLE
from articles.models import Article, ArticleStatus
from articles.services.articles import _build_article_slug_candidate
from articles.services.publishing import (
    _has_meaningful_html_content,
    _normalize_article_text,
    _validate_article_ready,
    get_next_article_publish_sequence_value,
    publish_article,
    reject_article,
    submit_article_for_review,
    unpublish_article,
    withdraw_article_from_review,
)
from users.models import User


class ArticleServiceBaseTestCase(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )

    def create_article(self, *, status=ArticleStatus.DRAFT) -> Article:
        published_at = None
        publish_sequence = None

        if status == ArticleStatus.PUBLISHED:
            published_at = timezone.now()
            publish_sequence = 123

        return Article.objects.create(
            title="a",
            slug=_build_article_slug_candidate("a", use_suffix=True),
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=status,
            published_at=published_at,
            publish_sequence=publish_sequence,
        )


class TestSubmitArticleForReview(ArticleServiceBaseTestCase):
    def test_submit_article_for_review_from_draft(self):
        article = self.create_article(status=ArticleStatus.DRAFT)
        result = submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(result.id, article.id)
        self.assertEqual(article.status, ArticleStatus.PENDING_REVIEW)

    def test_submit_article_for_review_from_pending_review_raises_error(self):
        article = self.create_article(status=ArticleStatus.PENDING_REVIEW)

        with self.assertRaisesMessage(
            ValueError, "only draft articles can be submitted for review"
        ):
            submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.PENDING_REVIEW)

    def test_submit_article_for_review_from_published_raises_error(self):
        article = self.create_article(status=ArticleStatus.PUBLISHED)

        with self.assertRaisesMessage(
            ValueError, "only draft articles can be submitted for review"
        ):
            submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.PUBLISHED)
        self.assertIsNotNone(article.published_at)
        self.assertIsNotNone(article.publish_sequence)

    def test_submit_article_for_review_from_rejected_raises_error(self):
        article = self.create_article(status=ArticleStatus.REJECTED)

        with self.assertRaisesMessage(
            ValueError, "only draft articles can be submitted for review"
        ):
            submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.REJECTED)

    def test_raises_when_title_is_blank(self):
        article = self.create_article(status=ArticleStatus.DRAFT)
        article.title = "   "
        article.save(update_fields=["title"])

        with self.assertRaisesMessage(
            ValueError, "Title is required before submission for review."
        ):
            submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    def test_raises_when_title_is_default_draft_title(self):
        article = self.create_article(status=ArticleStatus.DRAFT)
        article.title = DEFAULT_DRAFT_ARTICLE_TITLE
        article.save(update_fields=["title"])

        with self.assertRaisesMessage(
            ValueError, "Title is required before submission for review."
        ):
            submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    def test_raises_when_preview_text_is_blank(self):
        article = self.create_article(status=ArticleStatus.DRAFT)
        article.preview_text = "   "
        article.save(update_fields=["preview_text"])

        with self.assertRaisesMessage(
            ValueError, "Preview text is required before submission for review."
        ):
            submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    def test_raises_when_content_is_empty_html(self):
        article = self.create_article(status=ArticleStatus.DRAFT)
        article.content = "<p><br></p>"
        article.save(update_fields=["content"])

        with self.assertRaisesMessage(
            ValueError, "Content is required before submission for review."
        ):
            submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    def test_clears_review_metadata(self):
        reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@test.com"
        )
        article = self.create_article(status=ArticleStatus.DRAFT)
        article.review_note = "Old review note."
        article.reviewed_at = timezone.now()
        article.reviewed_by = reviewer
        article.save(update_fields=["review_note", "reviewed_at", "reviewed_by"])

        submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.PENDING_REVIEW)
        self.assertEqual(article.review_note, "")
        self.assertIsNone(article.reviewed_at)
        self.assertIsNone(article.reviewed_by)

    @patch("articles.services.publishing.invalidate_article_slug_id")
    def test_invalidates_article_slug_id_cache(self, mock_invalidate):
        article = self.create_article(status=ArticleStatus.DRAFT)

        with self.captureOnCommitCallbacks(execute=True):
            submit_article_for_review(article_id=article.id)

        mock_invalidate.assert_called_once_with(article_slug=article.slug)

    @patch("articles.services.publishing.invalidate_article_slug_id")
    def test_does_not_invalidate_cache_before_commit(self, mock_invalidate):
        article = self.create_article(status=ArticleStatus.DRAFT)

        with self.captureOnCommitCallbacks(execute=False):
            submit_article_for_review(article_id=article.id)

        mock_invalidate.assert_not_called()

    @patch("articles.services.publishing.invalidate_article_slug_id")
    def test_does_not_invalidate_cache_when_submit_fails(self, mock_invalidate):
        article = self.create_article(status=ArticleStatus.REJECTED)

        with self.assertRaisesMessage(
            ValueError, "only draft articles can be submitted for review"
        ):
            submit_article_for_review(article_id=article.id)

        mock_invalidate.assert_not_called()


class TestWithdrawArticleFromReview(ArticleServiceBaseTestCase):
    def test_withdraw_article_from_review_from_pending_review(self):
        article = self.create_article(status=ArticleStatus.PENDING_REVIEW)
        result = withdraw_article_from_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(result.id, article.id)
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    def test_withdraw_article_from_review_from_draft_raises_error(self):
        article = self.create_article(status=ArticleStatus.DRAFT)

        with self.assertRaisesMessage(
            ValueError, "only articles pending review can be withdrawn from review"
        ):
            withdraw_article_from_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    def test_withdraw_article_from_review_from_rejected_raises_error(self):
        article = self.create_article(status=ArticleStatus.REJECTED)

        with self.assertRaisesMessage(
            ValueError, "only articles pending review can be withdrawn from review"
        ):
            withdraw_article_from_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.REJECTED)

    def test_withdraw_article_from_review_from_published_raises_error(self):
        article = self.create_article(status=ArticleStatus.PUBLISHED)

        with self.assertRaisesMessage(
            ValueError, "only articles pending review can be withdrawn from review"
        ):
            withdraw_article_from_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.PUBLISHED)
        self.assertIsNotNone(article.published_at)
        self.assertIsNotNone(article.publish_sequence)


class TestPublishArticle(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
            latest_article_publish_sequence=0,
        )
        self.article = Article.objects.create(
            author=self.author,
            title="a",
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PENDING_REVIEW,
        )

    def test_publishing_two_articles_assigns_unique_increasing_sequences(self):
        first_article = Article.objects.create(
            author=self.author,
            title="First article",
            slug="first-article",
            preview_text="First preview",
            content="<p>First body</p>",
            content_text="First body",
            status=ArticleStatus.PENDING_REVIEW,
        )
        second_article = Article.objects.create(
            author=self.author,
            title="Second article",
            slug="second-article",
            preview_text="Second preview",
            content="<p>Second body</p>",
            content_text="Second body",
            status=ArticleStatus.PENDING_REVIEW,
        )

        with self.captureOnCommitCallbacks(execute=True):
            first_published = publish_article(article_id=first_article.id)

        with self.captureOnCommitCallbacks(execute=True):
            second_published = publish_article(article_id=second_article.id)

        first_article.refresh_from_db()
        second_article.refresh_from_db()
        self.author.refresh_from_db()

        self.assertEqual(first_article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(second_article.status, ArticleStatus.PUBLISHED)

        sequences = [first_article.publish_sequence, second_article.publish_sequence]

        self.assertNotIn(None, sequences)
        self.assertEqual(len(set(sequences)), 2)
        self.assertGreater(
            second_article.publish_sequence, first_article.publish_sequence
        )

        self.assertEqual(
            self.author.latest_article_publish_sequence, second_article.publish_sequence
        )

        self.assertEqual(first_published.id, first_article.id)
        self.assertEqual(second_published.id, second_article.id)

    @patch("articles.services.publishing.notify_article_published")
    def test_sets_published_fields_review_metadata_and_updates_author_sequence(
        self, mock_notify
    ):
        reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@test.com"
        )

        before = timezone.now()

        with self.captureOnCommitCallbacks(execute=True):
            published = publish_article(article_id=self.article.id, reviewer=reviewer)

        after = timezone.now()

        self.article.refresh_from_db()
        self.author.refresh_from_db()

        self.assertEqual(published.id, self.article.id)
        self.assertEqual(self.article.status, ArticleStatus.PUBLISHED)
        self.assertIsNotNone(self.article.published_at)
        self.assertIsNotNone(self.article.publish_sequence)

        self.assertGreaterEqual(self.article.published_at, before)
        self.assertLessEqual(self.article.published_at, after)

        self.assertEqual(self.article.review_note, "")
        self.assertIsNotNone(self.article.reviewed_at)
        self.assertGreaterEqual(self.article.reviewed_at, before)
        self.assertLessEqual(self.article.reviewed_at, after)
        self.assertEqual(self.article.reviewed_by, reviewer)

        self.assertEqual(
            self.author.latest_article_publish_sequence, self.article.publish_sequence
        )

        mock_notify.assert_called_once_with(
            recipient_id=self.author.id,
            article_id=self.article.id,
            article_slug=self.article.slug,
            article_title=self.article.title,
            actor_id=reviewer.id,
            publish_sequence=self.article.publish_sequence,
        )

    @patch("articles.services.publishing.notify_article_published")
    def test_sets_review_metadata_when_publishing(self, mock_notify):
        reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@test.com"
        )
        self.article.review_note = "Old review note."
        self.article.reviewed_at = timezone.now()
        self.article.reviewed_by = None
        self.article.save(update_fields=["review_note", "reviewed_at", "reviewed_by"])

        before = timezone.now()

        with self.captureOnCommitCallbacks(execute=True):
            publish_article(article_id=self.article.id, reviewer=reviewer)

        after = timezone.now()

        self.article.refresh_from_db()

        self.assertEqual(self.article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(self.article.review_note, "")
        self.assertIsNotNone(self.article.reviewed_at)
        self.assertGreaterEqual(self.article.reviewed_at, before)
        self.assertLessEqual(self.article.reviewed_at, after)
        self.assertEqual(self.article.reviewed_by, reviewer)

        mock_notify.assert_called_once()

    @patch("articles.services.publishing.notify_article_published")
    def test_sets_review_metadata_to_none_when_published_without_reviewer(
        self, mock_notify
    ):
        with self.captureOnCommitCallbacks(execute=True):
            publish_article(article_id=self.article.id)

        self.article.refresh_from_db()

        self.assertEqual(self.article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(self.article.review_note, "")
        self.assertIsNotNone(self.article.reviewed_at)
        self.assertIsNone(self.article.reviewed_by)

        mock_notify.assert_called_once_with(
            recipient_id=self.author.id,
            article_id=self.article.id,
            article_slug=self.article.slug,
            article_title=self.article.title,
            actor_id=None,
            publish_sequence=self.article.publish_sequence,
        )

    @patch("articles.services.publishing.notify_article_published")
    def test_raises_when_not_pending_review(self, mock_notify):
        reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@test.com"
        )
        reviewed_at = timezone.now()

        self.article.status = ArticleStatus.REJECTED
        self.article.review_note = "Needs more sources."
        self.article.reviewed_at = reviewed_at
        self.article.reviewed_by = reviewer
        self.article.save(
            update_fields=["status", "review_note", "reviewed_at", "reviewed_by"]
        )

        with self.assertRaisesMessage(
            ValueError, "only articles pending review can be published"
        ):
            publish_article(article_id=self.article.id, reviewer=reviewer)

        self.article.refresh_from_db()

        self.assertEqual(self.article.status, ArticleStatus.REJECTED)
        self.assertEqual(self.article.review_note, "Needs more sources.")
        self.assertEqual(self.article.reviewed_at, reviewed_at)
        self.assertEqual(self.article.reviewed_by, reviewer)
        self.assertIsNone(self.article.published_at)
        self.assertIsNone(self.article.publish_sequence)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_published")
    @patch("articles.services.publishing.get_next_article_publish_sequence_value")
    @patch("articles.services.publishing.advance_latest_article_publish_sequence")
    def test_raises_for_already_published_article(
        self, mock_advance, mock_get_next, mock_notify
    ):
        reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@test.com"
        )
        published_at = timezone.now()
        reviewed_at = timezone.now()

        self.article.status = ArticleStatus.PUBLISHED
        self.article.published_at = published_at
        self.article.publish_sequence = 123
        self.article.reviewed_at = reviewed_at
        self.article.reviewed_by = reviewer
        self.article.save(
            update_fields=[
                "status",
                "published_at",
                "publish_sequence",
                "reviewed_at",
                "reviewed_by",
            ]
        )

        self.author.latest_article_publish_sequence = 123
        self.author.save(update_fields=["latest_article_publish_sequence"])

        with self.assertRaisesMessage(
            ValueError, "only articles pending review can be published"
        ):
            publish_article(article_id=self.article.id, reviewer=reviewer)

        self.article.refresh_from_db()
        self.author.refresh_from_db()

        self.assertEqual(self.article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(self.article.publish_sequence, 123)
        self.assertEqual(self.article.published_at, published_at)
        self.assertEqual(self.article.reviewed_at, reviewed_at)
        self.assertEqual(self.article.reviewed_by, reviewer)
        self.assertEqual(self.author.latest_article_publish_sequence, 123)

        mock_get_next.assert_not_called()
        mock_advance.assert_not_called()
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_published")
    @patch("articles.services.publishing.advance_latest_article_publish_sequence")
    @patch("articles.services.publishing.get_next_article_publish_sequence_value")
    def test_calls_advance_with_author_id_and_sequence(
        self,
        mock_get_next,
        mock_advance,
        mock_notify,
    ):
        mock_get_next.return_value = 777

        with self.captureOnCommitCallbacks(execute=True):
            publish_article(article_id=self.article.id)

        mock_advance.assert_called_once_with(
            user_id=self.author.id, publish_sequence=777
        )

        self.article.refresh_from_db()

        self.assertEqual(self.article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(self.article.publish_sequence, 777)
        self.assertIsNotNone(self.article.published_at)
        self.assertIsNotNone(self.article.reviewed_at)
        self.assertIsNone(self.article.reviewed_by)

        mock_notify.assert_called_once_with(
            recipient_id=self.author.id,
            article_id=self.article.id,
            article_slug=self.article.slug,
            article_title=self.article.title,
            actor_id=None,
            publish_sequence=777,
        )

    @patch("articles.services.publishing.notify_article_published")
    def test_publish_notifies_author_when_reviewer_is_none(self, mock_notify):
        with self.captureOnCommitCallbacks(execute=True):
            published = publish_article(article_id=self.article.id)

        mock_notify.assert_called_once_with(
            recipient_id=self.author.id,
            article_id=published.id,
            article_slug=published.slug,
            article_title=published.title,
            actor_id=None,
            publish_sequence=published.publish_sequence,
        )

    @patch("articles.services.publishing.notify_article_published")
    def test_publish_notifies_author_when_reviewer_is_not_author(self, mock_notify):
        reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@test.com"
        )

        with self.captureOnCommitCallbacks(execute=True):
            published = publish_article(article_id=self.article.id, reviewer=reviewer)

        self.article.refresh_from_db()

        self.assertEqual(self.article.reviewed_by, reviewer)

        mock_notify.assert_called_once_with(
            recipient_id=self.author.id,
            article_id=published.id,
            article_slug=published.slug,
            article_title=published.title,
            actor_id=reviewer.id,
            publish_sequence=published.publish_sequence,
        )

    @patch("articles.services.publishing.notify_article_published")
    def test_publish_does_not_notify_when_reviewer_is_author(self, mock_notify):
        with self.captureOnCommitCallbacks(execute=True):
            publish_article(article_id=self.article.id, reviewer=self.author)

        self.article.refresh_from_db()

        self.assertEqual(self.article.reviewed_by, self.author)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_published")
    def test_publish_does_not_notify_before_commit(self, mock_notify):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            publish_article(article_id=self.article.id)

        mock_notify.assert_not_called()
        self.assertEqual(len(callbacks), 3)

    @patch("articles.services.publishing.notify_article_published")
    def test_raises_for_missing_article(self, mock_notify):
        with self.assertRaises(Article.DoesNotExist):
            publish_article(article_id=999999)

        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_published")
    @patch("articles.services.publishing.advance_latest_article_publish_sequence")
    @patch("articles.services.publishing.get_next_article_publish_sequence_value")
    def test_raises_when_content_is_empty_html(
        self, mock_get_next, mock_advance, mock_notify
    ):
        self.article.content = "<p>&nbsp;</p>"
        self.article.save(update_fields=["content"])

        with self.assertRaisesMessage(
            ValueError, "Content is required before publishing."
        ):
            publish_article(article_id=self.article.id)

        self.article.refresh_from_db()

        self.assertEqual(self.article.status, ArticleStatus.PENDING_REVIEW)
        self.assertIsNone(self.article.published_at)
        self.assertIsNone(self.article.publish_sequence)

        mock_get_next.assert_not_called()
        mock_advance.assert_not_called()
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.cache_article_slug_id")
    @patch("articles.services.publishing.notify_article_published")
    def test_caches_article_slug_id(self, mock_notify, mock_cache):
        with self.captureOnCommitCallbacks(execute=True):
            published = publish_article(article_id=self.article.id)

        mock_cache.assert_called_once_with(
            article_slug=published.slug, article_id=published.id
        )

    @patch("articles.services.publishing.cache_article_slug_id")
    @patch("articles.services.publishing.notify_article_published")
    def test_does_not_cache_when_publish_fails(self, mock_notify, mock_cache):
        self.article.status = ArticleStatus.REJECTED
        self.article.save(update_fields=["status"])

        with self.assertRaisesMessage(
            ValueError, "only articles pending review can be published"
        ):
            publish_article(article_id=self.article.id)

        mock_cache.assert_not_called()


class TestGetNextArticlePublishSequenceValue(TestCase):
    def test_returns_int(self):
        value = get_next_article_publish_sequence_value()

        self.assertIsInstance(value, int)

    def test_returns_increasing_values(self):
        first = get_next_article_publish_sequence_value()
        second = get_next_article_publish_sequence_value()

        self.assertGreater(second, first)


class TestUnpublishArticle(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_changes_published_article_to_draft(self, mock_notify):
        article = Article.objects.create(
            title="Published",
            slug="published",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        with self.captureOnCommitCallbacks(execute=True):
            returned_article = unpublish_article(article_id=article.id)

        article.refresh_from_db()

        self.assertEqual(returned_article.id, article.id)
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertIsNone(article.published_at)
        self.assertIsNone(article.publish_sequence)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_raises_for_draft_article(self, mock_notify):
        article = Article.objects.create(
            title="Draft",
            slug="draft",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.DRAFT,
            published_at=None,
            publish_sequence=None,
        )

        with self.assertRaisesMessage(
            ValueError, "only published articles can be unpublished"
        ):
            unpublish_article(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertIsNone(article.published_at)
        self.assertIsNone(article.publish_sequence)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_raises_for_rejected_article(self, mock_notify):
        article = Article.objects.create(
            title="Rejected",
            slug="rejected",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.REJECTED,
            published_at=None,
            publish_sequence=None,
        )

        with self.assertRaisesMessage(
            ValueError, "only published articles can be unpublished"
        ):
            unpublish_article(article_id=article.id)

        article.refresh_from_db()

        self.assertEqual(article.status, ArticleStatus.REJECTED)
        self.assertIsNone(article.published_at)
        self.assertIsNone(article.publish_sequence)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_unpublish_notifies_when_actor_is_not_author(self, mock_notify):
        editor = User.objects.create_user(username="editor", email="editor@test.com")
        article = Article.objects.create(
            title="Published",
            slug="published",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        with self.captureOnCommitCallbacks(execute=True):
            result = unpublish_article(article_id=article.id, actor=editor)

        mock_notify.assert_called_once()
        kwargs = mock_notify.call_args.kwargs
        self.assertEqual(kwargs["recipient_id"], self.author.id)
        self.assertEqual(kwargs["article_id"], result.id)
        self.assertEqual(kwargs["actor_id"], editor.id)
        self.assertEqual(kwargs["article_slug"], result.slug)
        self.assertEqual(kwargs["article_title"], result.title)
        self.assertIsNotNone(kwargs["unpublished_at_ts"])

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_unpublish_does_not_notify_when_actor_is_none(self, mock_notify):
        article = Article.objects.create(
            title="Published",
            slug="published",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        with self.captureOnCommitCallbacks(execute=True):
            unpublish_article(article_id=article.id)

        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_unpublish_does_not_notify_when_actor_is_author(self, mock_notify):
        article = Article.objects.create(
            title="Published",
            slug="published",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        with self.captureOnCommitCallbacks(execute=True):
            unpublish_article(article_id=article.id, actor=self.author)

        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_unpublish_does_not_notify_before_commit(self, mock_notify):
        article = Article.objects.create(
            title="Published",
            slug="published",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )
        editor = User.objects.create_user(username="editor", email="editor@test.com")

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            unpublish_article(article_id=article.id, actor=editor)

        mock_notify.assert_not_called()
        self.assertEqual(len(callbacks), 2)

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_raises_for_missing_article(self, mock_notify):
        with self.assertRaises(Article.DoesNotExist):
            unpublish_article(article_id=999999)

        mock_notify.assert_not_called()

    @patch("articles.services.publishing.invalidate_article_slug_id")
    @patch("articles.services.publishing.notify_article_unpublished")
    def test_invalidates_article_slug_id(self, mock_notify, mock_invalidate):
        article = Article.objects.create(
            title="Published",
            slug="published",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        with self.captureOnCommitCallbacks(execute=True):
            unpublish_article(article_id=article.id)

        mock_invalidate.assert_called_once_with(article_slug="published")

    @patch("articles.services.publishing.invalidate_article_slug_id")
    @patch("articles.services.publishing.notify_article_unpublished")
    def test_unpublish_does_not_invalidate_when_unpublish_fails(
        self,
        mock_notify,
        mock_invalidate,
    ):
        article = Article.objects.create(
            title="Draft",
            slug="draft",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.DRAFT,
        )

        with self.assertRaisesMessage(
            ValueError, "only published articles can be unpublished"
        ):
            unpublish_article(article_id=article.id)

        mock_invalidate.assert_not_called()


class TestRejectArticle(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@test.com"
        )

    @patch("articles.services.publishing.notify_article_rejected")
    def test_reject_pending_article_marks_it_rejected(self, mock_notify):
        article = Article.objects.create(
            title="Draft",
            slug="draft",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PENDING_REVIEW,
        )

        before = timezone.now()
        with self.captureOnCommitCallbacks(execute=True):
            result = reject_article(
                article_id=article.id,
                reviewer=self.reviewer,
                reason="Please improve structure.",
            )
        after = timezone.now()

        article.refresh_from_db()

        self.assertEqual(result.id, article.id)
        self.assertEqual(article.status, ArticleStatus.REJECTED)
        self.assertIsNone(article.published_at)
        self.assertIsNone(article.publish_sequence)
        self.assertEqual(article.review_note, "Please improve structure.")
        self.assertEqual(article.reviewed_by, self.reviewer)
        self.assertIsNotNone(article.reviewed_at)
        self.assertGreaterEqual(article.reviewed_at, before)
        self.assertLessEqual(article.reviewed_at, after)

        mock_notify.assert_called_once()
        kwargs = mock_notify.call_args.kwargs
        self.assertEqual(kwargs["recipient_id"], self.author.id)
        self.assertEqual(kwargs["article_id"], result.id)
        self.assertEqual(kwargs["article_slug"], result.slug)
        self.assertEqual(kwargs["article_title"], result.title)
        self.assertEqual(kwargs["review_note"], "Please improve structure.")
        self.assertEqual(kwargs["reviewer_id"], self.reviewer.id)
        self.assertIsNotNone(kwargs["reviewed_at_ts"])

    @patch("articles.services.publishing.notify_article_rejected")
    def test_replaces_previous_review_metadata(self, mock_notify):
        old_reviewed_at = timezone.now()
        article = Article.objects.create(
            title="a",
            slug="a",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PENDING_REVIEW,
            review_note="Old note",
            reviewed_at=old_reviewed_at,
            reviewed_by=self.reviewer,
        )

        new_reviewer = User.objects.create_user(
            username="editor2", email="editor2@test.com"
        )

        before = timezone.now()
        with self.captureOnCommitCallbacks(execute=True):
            result = reject_article(
                article_id=article.id,
                reviewer=new_reviewer,
                reason="Please fix formatting and sources.",
            )
        after = timezone.now()

        article.refresh_from_db()

        self.assertEqual(result.id, article.id)
        self.assertEqual(article.status, ArticleStatus.REJECTED)
        self.assertEqual(article.review_note, "Please fix formatting and sources.")
        self.assertEqual(article.reviewed_by, new_reviewer)
        self.assertIsNotNone(article.reviewed_at)
        self.assertGreaterEqual(article.reviewed_at, before)
        self.assertLessEqual(article.reviewed_at, after)

        mock_notify.assert_called_once()
        kwargs = mock_notify.call_args.kwargs
        self.assertEqual(kwargs["recipient_id"], self.author.id)
        self.assertEqual(kwargs["article_id"], result.id)
        self.assertEqual(kwargs["article_slug"], result.slug)
        self.assertEqual(kwargs["article_title"], result.title)
        self.assertEqual(kwargs["review_note"], "Please fix formatting and sources.")
        self.assertEqual(kwargs["reviewer_id"], new_reviewer.id)
        self.assertIsNotNone(kwargs["reviewed_at_ts"])

    @patch("articles.services.publishing.notify_article_rejected")
    def test_reject_non_pending_article_raises_error(self, mock_notify):
        article = Article.objects.create(
            title="Published",
            slug="published",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.REJECTED,
        )

        with self.assertRaisesMessage(
            ValueError, "only articles pending review can be rejected"
        ):
            reject_article(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.REJECTED)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_rejected")
    def test_reject_nonexistent_article_raises_does_not_exist(self, mock_notify):
        with self.assertRaises(Article.DoesNotExist):
            reject_article(article_id=999999)

        mock_notify.assert_not_called()

    def test_raises_for_empty_reason(self):
        article = Article.objects.create(
            title="Pending",
            slug="pending",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PENDING_REVIEW,
        )

        with self.assertRaisesMessage(ValueError, "rejection reason is required"):
            reject_article(article_id=article.id, reason="   ")

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.PENDING_REVIEW)
        self.assertIsNone(article.reviewed_at)
        self.assertIsNone(article.reviewed_by)
        self.assertEqual(article.review_note, "")

    @patch("articles.services.publishing.invalidate_article_slug_id")
    @patch("articles.services.publishing.notify_article_rejected")
    def test_reject_invalidates_article_slug_id(self, mock_notify, mock_invalidate):
        article = Article.objects.create(
            title="Pending",
            slug="pending",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PENDING_REVIEW,
        )

        with self.captureOnCommitCallbacks(execute=True):
            reject_article(
                article_id=article.id,
                reviewer=self.reviewer,
                reason="Please improve structure.",
            )

        mock_invalidate.assert_called_once_with(article_slug="pending")

    @patch("articles.services.publishing.notify_article_rejected")
    def test_reject_does_not_notify_before_commit(self, mock_notify):
        article = Article.objects.create(
            title="Pending",
            slug="pending",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PENDING_REVIEW,
        )

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            reject_article(
                article_id=article.id,
                reviewer=self.reviewer,
                reason="Please improve structure.",
            )

        mock_notify.assert_not_called()
        self.assertEqual(len(callbacks), 2)

    @patch("articles.services.publishing.invalidate_article_slug_id")
    def test_does_not_invalidate_when_reject_fails(self, mock_invalidate):
        article = Article.objects.create(
            title="Pending",
            slug="pending",
            author=self.author,
            preview_text="p",
            content="c",
            content_text="c",
            status=ArticleStatus.PENDING_REVIEW,
        )

        with self.assertRaisesMessage(ValueError, "rejection reason is required"):
            reject_article(article_id=article.id, reviewer=self.reviewer)

        mock_invalidate.assert_not_called()


class TestNormalizeArticleText(SimpleTestCase):
    def test_returns_empty_string_for_none(self):
        self.assertEqual(_normalize_article_text(None), "")

    def test_returns_empty_string_for_blank_string(self):
        self.assertEqual(_normalize_article_text(""), "")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(_normalize_article_text("  Hello world  "), "Hello world")

    def test_strips_tabs_and_newlines(self):
        self.assertEqual(_normalize_article_text("\n\t Hello \t\n"), "Hello")


class TestHasMeaningfulHtmlContent(SimpleTestCase):
    def test_returns_false_for_none(self):
        self.assertFalse(_has_meaningful_html_content(None))

    def test_returns_false_for_empty_string(self):
        self.assertFalse(_has_meaningful_html_content(""))

    def test_returns_false_for_whitespace_only(self):
        self.assertFalse(_has_meaningful_html_content("   \n\t   "))

    def test_returns_false_for_empty_paragraph(self):
        self.assertFalse(_has_meaningful_html_content("<p></p>"))

    def test_returns_false_for_br_only(self):
        self.assertFalse(_has_meaningful_html_content("<p><br></p>"))

    def test_returns_false_for_nbsp_only(self):
        self.assertFalse(_has_meaningful_html_content("<p>\xa0</p>"))

    def test_returns_false_for_html_nbsp_entity_only(self):
        self.assertFalse(_has_meaningful_html_content("<p>&nbsp;</p>"))

    def test_returns_true_for_plain_text(self):
        self.assertTrue(_has_meaningful_html_content("Hello"))

    def test_returns_true_for_html_with_text(self):
        self.assertTrue(_has_meaningful_html_content("<p>Hello world</p>"))

    def test_returns_true_for_nested_html_with_text(self):
        self.assertTrue(
            _has_meaningful_html_content("<div><p><strong>Hello</strong></p></div>")
        )


class TestValidateArticleReady(SimpleTestCase):
    def make_article(
        self,
        *,
        title="Valid title",
        preview_text="Valid preview text",
        content="<p>Valid content</p>",
    ) -> Article:
        return Article(
            title=title,
            preview_text=preview_text,
            content=content,
            status=ArticleStatus.DRAFT,
        )

    def test_does_not_raise_for_valid_article(self):
        article = self.make_article()

        _validate_article_ready(article, action="publishing")

    def test_raises_when_title_is_none(self):
        article = self.make_article(title=None)

        with self.assertRaisesMessage(
            ValueError, "Title is required before publishing."
        ):
            _validate_article_ready(article, action="publishing")

    def test_raises_when_title_is_blank(self):
        article = self.make_article(title="   ")

        with self.assertRaisesMessage(
            ValueError, "Title is required before publishing."
        ):
            _validate_article_ready(article, action="publishing")

    def test_raises_when_title_is_default_draft_title(self):
        article = self.make_article(title=DEFAULT_DRAFT_ARTICLE_TITLE)

        with self.assertRaisesMessage(
            ValueError, "Title is required before publishing."
        ):
            _validate_article_ready(article, action="publishing")

    def test_raises_when_preview_text_is_none(self):
        article = self.make_article(preview_text=None)

        with self.assertRaisesMessage(
            ValueError, "Preview text is required before publishing."
        ):
            _validate_article_ready(article, action="publishing")

    def test_raises_when_preview_text_is_blank(self):
        article = self.make_article(preview_text=" \n\t ")

        with self.assertRaisesMessage(
            ValueError, "Preview text is required before publishing."
        ):
            _validate_article_ready(article, action="publishing")

    def test_raises_when_content_is_none(self):
        article = self.make_article(content=None)

        with self.assertRaisesMessage(
            ValueError, "Content is required before publishing."
        ):
            _validate_article_ready(article, action="publishing")

    def test_raises_when_content_is_empty_html(self):
        article = self.make_article(content="<p><br></p>")

        with self.assertRaisesMessage(
            ValueError, "Content is required before publishing."
        ):
            _validate_article_ready(article, action="publishing")

    def test_uses_action_name_in_error_message(self):
        article = self.make_article(title="")

        with self.assertRaisesMessage(
            ValueError, "Title is required before submitting for review."
        ):
            _validate_article_ready(article, action="submitting for review")
