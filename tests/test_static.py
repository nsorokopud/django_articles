from django.test import TestCase
from django.contrib.staticfiles import finders


class TestStatic(TestCase):
    def test_css_is_loading(self):
        css_path = finders.find('css/style.css')
        self.assertIsNotNone(css_path)
