from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from articles.models import Article, ArticleStatus
from articles.services.articles import _build_article_slug_candidate
from articles.services.publishing import (
    get_next_article_publish_sequence_value,
    publish_article,
    reject_article,
    restore_article_to_draft,
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

    def test_submit_article_for_review_from_rejected(self):
        article = self.create_article(status=ArticleStatus.REJECTED)
        result = submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(result.id, article.id)
        self.assertEqual(article.status, ArticleStatus.PENDING_REVIEW)

    def test_submit_article_for_review_from_pending_review_is_idempotent(self):
        article = self.create_article(status=ArticleStatus.PENDING_REVIEW)
        result = submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(result.id, article.id)
        self.assertEqual(article.status, ArticleStatus.PENDING_REVIEW)

    def test_submit_article_for_review_from_published_raises_error(self):
        article = self.create_article(status=ArticleStatus.PUBLISHED)

        with self.assertRaisesMessage(
            ValueError,
            "only draft or rejected articles can be submitted for review",
        ):
            submit_article_for_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.PUBLISHED)
        self.assertIsNotNone(article.published_at)
        self.assertIsNotNone(article.publish_sequence)


class TestWithdrawArticleFromReview(ArticleServiceBaseTestCase):

    def test_withdraw_article_from_review_from_pending_review(self):
        article = self.create_article(status=ArticleStatus.PENDING_REVIEW)
        result = withdraw_article_from_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(result.id, article.id)
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    def test_withdraw_article_from_review_from_draft_is_idempotent(self):
        article = self.create_article(status=ArticleStatus.DRAFT)
        result = withdraw_article_from_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(result.id, article.id)
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    def test_withdraw_article_from_review_from_rejected_raises_error(self):
        article = self.create_article(status=ArticleStatus.REJECTED)

        with self.assertRaisesMessage(
            ValueError,
            "only articles pending review can be withdrawn from review",
        ):
            withdraw_article_from_review(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.REJECTED)

    def test_withdraw_article_from_review_from_published_raises_error(self):
        article = self.create_article(status=ArticleStatus.PUBLISHED)

        with self.assertRaisesMessage(
            ValueError,
            "only articles pending review can be withdrawn from review",
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
            content="c",
        )

    @patch("articles.services.publishing.notify_article_published")
    def test_sets_published_fields_and_updates_author_sequence(self, mock_notify):
        before = timezone.now()

        published = publish_article(article_id=self.article.id)

        after = timezone.now()

        self.article.refresh_from_db()
        self.author.refresh_from_db()

        self.assertEqual(published.id, self.article.id)
        self.assertEqual(self.article.status, ArticleStatus.PUBLISHED)
        self.assertIsNotNone(self.article.published_at)
        self.assertIsNotNone(self.article.publish_sequence)
        self.assertGreaterEqual(self.article.published_at, before)
        self.assertLessEqual(self.article.published_at, after)
        self.assertEqual(
            self.author.latest_article_publish_sequence,
            self.article.publish_sequence,
        )

        mock_notify.assert_called_once_with(
            recipient_id=self.author.id,
            article_id=self.article.id,
            article_slug=self.article.slug,
            article_title=self.article.title,
            actor_id=None,
            publish_sequence=self.article.publish_sequence,
        )

    @patch("articles.services.publishing.notify_article_published")
    def test_clears_review_metadata_when_publishing_draft(self, mock_notify):
        reviewer = User.objects.create_user(
            username="reviewer",
            email="reviewer@test.com",
        )
        self.article.status = ArticleStatus.DRAFT
        self.article.review_note = "Old review note."
        self.article.reviewed_at = timezone.now()
        self.article.reviewed_by = reviewer
        self.article.save(
            update_fields=[
                "status",
                "review_note",
                "reviewed_at",
                "reviewed_by",
            ]
        )

        publish_article(article_id=self.article.id)

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(self.article.review_note, "")
        self.assertIsNone(self.article.reviewed_at)
        self.assertIsNone(self.article.reviewed_by)
        mock_notify.assert_called_once()

    @patch("articles.services.publishing.notify_article_published")
    def test_raises_when_article_is_rejected(self, mock_notify):
        reviewer = User.objects.create_user(
            username="reviewer",
            email="reviewer@test.com",
        )
        reviewed_at = timezone.now()

        self.article.status = ArticleStatus.REJECTED
        self.article.review_note = "Needs more sources."
        self.article.reviewed_at = reviewed_at
        self.article.reviewed_by = reviewer
        self.article.save(
            update_fields=[
                "status",
                "review_note",
                "reviewed_at",
                "reviewed_by",
            ]
        )

        with self.assertRaisesMessage(
            ValueError,
            "only draft articles can be published",
        ):
            publish_article(article_id=self.article.id)

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
    def test_returns_already_published_article_without_changing_it(
        self, mock_advance, mock_get_next, mock_notify
    ):
        published_at = timezone.now()
        self.article.status = ArticleStatus.PUBLISHED
        self.article.published_at = published_at
        self.article.publish_sequence = 123
        self.article.save(update_fields=["status", "published_at", "publish_sequence"])

        self.author.latest_article_publish_sequence = 123
        self.author.save(update_fields=["latest_article_publish_sequence"])

        result = publish_article(article_id=self.article.id)

        self.article.refresh_from_db()
        self.author.refresh_from_db()

        self.assertEqual(result.id, self.article.id)
        self.assertEqual(self.article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(self.article.publish_sequence, 123)
        self.assertEqual(self.article.published_at, published_at)
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

        publish_article(article_id=self.article.id)

        mock_advance.assert_called_once_with(
            user_id=self.author.id,
            publish_sequence=777,
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(self.article.publish_sequence, 777)
        self.assertIsNotNone(self.article.published_at)
        mock_notify.assert_called_once_with(
            recipient_id=self.author.id,
            article_id=self.article.id,
            article_slug=self.article.slug,
            article_title=self.article.title,
            actor_id=None,
            publish_sequence=777,
        )

    @patch("articles.services.publishing.notify_article_published")
    def test_publish_notifies_author_when_actor_is_none(self, mock_notify):
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
    def test_publish_notifies_author_when_actor_is_not_author(self, mock_notify):
        editor = User.objects.create_user(username="editor", email="editor@test.com")

        published = publish_article(article_id=self.article.id, actor=editor)

        mock_notify.assert_called_once_with(
            recipient_id=self.author.id,
            article_id=published.id,
            article_slug=published.slug,
            article_title=published.title,
            actor_id=editor.id,
            publish_sequence=published.publish_sequence,
        )

    @patch("articles.services.publishing.notify_article_published")
    def test_publish_does_not_notify_when_actor_is_author(self, mock_notify):
        publish_article(article_id=self.article.id, actor=self.author)

        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_published")
    def test_raises_for_missing_article(self, mock_notify):
        with self.assertRaises(Article.DoesNotExist):
            publish_article(article_id=999999)

        mock_notify.assert_not_called()


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
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        returned_article = unpublish_article(article_id=article.id)
        article.refresh_from_db()

        self.assertEqual(returned_article.id, article.id)
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertIsNone(article.published_at)
        self.assertIsNone(article.publish_sequence)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_does_nothing_for_draft_article(self, mock_notify):
        article = Article.objects.create(
            title="Draft",
            slug="draft",
            author=self.author,
            preview_text="p",
            content="c",
            status=ArticleStatus.DRAFT,
            published_at=None,
            publish_sequence=None,
        )

        returned_article = unpublish_article(article_id=article.id)
        article.refresh_from_db()

        self.assertEqual(returned_article.id, article.id)
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertIsNone(article.published_at)
        self.assertIsNone(article.publish_sequence)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_does_nothing_for_rejected_article(self, mock_notify):
        article = Article.objects.create(
            title="Rejected",
            slug="rejected",
            author=self.author,
            preview_text="p",
            content="c",
            status=ArticleStatus.REJECTED,
            published_at=None,
            publish_sequence=None,
        )

        returned_article = unpublish_article(article_id=article.id)
        article.refresh_from_db()

        self.assertEqual(returned_article.id, article.id)
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
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

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
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

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
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        unpublish_article(article_id=article.id, actor=self.author)

        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_unpublished")
    def test_raises_for_missing_article(self, mock_notify):
        with self.assertRaises(Article.DoesNotExist):
            unpublish_article(article_id=999999)

        mock_notify.assert_not_called()


class TestRejectArticle(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@test.com"
        )

    @patch("articles.services.publishing.notify_article_rejected")
    def test_reject_draft_article_marks_it_rejected(self, mock_notify):
        article = Article.objects.create(
            title="Draft",
            slug="draft",
            author=self.author,
            preview_text="p",
            content="c",
            status=ArticleStatus.DRAFT,
            published_at=None,
            publish_sequence=None,
        )

        before = timezone.now()
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
    def test_reject_rejected_article_without_new_data_is_idempotent(self, mock_notify):
        reviewed_at = timezone.now()
        article = Article.objects.create(
            title="Rejected",
            slug="rejected",
            author=self.author,
            preview_text="p",
            content="c",
            status=ArticleStatus.REJECTED,
            published_at=None,
            publish_sequence=None,
            review_note="Old note",
            reviewed_at=reviewed_at,
            reviewed_by=self.reviewer,
        )

        result = reject_article(article_id=article.id)
        article.refresh_from_db()

        self.assertEqual(result.id, article.id)
        self.assertEqual(article.status, ArticleStatus.REJECTED)
        self.assertIsNone(article.published_at)
        self.assertIsNone(article.publish_sequence)
        self.assertEqual(article.review_note, "Old note")
        self.assertEqual(article.reviewed_at, reviewed_at)
        self.assertEqual(article.reviewed_by, self.reviewer)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_rejected")
    def test_reject_rejected_article_with_new_reason_updates_review_metadata(
        self, mock_notify
    ):
        old_reviewed_at = timezone.now()
        article = Article.objects.create(
            title="Rejected",
            slug="rejected",
            author=self.author,
            preview_text="p",
            content="c",
            status=ArticleStatus.REJECTED,
            published_at=None,
            publish_sequence=None,
            review_note="Old note",
            reviewed_at=old_reviewed_at,
            reviewed_by=self.reviewer,
        )

        new_reviewer = User.objects.create_user(
            username="editor2",
            email="editor2@test.com",
        )

        before = timezone.now()
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
        self.assertEqual(
            kwargs["review_note"],
            "Please fix formatting and sources.",
        )
        self.assertEqual(kwargs["reviewer_id"], new_reviewer.id)
        self.assertIsNotNone(kwargs["reviewed_at_ts"])

    @patch("articles.services.publishing.notify_article_rejected")
    def test_reject_published_article_raises_error_and_does_not_modify_article(
        self, mock_notify
    ):
        published_at = timezone.now()

        article = Article.objects.create(
            title="Published",
            slug="published",
            author=self.author,
            preview_text="p",
            content="c",
            status=ArticleStatus.PUBLISHED,
            published_at=published_at,
            publish_sequence=123,
        )

        with self.assertRaisesMessage(
            ValueError,
            "published articles cannot be rejected",
        ):
            reject_article(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.PUBLISHED)
        self.assertEqual(article.published_at, published_at)
        self.assertEqual(article.publish_sequence, 123)
        mock_notify.assert_not_called()

    @patch("articles.services.publishing.notify_article_rejected")
    def test_reject_nonexistent_article_raises_does_not_exist(self, mock_notify):
        with self.assertRaises(Article.DoesNotExist):
            reject_article(article_id=999999)

        mock_notify.assert_not_called()


class TestRestoreArticleToDraft(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@test.com"
        )

    def create_article(self, **kwargs) -> Article:
        data = {
            "title": "Test article",
            "slug": f"test-article-{timezone.now().timestamp()}",
            "author": self.author,
            "preview_text": "p",
            "content": "c",
            "status": ArticleStatus.DRAFT,
        }
        data.update(kwargs)
        return Article.objects.create(**data)

    def test_restore_rejected_article_to_draft(self):
        reviewed_at = timezone.now()
        article = self.create_article(
            status=ArticleStatus.REJECTED,
            review_note="Please fix the structure and title.",
            reviewed_at=reviewed_at,
            reviewed_by=self.reviewer,
        )

        restored = restore_article_to_draft(article_id=article.id)
        article.refresh_from_db()

        self.assertEqual(restored.id, article.id)
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertEqual(article.reviewed_at, reviewed_at)
        self.assertEqual(article.reviewed_by, self.reviewer)
        self.assertEqual(article.review_note, "Please fix the structure and title.")

    def test_restore_draft_article_is_idempotent(self):
        article = self.create_article(
            status=ArticleStatus.DRAFT,
            review_note="Old note",
            reviewed_at=None,
            reviewed_by=None,
        )

        restored = restore_article_to_draft(article_id=article.id)
        article.refresh_from_db()

        self.assertEqual(restored.id, article.id)
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertIsNone(article.reviewed_at)
        self.assertIsNone(article.reviewed_by)
        self.assertEqual(article.review_note, "Old note")

    def test_restore_published_article_raises_error(self):
        article = self.create_article(
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=123,
        )

        with self.assertRaisesMessage(
            ValueError,
            "only rejected articles can be restored to draft",
        ):
            restore_article_to_draft(article_id=article.id)

        article.refresh_from_db()
        self.assertEqual(article.status, ArticleStatus.PUBLISHED)
        self.assertIsNotNone(article.published_at)
        self.assertEqual(article.publish_sequence, 123)

    def test_restore_nonexistent_article_raises_does_not_exist(self):
        with self.assertRaises(Article.DoesNotExist):
            restore_article_to_draft(article_id=999999)
