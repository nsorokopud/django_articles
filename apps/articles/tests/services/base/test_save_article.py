from unittest.mock import Mock, call, patch

from django.db import IntegrityError
from django.test import TransactionTestCase
from django.utils import timezone

from articles.models import Article, ArticleCategory, ArticleMedia, ArticleStatus
from articles.services.articles import MAX_SLUG_RETRY_ATTEMPTS, save_article
from users.models import User


class TestSaveArticle(TransactionTestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com"
        )
        self.category = ArticleCategory.objects.create(title="cat", slug="cat")

    def test_creates_article_unpublished_by_default(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
            content_text="content",
        )

        saved = save_article(article=article, author=self.author)

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

    def test_updates_existing_article_without_replacing_author(self):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            content_text="content",
        )
        article.title = "updated"
        article.preview_text = "updated preview"

        saved = save_article(article=article, author=self.other_user)

        self.assertEqual(saved.pk, article.pk)
        self.assertEqual(saved.author, self.author)
        self.assertEqual(saved.title, "updated")
        self.assertEqual(saved.preview_text, "updated preview")

        article.refresh_from_db()
        self.assertEqual(article.author, self.author)
        self.assertEqual(article.title, "updated")
        self.assertEqual(article.preview_text, "updated preview")

    def test_raises_when_creating_article_without_author(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
            content_text="content",
        )
        save_related = Mock()

        with self.assertRaises(ValueError):
            save_article(article=article)

        self.assertEqual(Article.objects.count(), 0)
        save_related.assert_not_called()

    def test_updates_rejected_article_restores_to_draft(self):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.REJECTED,
            review_note="Needs work",
        )
        article.title = "updated"

        saved = save_article(article=article)
        article.refresh_from_db()
        self.assertEqual(article.title, "updated")
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertEqual(saved.pk, article.pk)

    def test_editing_rejected_article_non_title_field_restores_to_draft(self):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.REJECTED,
            review_note="Needs work",
        )
        article.preview_text = "updated preview"

        saved = save_article(article=article)
        article.refresh_from_db()
        self.assertEqual(saved.pk, article.pk)
        self.assertEqual(article.preview_text, "updated preview")
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    def test_saves_article_when_save_related_is_none(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
            content_text="content",
        )

        saved = save_article(article=article, author=self.author)
        self.assertIsNotNone(saved.pk)
        self.assertEqual(saved.author, self.author)
        self.assertEqual(Article.objects.count(), 1)

    @patch("articles.services.articles.sanitize_article_html")
    def test_calls_sanitizer_before_save(self, mock_sanitize):
        mock_sanitize.return_value = "<p>clean</p>"

        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="<p>x</p><script>alert(1)</script>",
        )

        saved = save_article(article=article, author=self.author)

        mock_sanitize.assert_called_once_with("<p>x</p><script>alert(1)</script>")
        self.assertEqual(saved.content, "<p>clean</p>")

    def test_sanitizes_content_when_creating_article(self):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content='<p>Hello</p><script>alert("xss")</script>',
        )

        saved = save_article(article=article, author=self.author)

        self.assertIn("<p>Hello</p>", saved.content)
        self.assertNotIn("<script", saved.content)

        saved.refresh_from_db()
        self.assertIn("<p>Hello</p>", saved.content)
        self.assertNotIn("<script", saved.content)

    def test_clears_review_metadata_when_restoring_to_draft(self):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.author,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.REJECTED,
            review_note="note",
            reviewed_at=timezone.now(),
            reviewed_by=self.other_user,
        )
        article.title = "updated"

        saved = save_article(article=article)
        article.refresh_from_db()
        self.assertEqual(saved.pk, article.pk)
        self.assertEqual(article.title, "updated")
        self.assertEqual(article.status, ArticleStatus.DRAFT)
        self.assertEqual(article.review_note, "")
        self.assertIsNone(article.reviewed_at)
        self.assertIsNone(article.reviewed_by)

    @patch("articles.services.articles.sync_article_inline_media_references")
    def test_syncs_inline_media_references(self, mock_sync):
        article = Article(
            title="a1",
            slug="a1",
            category=self.category,
            preview_text="preview",
            content="content",
        )

        saved = save_article(article=article, author=self.author)

        mock_sync.assert_called_once_with(article=saved)

    def test_marks_media_as_referenced(self):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.author,
            preview_text="preview",
            content="",
            content_text="",
        )

        media = ArticleMedia.objects.create(
            article=article,
            file=f"articles/uploads/{self.author.id}/{article.id}/image.png",
            unreferenced_at=timezone.now(),
        )

        article.content = (
            f'<img src="/media/articles/uploads/'
            f'{self.author.id}/{article.id}/image.png">'
        )

        save_article(article=article)

        media.refresh_from_db()
        self.assertIsNone(media.unreferenced_at)

    def test_marks_media_unreferenced_when_removed(self):
        article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.author,
            preview_text="preview",
            content="",
            content_text="",
        )

        media = ArticleMedia.objects.create(
            article=article,
            file=f"articles/uploads/{self.author.id}/{article.id}/image.png",
            unreferenced_at=None,
        )

        article.content = "<p>No image</p>"

        save_article(article=article)

        media.refresh_from_db()
        self.assertIsNotNone(media.unreferenced_at)

    def test_generates_slug_for_new_article_when_slug_blank(self):
        article = Article(
            title="Hello World",
            category=self.category,
            preview_text="preview",
            content="content",
            content_text="content",
        )

        saved = save_article(
            article=article,
            author=self.author,
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
        )
        saved_second = save_article(
            article=second,
            author=self.author,
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
            content_text="content",
        )

        saved = save_article(
            article=article,
            author=self.author,
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
            content_text="content",
            status=ArticleStatus.DRAFT,
        )
        article.title = "new title"
        mock_build_slug.return_value = "new-title"

        saved = save_article(article=article)

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
            content_text="content",
            status=ArticleStatus.DRAFT,
        )
        article.preview_text = "updated preview"

        saved = save_article(article=article)

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
            content_text="content",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )
        article.title = "new published title"

        saved = save_article(article=article)

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
            content_text="content",
            status=ArticleStatus.REJECTED,
            review_note="Needs work",
        )
        article.title = "new rejected title"
        mock_build_slug.return_value = "new-rejected-title"

        saved = save_article(article=article)

        self.assertEqual(saved.slug, "new-rejected-title")
        mock_build_slug.assert_called_once_with(
            "new rejected title",
            use_suffix=False,
        )

        article.refresh_from_db()
        self.assertEqual(article.slug, "new-rejected-title")
        self.assertEqual(article.status, ArticleStatus.DRAFT)

    @patch("articles.services.articles._build_article_slug_candidate")
    def test_does_not_regenerate_slug_when_title_changed_for_pending_review_article(
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
            content_text="content",
            status=ArticleStatus.PENDING_REVIEW,
        )
        article.title = "new pending title"

        saved = save_article(article=article)

        self.assertEqual(saved.slug, "old-title")
        mock_build_slug.assert_not_called()

        article.refresh_from_db()
        self.assertEqual(article.slug, "old-title")
        self.assertEqual(article.title, "new pending title")

    @patch("articles.services.articles._build_article_slug_candidate")
    def test_retries_slug_generation_on_integrity_error(self, mock_build_slug):
        article = Article(
            title="a1",
            category=self.category,
            preview_text="preview",
            content="content",
            content_text="content",
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
            saved = save_article(article=article, author=self.author)

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
            content_text="content",
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
                save_article(article=article, author=self.author)

        self.assertEqual(mock_build_slug.call_count, MAX_SLUG_RETRY_ATTEMPTS)
        self.assertEqual(Article.objects.count(), 0)

    @patch("articles.services.articles.invalidate_article_slug_id")
    def test_invalidates_old_slug_when_slug_changes(self, mock_invalidate):
        article = Article.objects.create(
            title="old title",
            slug="old-title",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.DRAFT,
        )
        article.title = "new title"

        save_article(article=article)
        mock_invalidate.assert_called_once_with(article_slug="old-title")

    @patch("articles.services.articles.cache_article_slug_id")
    def test_caches_slug_id_when_saving_published_article(self, mock_cache):
        article = Article.objects.create(
            title="published",
            slug="published",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )
        article.preview_text = "updated preview"

        save_article(article=article)
        mock_cache.assert_called_once_with(
            article_slug="published", article_id=article.id
        )

    @patch("articles.services.articles.cache_article_slug_id")
    def test_does_not_cache_slug_id_when_saving_draft_article(self, mock_cache):
        article = Article.objects.create(
            title="draft",
            slug="draft",
            category=self.category,
            author=self.author,
            preview_text="preview",
            content="content",
            content_text="content",
            status=ArticleStatus.DRAFT,
        )
        article.preview_text = "updated preview"

        save_article(article=article)
        mock_cache.assert_not_called()
