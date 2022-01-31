from django.test import TestCase, Client
from django.urls import reverse


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_homepage_view(self):
        response = self.client.get(reverse("home"))

        self.assertEquals(response.status_code, 200)
        self.assertTemplateUsed("articles/home_page.html")
