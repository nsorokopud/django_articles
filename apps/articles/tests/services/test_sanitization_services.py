from django.test import SimpleTestCase, override_settings

from articles.services.sanitization import sanitize_article_html


ARTICLE_ID = 2
AUTHOR_ID = 1


def clean(html, *, article_id=ARTICLE_ID, author_id=AUTHOR_ID):
    return sanitize_article_html(html, article_id=article_id, author_id=author_id)


class TestSanitizeArticleHtml(SimpleTestCase):
    def test_returns_empty_string_for_none(self):
        self.assertEqual(clean(None), "")

    def test_returns_empty_string_for_empty_input(self):
        self.assertEqual(clean(""), "")

    def test_keeps_allowed_tags(self):
        html = (
            "<p>Hello <strong>world</strong></p>"
            "<blockquote>Quote</blockquote>"
            "<pre><code>print('x')</code></pre>"
            "<ul><li>Item</li></ul>"
            "<table><thead><tr><th>Head</th></tr></thead>"
            "<tbody><tr><td>Cell</td></tr></tbody></table>"
        )

        cleaned = clean(html)

        self.assertIn("<p>Hello <strong>world</strong></p>", cleaned)
        self.assertIn("<blockquote>Quote</blockquote>", cleaned)
        self.assertIn("<pre><code>print('x')</code></pre>", cleaned)
        self.assertIn("<ul><li>Item</li></ul>", cleaned)
        self.assertIn("<table>", cleaned)
        self.assertIn("<th>Head</th>", cleaned)
        self.assertIn("<td>Cell</td>", cleaned)

    def test_removes_script_tag(self):
        cleaned = clean('<p>Hello</p><script>alert("xss")</script>')

        self.assertIn("<p>Hello</p>", cleaned)
        self.assertNotIn("<script", cleaned)
        self.assertNotIn("alert", cleaned)

    def test_removes_iframe_tag(self):
        cleaned = clean('<p>Text</p><iframe src="https://test.com"></iframe>')

        self.assertIn("<p>Text</p>", cleaned)
        self.assertNotIn("<iframe", cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_removes_event_handler_attributes(self):
        html = (
            '<p onclick="alert(1)">Click me</p>'
            '<img src="/media/articles/uploads/1/2/img.jpg" onerror="alert(1)">'
        )

        cleaned = clean(html)

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

        cleaned = clean(html)

        self.assertIn('href="https://test.com"', cleaned)
        self.assertIn('title="Example"', cleaned)
        self.assertIn('target="_blank"', cleaned)
        self.assertIn("rel=", cleaned)
        self.assertIn("noopener", cleaned)
        self.assertIn("noreferrer", cleaned)
        self.assertIn("nofollow", cleaned)

    def test_removes_javascript_href(self):
        cleaned = clean('<a href="javascript:alert(1)">Bad link</a>')

        self.assertIn(">Bad link</a>", cleaned)
        self.assertNotIn("javascript:", cleaned)
        self.assertNotIn('href="', cleaned)

    def test_removes_mailto_href(self):
        cleaned = clean('<a href="mailto:test@test.com">Email</a>')

        self.assertNotIn('href="mailto:test@test.com"', cleaned)

    def test_removes_unallowlisted_remote_image_src(self):
        html = (
            '<img src="http://test.com/image.jpg" alt="a">'
            '<img src="https://test.com/image.jpg" alt="b">'
            '<img src="//test.com/image.jpg" alt="c">'
            '<img src="data:image/png;base64,abc" alt="d">'
            '<img src="blob:https://test.com/abc" alt="e">'
        )

        cleaned = clean(html)

        self.assertNotIn("http://test.com/image.jpg", cleaned)
        self.assertNotIn("https://test.com/image.jpg", cleaned)
        self.assertNotIn("//test.com/image.jpg", cleaned)
        self.assertNotIn("data:image", cleaned)
        self.assertNotIn("blob:", cleaned)

    def test_removes_javascript_image_src(self):
        cleaned = clean('<img src="javascript:alert(1)" alt="x">')

        self.assertIn("<img", cleaned)
        self.assertNotIn("javascript:", cleaned)
        self.assertNotIn('src="javascript:alert(1)"', cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_keeps_allowed_local_article_image_src(self):
        html = (
            '<img src="/media/articles/uploads/1/2/test.jpg" '
            'alt="preview" title="Title" width="640" height="480">'
        )

        cleaned = clean(html)

        self.assertIn('src="/media/articles/uploads/1/2/test.jpg"', cleaned)
        self.assertIn('alt="preview"', cleaned)
        self.assertIn('title="Title"', cleaned)
        self.assertNotIn("width=", cleaned)
        self.assertNotIn("height=", cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_removes_local_image_for_different_article(self):
        cleaned = clean('<img src="/media/articles/uploads/1/3/test.jpg" alt="x">')

        self.assertNotIn("src=", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_removes_local_image_for_different_author(self):
        cleaned = clean('<img src="/media/articles/uploads/9/2/test.jpg" alt="x">')

        self.assertNotIn("src=", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_removes_owned_image_when_article_context_missing(self):
        cleaned = clean(
            '<img src="/media/articles/uploads/1/2/test.jpg" alt="x">',
            article_id=None,
            author_id=AUTHOR_ID,
        )

        self.assertNotIn("src=", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(MEDIA_URL="/media/")
    def test_removes_owned_image_when_author_context_missing(self):
        cleaned = clean(
            '<img src="/media/articles/uploads/1/2/test.jpg" alt="x">',
            article_id=ARTICLE_ID,
            author_id=None,
        )

        self.assertNotIn("src=", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/"])
    def test_keeps_allowed_absolute_article_image_src(self):
        url = "https://bucket.s3.amazonaws.com/articles/uploads/1/2/test.jpg"

        cleaned = clean(f'<img src="{url}" alt="x">')

        self.assertIn(f'src="{url}"', cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(
        MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/media/"]
    )
    def test_keeps_allowed_absolute_article_image_src_with_base_path(self):
        url = "https://bucket.s3.amazonaws.com/media/articles/uploads/1/2/test.jpg"

        cleaned = clean(f'<img src="{url}" alt="x">')

        self.assertIn(f'src="{url}"', cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/"])
    def test_removes_absolute_image_for_different_article(self):
        url = "https://bucket.s3.amazonaws.com/articles/uploads/1/3/test.jpg"

        cleaned = clean(f'<img src="{url}" alt="x">')

        self.assertNotIn("src=", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/"])
    def test_removes_absolute_image_for_different_author(self):
        url = "https://bucket.s3.amazonaws.com/articles/uploads/9/2/test.jpg"

        cleaned = clean(f'<img src="{url}" alt="x">')

        self.assertNotIn("src=", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/"])
    def test_removes_http_absolute_media_image_src(self):
        html = (
            '<img src="http://bucket.s3.amazonaws.com/articles/uploads/1/2/test.jpg" '
            'alt="x">'
        )

        cleaned = clean(html)

        self.assertNotIn("http://bucket.s3.amazonaws.com", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/"])
    def test_removes_absolute_media_image_src_from_unallowed_host(self):
        html = (
            '<img src="https://evil.example.com/articles/uploads/1/2/test.jpg" '
            'alt="x">'
        )

        cleaned = clean(html)

        self.assertNotIn("https://evil.example.com", cleaned)
        self.assertIn('alt="x"', cleaned)

    @override_settings(MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/"])
    def test_removes_absolute_media_image_src_outside_uploads(self):
        url = "https://bucket.s3.amazonaws.com/other/test.jpg"

        cleaned = clean(f'<img src="{url}" alt="x">')

        self.assertNotIn(url, cleaned)
        self.assertIn('alt="x"', cleaned)

    def test_keeps_text_alignment_style(self):
        cleaned = clean('<p style="text-align: center; color: red;">Hello</p>')

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

        cleaned = clean(html)

        self.assertIn('<h2 style="text-align: right;">Heading</h2>', cleaned)
        self.assertIn(
            '<blockquote style="text-align: justify;">Quote</blockquote>', cleaned
        )
        self.assertIn('<li style="text-align: center;">Item</li>', cleaned)
        self.assertIn('<td style="text-align: left;">Cell</td>', cleaned)

    def test_removes_invalid_alignment_style_value(self):
        cleaned = clean('<p style="text-align: evil;">Hello</p>')

        self.assertNotIn("style=", cleaned)

    def test_removes_non_alignment_style(self):
        cleaned = clean('<p style="color: red; background-image: url(x);">Hello</p>')

        self.assertNotIn("style=", cleaned)
        self.assertNotIn("color", cleaned)
        self.assertNotIn("background-image", cleaned)

    def test_removes_disallowed_attributes_but_keeps_allowed_tags(self):
        html = '<a href="https://test.com" onclick="alert(1)" data-id="123">Link</a>'

        cleaned = clean(html)

        self.assertIn('href="https://test.com"', cleaned)
        self.assertIn(">Link</a>", cleaned)
        self.assertNotIn("onclick", cleaned)
        self.assertNotIn("data-id", cleaned)
