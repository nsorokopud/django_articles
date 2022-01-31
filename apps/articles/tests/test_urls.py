from django.test import TestCase
from django.urls import reverse, resolve

from articles.views import HomePageView


class TestViews(TestCase):
    def test_homepage_url_is_resolved(self):
        url = reverse("home")
        self.assertEquals(resolve(url).func.view_class, HomePageView)
