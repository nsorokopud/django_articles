from django.contrib.auth.models import User
from django.db.models import signals
from django.test import TransactionTestCase

from articles.models import Article, ArticleComment
from articles.signals import send_article_notification, send_comment_notification


class TestTasks(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        signals.post_save.disconnect(send_article_notification, sender=Article)
        signals.post_save.disconnect(send_comment_notification, sender=ArticleComment)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        signals.post_save.connect(send_article_notification, sender=Article)
        signals.post_save.connect(send_comment_notification, sender=ArticleComment)

    def setUp(self):
        self.user = User.objects.create_user(username="user")
        self.author = User.objects.create_user(username="author")
        self.author.profile.subscribers.add(self.user)
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.author,
            preview_text="text1",
            content="content1",
        )
        self.comment = ArticleComment.objects.create(
            article=self.article, author=self.author, text="1"
        )
