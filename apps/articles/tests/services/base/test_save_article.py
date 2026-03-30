from unittest.mock import Mock, call, patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleStatus
from articles.services.articles import MAX_SLUG_RETRY_ATTEMPTS, save_article
from users.models import User


class TestSaveArticle(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@test.com",
        )
        self.category = ArticleCategory.objects.create(
            title="cat",
            slug="cat",
        )

    def test_creates_article_unpublished_by_default(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        save_m2m = Mock()

        saved = save_article(
            article=article,
            author=self.author,
            save_m2m=save_m2m,
        )

        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.author, self.author)
        self.assertEqual(saved.status, ArticleStatus.DRAFT)
        self.assertIsNone(saved.published_at)
        self.assertIsNone(saved.publish_sequence)

        db_article = Article.objects.get(id=saved.id)
        self.assertEqual(db_article.author, self.author)
        self.assertEqual(db_article.status, ArticleStatus.DRAFT)
        self.assertIsNone(db_article.published_at)
        self.assertIsNone(db_article.publish_sequence)

        save_m2m.assert_called_once_with()

    @patch("articles.services.articles.publish_article")
    def test_creates_article_assigns_author_and_publishes_when_publish_true(
        self,
        mock_publish_article,
    ):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        save_m2m = Mock()

        mock_publish_article.side_effect = lambda *, article_id: Article.objects.get(
            id=article_id
        )

        saved = save_article(
            article=article,
            author=self.author,
            save_m2m=save_m2m,
            publish=True,
        )

        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.author, self.author)
        self.assertEqual(saved.title, "a1")
        self.assertEqual(saved.slug, "a1")
        self.assertEqual(saved.category, self.category)
        self.assertEqual(saved.preview_text, "preview")
        self.assertEqual(saved.content, "content")

        db_article = Article.objects.get(id=saved.id)
        self.assertEqual(db_article.author, self.author)

        save_m2m.assert_called_once_with()
        mock_publish_article.assert_called_once_with(article_id=saved.id)

    def test_creates_article_without_publishing_when_publish_false(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        save_m2m = Mock()

        saved = save_article(
            article=article,
            author=self.author,
            save_m2m=save_m2m,
            publish=False,
        )

        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.author, self.author)
        self.assertIsNone(saved.published_at)
        self.assertIsNone(saved.publish_sequence)

        db_article = Article.objects.get(id=saved.id)
        self.assertEqual(db_article.author, self.author)
        self.assertIsNone(db_article.published_at)
        self.assertIsNone(db_article.publish_sequence)

        save_m2m.assert_called_once_with()

    def test_updates_existing_article_without_replacing_author(self):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
        )
        article.title = "updated"
        article.preview_text = "updated preview"

        save_m2m = Mock()

        saved = save_article(
            article=article,
            author=self.other_user,
            save_m2m=save_m2m,
            publish=False,
        )

        self.assertEqual(saved.pk, article.pk)
        self.assertEqual(saved.author, self.author)
        self.assertEqual(saved.title, "updated")
        self.assertEqual(saved.preview_text, "updated preview")

        article.refresh_from_db()
        self.assertEqual(article.author, self.author)
        self.assertEqual(article.title, "updated")
        self.assertEqual(article.preview_text, "updated preview")

        save_m2m.assert_called_once_with()

    def test_raises_when_creating_article_without_author(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        save_m2m = Mock()

        with self.assertRaises(ValueError):
            save_article(
                article=article,
                save_m2m=save_m2m,
                publish=False,
            )

        self.assertEqual(Article.objects.count(), 0)
        save_m2m.assert_not_called()

    @patch("articles.services.articles.publish_article")
    def test_publish_true_delegates_to_publish_service_for_existing_article(
        self,
        mock_publish_article,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.PUBLISHED,
            publish_sequence=123,
            published_at=timezone.now(),
        )
        save_m2m = Mock()

        mock_publish_article.return_value = article

        saved = save_article(
            article=article,
            save_m2m=save_m2m,
            publish=True,
        )

        self.assertEqual(saved.pk, article.pk)
        save_m2m.assert_called_once_with()
        mock_publish_article.assert_called_once_with(article_id=article.id)

    @patch("articles.services.articles.publish_article")
    def test_publishes_existing_unpublished_article_when_publish_true(
        self,
        mock_publish_article,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
        )
        save_m2m = Mock()

        mock_publish_article.side_effect = lambda *, article_id: Article.objects.get(
            id=article_id
        )

        saved = save_article(
            article=article,
            save_m2m=save_m2m,
            publish=True,
        )

        self.assertEqual(saved.pk, article.pk)
        save_m2m.assert_called_once_with()
        mock_publish_article.assert_called_once_with(article_id=article.id)

    @patch("articles.services.articles.restore_article_to_draft")
    @patch("articles.services.articles.publish_article")
    def test_updates_rejected_article_restores_to_draft_when_publish_false(
        self,
        mock_publish_article,
        mock_restore_article_to_draft,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.REJECTED,
            review_note="Needs work",
        )
        article.title = "updated"

        mock_restore_article_to_draft.side_effect = (
            lambda *, article_id: Article.objects.get(id=article_id)
        )

        save_m2m = Mock()

        saved = save_article(
            article=article,
            save_m2m=save_m2m,
            publish=False,
        )

        article.refresh_from_db()
        self.assertEqual(article.title, "updated")
        self.assertEqual(saved.pk, article.pk)
        save_m2m.assert_called_once_with()
        mock_restore_article_to_draft.assert_called_once_with(article_id=article.id)
        mock_publish_article.assert_not_called()

    @patch("articles.services.articles.restore_article_to_draft")
    @patch("articles.services.articles.publish_article")
    def test_rejected_article_with_publish_true_does_not_restore_to_draft(
        self,
        mock_publish_article,
        mock_restore_article_to_draft,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.REJECTED,
            review_note="Needs work",
        )
        save_m2m = Mock()

        mock_publish_article.side_effect = ValueError(
            "only draft articles can be published"
        )

        with self.assertRaises(ValueError):
            save_article(
                article=article,
                save_m2m=save_m2m,
                publish=True,
            )

        save_m2m.assert_called_once_with()
        mock_restore_article_to_draft.assert_not_called()
        mock_publish_article.assert_called_once_with(article_id=article.id)

    @patch("articles.services.articles.restore_article_to_draft")
    def test_existing_draft_does_not_restore_to_draft_again(
        self,
        mock_restore_article_to_draft,
    ):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.DRAFT,
        )
        article.title = "updated"

        save_m2m = Mock()

        saved = save_article(
            article=article,
            save_m2m=save_m2m,
            publish=False,
        )

        self.assertEqual(saved.pk, article.pk)
        save_m2m.assert_called_once_with()
        mock_restore_article_to_draft.assert_not_called()

    def test_saves_article_when_save_m2m_is_none(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )

        saved = save_article(
            article=article,
            author=self.author,
            save_m2m=None,
            publish=False,
        )

        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.author, self.author)
        self.assertEqual(Article.objects.count(), 1)

    def test_generates_slug_for_new_article_when_slug_blank(self):
        article = Article(
            title="Hello World",
            category=self.category,
            preview_text="preview",
            content="content",
        )

        saved = save_article(
            article=article,
            author=self.author,
            publish=False,
        )

        self.assertIsNotNone(saved.pk)
        self.assertTrue(saved.slug)
        self.assertEqual(saved.slug, "hello-world")

        db_article = Article.objects.get(id=saved.id)
        self.assertEqual(db_article.slug, "hello-world")

    def test_generates_distinct_slugs_for_two_new_articles_with_same_title(self):
        first = Article(
            title="Same Title",
            category=self.category,
            preview_text="preview 1",
            content="content 1",
        )
        second = Article(
            title="Same Title",
            category=self.category,
            preview_text="preview 2",
            content="content 2",
        )

        saved_first = save_article(
            article=first,
            author=self.author,
            publish=False,
        )
        saved_second = save_article(
            article=second,
            author=self.author,
            publish=False,
        )

        self.assertEqual(saved_first.slug, "same-title")
        self.assertTrue(saved_second.slug.startswith("same-title-"))
        self.assertNotEqual(saved_first.slug, saved_second.slug)

    @patch("articles.services.articles._build_article_slug_candidate")
    def test_does_not_generate_slug_for_new_article_when_slug_already_set(
        self,
        mock_build_slug,
    ):
        article = Article(
            title="a1",
            slug="custom-slug",
            category=self.category,
            preview_text="preview",
            content="content",
        )

        saved = save_article(
            article=article,
            author=self.author,
            publish=False,
        )

        self.assertEqual(saved.slug, "custom-slug")
        mock_build_slug.assert_not_called()

        db_article = Article.objects.get(id=saved.id)
        self.assertEqual(db_article.slug, "custom-slug")

    @patch("articles.services.articles._build_article_slug_candidate")
    def test_regenerates_slug_when_title_changed_for_draft_article(
        self,
        mock_build_slug,
    ):
        article = Article.objects.create(
            title="old title",
            slug="old-title",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.DRAFT,
        )
        article.title = "new title"
        mock_build_slug.return_value = "new-title"

        saved = save_article(
            article=article,
            publish=False,
        )

        self.assertEqual(saved.slug, "new-title")
        mock_build_slug.assert_called_once_with("new title", use_suffix=False)

        article.refresh_from_db()
        self.assertEqual(article.slug, "new-title")

    @patch("articles.services.articles._build_article_slug_candidate")
    def test_does_not_regenerate_slug_when_title_not_changed_for_draft_article(
        self,
        mock_build_slug,
    ):
        article = Article.objects.create(
            title="title",
            slug="title",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.DRAFT,
        )
        article.preview_text = "updated preview"

        saved = save_article(
            article=article,
            publish=False,
        )

        self.assertEqual(saved.slug, "title")
        mock_build_slug.assert_not_called()

        article.refresh_from_db()
        self.assertEqual(article.slug, "title")

    @patch("articles.services.articles._build_article_slug_candidate")
    def test_does_not_regenerate_slug_when_title_changed_for_published_article(
        self,
        mock_build_slug,
    ):
        article = Article.objects.create(
            title="old title",
            slug="old-title",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )
        article.title = "new published title"

        saved = save_article(
            article=article,
            publish=False,
        )

        self.assertEqual(saved.slug, "old-title")
        mock_build_slug.assert_not_called()

        article.refresh_from_db()
        self.assertEqual(article.slug, "old-title")
        self.assertEqual(article.title, "new published title")

    @patch("articles.services.articles._build_article_slug_candidate")
    def test_regenerates_slug_when_title_changed_for_rejected_article_before_restore(
        self,
        mock_build_slug,
    ):
        article = Article.objects.create(
            title="old title",
            slug="old-title",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            status=ArticleStatus.REJECTED,
            review_note="Needs work",
        )
        article.title = "new rejected title"
        mock_build_slug.return_value = "new-rejected-title"

        saved = save_article(
            article=article,
            publish=False,
        )

        self.assertEqual(saved.slug, "new-rejected-title")
        mock_build_slug.assert_called_once_with(
            "new rejected title",
            use_suffix=False,
        )

        article.refresh_from_db()
        self.assertEqual(article.slug, "new-rejected-title")
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    @patch("articles.services.articles._build_article_slug_candidate")
    def test_retries_slug_generation_on_integrity_error(self, mock_build_slug):
        article = Article(
            title="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        mock_build_slug.side_effect = ["a1", "a1-suffix"]

        original_save = Article.save
        save_call_count = 0

        def save_side_effect(instance, *args, **kwargs):
            nonlocal save_call_count
            save_call_count += 1
            if save_call_count == 1:
                raise IntegrityError("duplicate key value violates unique constraint")
            return original_save(instance, *args, **kwargs)

        with patch.object(
            Article,
            "save",
            autospec=True,
            side_effect=save_side_effect,
        ):
            saved = save_article(
                article=article,
                author=self.author,
                publish=False,
            )

        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.slug, "a1-suffix")
        self.assertEqual(
            mock_build_slug.call_args_list,
            [
                call("a1", use_suffix=False),
                call("a1", use_suffix=True),
            ],
        )

        db_article = Article.objects.get(id=saved.id)
        self.assertEqual(db_article.slug, "a1-suffix")

    @patch("articles.services.articles._build_article_slug_candidate")
    def test_raises_integrity_error_after_max_slug_attempts_exhausted(
        self,
        mock_build_slug,
    ):
        article = Article(
            title="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )
        mock_build_slug.side_effect = [
            "a1",
            "a1-s1",
            "a1-s2",
            "a1-s3",
            "a1-s4",
        ]

        with patch.object(
            Article,
            "save",
            autospec=True,
            side_effect=IntegrityError(
                "duplicate key value violates unique constraint"
            ),
        ):
            with self.assertRaises(IntegrityError):
                save_article(
                    article=article,
                    author=self.author,
                    publish=False,
                )

        self.assertEqual(mock_build_slug.call_count, MAX_SLUG_RETRY_ATTEMPTS)
        self.assertEqual(Article.objects.count(), 0)
