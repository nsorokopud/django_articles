from django.test import SimpleTestCase

from articles.services.sanitization import sanitize_article_html


class TestSanitizeArticleHtml(SimpleTestCase):
    def test_returns_empty_string_for_none(self):
        self.assertEqual(sanitize_article_html(None), "")

    def test_returns_empty_string_for_empty_input(self):
        self.assertEqual(sanitize_article_html(""), "")

    def test_keeps_allowed_tags(self):
        html = (
            "<p>Hello <strong>world</strong></p>"
            "<blockquote>Quote</blockquote>"
            "<pre><code>print('x')</code></pre>"
            "<ul><li>Item</li></ul>"
        )

        cleaned = sanitize_article_html(html)

        self.assertIn("<p>Hello <strong>world</strong></p>", cleaned)
        self.assertIn("<blockquote>Quote</blockquote>", cleaned)
        self.assertIn("<pre><code>print('x')</code></pre>", cleaned)
        self.assertIn("<ul><li>Item</li></ul>", cleaned)

    def test_removes_script_tag(self):
        html = '<p>Hello</p><script>alert("xss")</script>'
        cleaned = sanitize_article_html(html)

        self.assertIn("<p>Hello</p>", cleaned)
        self.assertNotIn("<script>", cleaned)
        self.assertNotIn("alert", cleaned)

    def test_removes_iframe_tag(self):
        html = '<p>Text</p><iframe src="https://test.com"></iframe>'
        cleaned = sanitize_article_html(html)

        self.assertIn("<p>Text</p>", cleaned)
        self.assertNotIn("<iframe", cleaned)

    def test_removes_event_handler_attributes(self):
        html = (
            '<p onclick="alert(1)">Click me</p><img src="/img.jpg" onerror="alert(1)">'
        )
        cleaned = sanitize_article_html(html)

        self.assertIn("<p>Click me</p>", cleaned)
        self.assertIn('<img src="/img.jpg">', cleaned)
        self.assertNotIn("onclick", cleaned)
        self.assertNotIn("onerror", cleaned)

    def test_keeps_safe_anchor_attributes(self):
        html = (
            '<a href="https://test.com" title="Example" target="_blank">'
            "Example"
            "</a>"
        )
        cleaned = sanitize_article_html(html)

        self.assertIn('href="https://test.com"', cleaned)
        self.assertIn('title="Example"', cleaned)
        self.assertIn('target="_blank"', cleaned)
        self.assertIn("rel=", cleaned)
        self.assertIn("noopener", cleaned)
        self.assertIn("noreferrer", cleaned)
        self.assertIn("nofollow", cleaned)

    def test_removes_javascript_href(self):
        html = '<a href="javascript:alert(1)">Bad link</a>'
        cleaned = sanitize_article_html(html)

        self.assertIn(">Bad link</a>", cleaned)
        self.assertNotIn("javascript:", cleaned)
        self.assertNotIn('href="', cleaned)

    def test_removes_mailto_href(self):
        html = '<a href="mailto:test@test.com">Email</a>'
        cleaned = sanitize_article_html(html)

        self.assertNotIn('href="mailto:test@test.com"', cleaned)

    def test_keeps_http_and_https_image_src(self):
        html = (
            '<img src="http://test.com/image.jpg" alt="a">'
            '<img src="https://test.com/image.jpg" alt="b">'
        )
        cleaned = sanitize_article_html(html)

        self.assertIn('src="http://test.com/image.jpg"', cleaned)
        self.assertIn('src="https://test.com/image.jpg"', cleaned)
        self.assertIn('alt="a"', cleaned)
        self.assertIn('alt="b"', cleaned)

    def test_removes_javascript_image_src(self):
        html = '<img src="javascript:alert(1)" alt="x">'
        cleaned = sanitize_article_html(html)

        self.assertIn("<img", cleaned)
        self.assertNotIn("javascript:", cleaned)
        self.assertNotIn('src="javascript:alert(1)"', cleaned)

    def test_keeps_allowed_image_attributes(self):
        html = (
            '<img src="/media/test.jpg" alt="preview" title="Title" '
            'width="640" height="480">'
        )
        cleaned = sanitize_article_html(html)

        self.assertIn('src="/media/test.jpg"', cleaned)
        self.assertIn('alt="preview"', cleaned)
        self.assertIn('title="Title"', cleaned)
        self.assertIn('width="640"', cleaned)
        self.assertIn('height="480"', cleaned)

    def test_removes_disallowed_attributes_but_keeps_allowed_tags(self):
        html = '<a href="https://test.com" onclick="alert(1)" data-id="123">Link</a>'
        cleaned = sanitize_article_html(html)

        self.assertIn('href="https://test.com"', cleaned)
        self.assertIn(">Link</a>", cleaned)
        self.assertNotIn("onclick", cleaned)
        self.assertNotIn("data-id", cleaned)
