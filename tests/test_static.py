from django.contrib.staticfiles import finders
from django.test import SimpleTestCase


class TestStatic(SimpleTestCase):
    def test_css_is_loading(self):
        css_path = finders.find("css/style.css")
        self.assertIsNotNone(css_path)

    def test_js_is_loading(self):
        js_path = finders.find("js/likes.js")
        self.assertIsNotNone(js_path)
