from django.contrib.auth import get_user_model
from django.test import TestCase

from articles.models import Article, ArticleComment


User = get_user_model()


class TestArticleCommentPostSaveSignal(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.commenter = User.objects.create_user(
            username="commenter", email="commenter@test.com"
        )
        self.article = Article.objects.create(
            title="Article", slug="article", author=self.author, comments_count=0
        )

    def test_increments_comments_count(self):
        ArticleComment.objects.create(
            article=self.article, author=self.commenter, text="First comment"
        )

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 1)

    def test_only_increments_on_create(self):
        comment = ArticleComment.objects.create(
            article=self.article, author=self.commenter, text="First comment"
        )
        comment.text = "Updated comment"
        comment.save()

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 1)


class TestArticleCommentPostDeleteSignal(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", email="author@test.com"
        )
        self.commenter = User.objects.create_user(
            username="commenter", email="commenter@test.com"
        )
        self.article = Article.objects.create(
            title="Article", slug="article", author=self.author
        )
        self.comment = ArticleComment.objects.create(
            article=self.article, author=self.commenter, text="Comment"
        )

    def test_decrements_article_comments_count(self):
        self.comment.delete()

        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 0)
