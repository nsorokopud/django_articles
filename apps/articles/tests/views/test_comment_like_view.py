from django.db.models import Count
from django.test import Client, TestCase
from django.urls import reverse

from articles.models import Article, ArticleComment
from users.models import User


class TestCommentLikeView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="user", email="user@test.com")
        self.article = Article.objects.create(
            title="a1",
            slug="a1",
            author=self.user,
            preview_text="text1",
            content="content1",
        )
        self.comment = ArticleComment.objects.create(
            article=self.article, author=self.user, text="text"
        )
        self.url = reverse("comment-like", args=[self.comment.id])

    def test_get(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_post_anonymous_user(self):
        response = self.client.post(self.url)
        self.assertRedirects(
            response,
            f"/login/?next={self.url}",
            status_code=302,
            target_status_code=200,
        )

    def test_post(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"likes": 1}},
        )
        self.assertCountEqual(list(self.comment.users_that_liked.all()), [self.user])
        likes_count = (
            ArticleComment.objects.filter(id=self.comment.id)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 1)

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"likes": 0}},
        )
        self.assertCountEqual(list(self.comment.users_that_liked.all()), [])
        likes_count = (
            ArticleComment.objects.filter(id=self.comment.id)
            .annotate(likes_count=Count("users_that_liked", distinct=True))
            .first()
            .likes_count
        )
        self.assertEqual(likes_count, 0)
