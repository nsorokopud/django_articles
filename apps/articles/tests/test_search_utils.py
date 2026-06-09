from django.test import SimpleTestCase

from articles.search_utils import extract_searchable_text


class TestExtractSearchableText(SimpleTestCase):
    def test_none_input_returns_empty_string(self):
        self.assertEqual(extract_searchable_text(None), "")

    def test_empty_string_returns_empty_string(self):
        self.assertEqual(extract_searchable_text(""), "")

    def test_strips_html_tags(self):
        html = "<p>Hello <strong>world</strong></p>"
        self.assertEqual(extract_searchable_text(html), "Hello world")

    def test_unescapes_html_entities(self):
        html = "<p>Tom &amp; Jerry &lt;3</p>"
        self.assertEqual(extract_searchable_text(html), "Tom & Jerry <3")

    def test_replaces_non_breaking_spaces(self):
        html = "<p>Hello&nbsp;&nbsp;world</p>"
        self.assertEqual(extract_searchable_text(html), "Hello world")

    def test_collapses_whitespace(self):
        html = "<p>Hello     world</p>"
        self.assertEqual(extract_searchable_text(html), "Hello world")

    def test_handles_newlines_and_tabs(self):
        html = "<p>Hello\n\n\tworld</p>"
        self.assertEqual(extract_searchable_text(html), "Hello world")

    def test_removes_nested_tags_and_attributes(self):
        html = '<div><p style="color:red">Hello <span>world</span></p></div>'
        self.assertEqual(extract_searchable_text(html), "Hello world")

    def test_mixed_realistic_content(self):
        html = """
            <p>Hello&nbsp;<strong>world</strong> &amp; everyone</p>
            <p>\n This is   a test&nbsp;&nbsp;</p>
        """
        self.assertEqual(
            extract_searchable_text(html),
            "Hello world & everyone This is a test",
        )
