import json

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from articles.models import Article, ArticleComment, ArticleStatus
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
            status=ArticleStatus.PUBLISHED,
            published_at=timezone.now(),
            publish_sequence=1,
        )
        self.comment = ArticleComment.objects.create(
            article=self.article, author=self.user, text="text"
        )
        self.url = reverse("comment-like", args=[self.comment.id])

    def post_like(self, liked: bool):
        return self.client.post(
            self.url, data=json.dumps({"liked": liked}), content_type="application/json"
        )

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_post_anonymous_user(self):
        response = self.client.post(
            self.url, data=json.dumps({"liked": True}), content_type="application/json"
        )

        self.assertRedirects(
            response,
            f"/login/?next={self.url}",
            status_code=302,
            target_status_code=200,
        )

    def test_like_comment(self):
        self.client.force_login(self.user)

        response = self.post_like(True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"likes": 1, "liked": True}},
        )

        self.comment.refresh_from_db()
        self.assertEqual(self.comment.likes_count, 1)
        self.assertCountEqual(list(self.comment.users_that_liked.all()), [self.user])

    def test_like_comment_is_idempotent(self):
        self.client.force_login(self.user)

        self.post_like(True)
        response = self.post_like(True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"likes": 1, "liked": True}},
        )

        self.comment.refresh_from_db()
        self.assertEqual(self.comment.likes_count, 1)
        self.assertEqual(self.comment.users_that_liked.count(), 1)

    def test_unlike_comment(self):
        self.client.force_login(self.user)

        self.post_like(True)
        response = self.post_like(False)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "data": {"likes": 0, "liked": False}},
        )

        self.comment.refresh_from_db()
        self.assertEqual(self.comment.likes_count, 0)
        self.assertEqual(self.comment.users_that_liked.count(), 0)

    def test_invalid_payload_returns_400(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            data=json.dumps({"liked": "yes"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"status": "fail", "message": "'liked' must be true or false."},
        )
