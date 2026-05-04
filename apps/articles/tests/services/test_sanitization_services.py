from django.test import SimpleTestCase, override_settings

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
            "<table><thead><tr><th>Head</th></tr></thead>"
            "<tbody><tr><td>Cell</td></tr></tbody></table>"
        )

        cleaned = sanitize_article_html(html)

        self.assertIn("<p>Hello <strong>world</strong></p>", cleaned)
        self.assertIn("<blockquote>Quote</blockquote>", cleaned)
        self.assertIn("<pre><code>print('x')</code></pre>", cleaned)
        self.assertIn("<ul><li>Item</li></ul>", cleaned)
        self.assertIn("<table>", cleaned)
        self.assertIn("<th>Head</th>", cleaned)
        self.assertIn("<td>Cell</td>", cleaned)

    def test_removes_script_tag(self):
        html = '<p>Hello</p><script>alert("xss")</script>'

        cleaned = sanitize_article_html(html)

        self.assertIn("<p>Hello</p>", cleaned)
        self.assertNotIn("<script", cleaned)
        self.assertNotIn("alert", cleaned)

    def test_removes_iframe_tag(self):
        html = '<p>Text</p><iframe src="https://test.com"></iframe>'

        cleaned = sanitize_article_html(html)

        self.assertIn("<p>Text</p>", cleaned)
        self.assertNotIn("<iframe", cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_removes_event_handler_attributes(self):
        html = (
            '<p onclick="alert(1)">Click me</p>'
            '<img src="/media/articles/uploads/1/2/img.jpg" onerror="alert(1)">'
        )

        cleaned = sanitize_article_html(html)

        self.assertIn("<p>Click me</p>", cleaned)
        self.assertIn('src="/media/articles/uploads/1/2/img.jpg"', cleaned)
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

    def test_removes_unallowlisted_remote_image_src(self):
        html = (
            '<img src="http://test.com/image.jpg" alt="a">'
            '<img src="https://test.com/image.jpg" alt="b">'
            '<img src="//test.com/image.jpg" alt="c">'
            '<img src="data:image/png;base64,abc" alt="d">'
            '<img src="blob:https://test.com/abc" alt="e">'
        )

        cleaned = sanitize_article_html(html)

        self.assertNotIn("http://test.com/image.jpg", cleaned)
        self.assertNotIn("https://test.com/image.jpg", cleaned)
        self.assertNotIn("//test.com/image.jpg", cleaned)
        self.assertNotIn("data:image", cleaned)
        self.assertNotIn("blob:", cleaned)

    def test_removes_javascript_image_src(self):
        html = '<img src="javascript:alert(1)" alt="x">'

        cleaned = sanitize_article_html(html)

        self.assertIn("<img", cleaned)
        self.assertNotIn("javascript:", cleaned)
        self.assertNotIn('src="javascript:alert(1)"', cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_keeps_allowed_local_upload_image_attributes(self):
        html = (
            '<img src="/media/articles/uploads/1/2/test.jpg" '
            'alt="preview" title="Title" width="640" height="480">'
        )

        cleaned = sanitize_article_html(html)

        self.assertIn('src="/media/articles/uploads/1/2/test.jpg"', cleaned)
        self.assertIn('alt="preview"', cleaned)
        self.assertIn('title="Title"', cleaned)
        self.assertNotIn("width=", cleaned)
        self.assertNotIn("height=", cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_removes_non_upload_local_image_src(self):
        html = '<img src="/media/test.jpg" alt="preview">'

        cleaned = sanitize_article_html(html)

        self.assertNotIn('src="/media/test.jpg"', cleaned)
        self.assertIn('alt="preview"', cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_removes_path_traversal_image_src(self):
        html = '<img src="/media/articles/uploads/1/2/../../evil.jpg" alt="x">'

        cleaned = sanitize_article_html(html)

        self.assertNotIn("src=", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(
        MEDIA_ALLOWED_BASE_URLS=["https://bucket.s3.amazonaws.com/"],
    )
    def test_keeps_allowed_absolute_s3_upload_image_src(self):
        html = (
            '<img src="https://bucket.s3.amazonaws.com/articles/uploads/1/2/test.jpg" '
            'alt="x">'
        )

        cleaned = sanitize_article_html(html)

        self.assertIn(
            'src="https://bucket.s3.amazonaws.com/articles/uploads/1/2/test.jpg"',
            cleaned,
        )
        self.assertIn('alt="x"', cleaned)

    @override_settings(
        MEDIA_ALLOWED_BASE_URLS=["https://bucket.s3.amazonaws.com/media/"],
    )
    def test_keeps_allowed_absolute_s3_upload_image_src_with_base_path(self):
        url = "https://bucket.s3.amazonaws.com/media/articles/uploads/1/2/test.jpg"
        html = f'<img src="{url}" alt="x">'

        cleaned = sanitize_article_html(html)

        self.assertIn(f'src="{url}"', cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(
        MEDIA_ALLOWED_BASE_URLS=["https://bucket.s3.amazonaws.com/"],
    )
    def test_removes_http_absolute_media_image_src(self):
        html = (
            '<img src="http://bucket.s3.amazonaws.com/articles/uploads/1/2/test.jpg" '
            'alt="x">'
        )

        cleaned = sanitize_article_html(html)

        self.assertNotIn("http://bucket.s3.amazonaws.com", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(
        MEDIA_ALLOWED_BASE_URLS=["https://bucket.s3.amazonaws.com/"],
    )
    def test_removes_absolute_media_image_src_from_unallowed_host(self):
        html = (
            '<img src="https://evil.example.com/articles/uploads/1/2/test.jpg" '
            'alt="x">'
        )

        cleaned = sanitize_article_html(html)

        self.assertNotIn("https://evil.example.com", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(
        MEDIA_ALLOWED_BASE_URLS=["https://bucket.s3.amazonaws.com/"],
    )
    def test_removes_absolute_media_image_src_outside_uploads(self):
        html = '<img src="https://bucket.s3.amazonaws.com/other/test.jpg" alt="x">'

        cleaned = sanitize_article_html(html)

        self.assertNotIn("https://bucket.s3.amazonaws.com/other/test.jpg", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(
        MEDIA_ALLOWED_BASE_URLS=["https://bucket.s3.amazonaws.com/"],
    )
    def test_removes_absolute_media_image_src_with_path_traversal(self):
        html = (
            '<img src="https://bucket.s3.amazonaws.com/articles/uploads/1/../evil.jpg" '
            'alt="x">'
        )

        cleaned = sanitize_article_html(html)

        self.assertNotIn("src=", cleaned)
        self.assertIn('alt="x"', cleaned)

    def test_keeps_text_alignment_style(self):
        html = '<p style="text-align: center; color: red;">Hello</p>'

        cleaned = sanitize_article_html(html)

        self.assertIn('style="text-align: center;"', cleaned)
        self.assertNotIn("color", cleaned)

    def test_keeps_alignment_on_allowed_tags(self):
        html = (
            '<h2 style="text-align: right;">Heading</h2>'
            '<blockquote style="text-align: justify;">Quote</blockquote>'
            '<li style="text-align: center;">Item</li>'
            '<table><tbody><tr><td style="text-align: left;">Cell'
            "</td></tr></tbody></table>"
        )

        cleaned = sanitize_article_html(html)

        self.assertIn('<h2 style="text-align: right;">Heading</h2>', cleaned)
        self.assertIn(
            '<blockquote style="text-align: justify;">Quote</blockquote>',
            cleaned,
        )
        self.assertIn('<li style="text-align: center;">Item</li>', cleaned)
        self.assertIn('<td style="text-align: left;">Cell</td>', cleaned)

    def test_removes_invalid_alignment_style_value(self):
        html = '<p style="text-align: evil;">Hello</p>'

        cleaned = sanitize_article_html(html)

        self.assertNotIn("style=", cleaned)

    def test_removes_non_alignment_style(self):
        html = '<p style="color: red; background-image: url(x);">Hello</p>'

        cleaned = sanitize_article_html(html)

        self.assertNotIn("style=", cleaned)
        self.assertNotIn("color", cleaned)
        self.assertNotIn("background-image", cleaned)

    def test_removes_disallowed_attributes_but_keeps_allowed_tags(self):
        html = '<a href="https://test.com" onclick="alert(1)" data-id="123">Link</a>'

        cleaned = sanitize_article_html(html)

        self.assertIn('href="https://test.com"', cleaned)
        self.assertIn(">Link</a>", cleaned)
        self.assertNotIn("onclick", cleaned)
        self.assertNotIn("data-id", cleaned)
