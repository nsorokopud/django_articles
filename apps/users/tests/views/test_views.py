from django.test import Client, TestCase
from django.urls import reverse


class TestPostRegistrationView(TestCase):
    def setUp(self):
        self.client = Client()

        self.url = reverse("post-registration")

    def test_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/post_registration.html")

    def test_post(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)
