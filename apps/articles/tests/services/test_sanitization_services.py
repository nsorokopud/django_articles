from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from articles.constants import ALLOWED_ARTICLE_INTERNAL_LINK_PREFIXES
from articles.services.sanitization import (
    _get_validated_internal_article_link_hosts,
    _get_validated_internal_article_link_prefixes,
    _is_valid_internal_link_prefix,
    sanitize_article_html,
)


ARTICLE_ID = 2
AUTHOR_ID = 1


def clean(html, *, article_id=ARTICLE_ID, author_id=AUTHOR_ID):
    return sanitize_article_html(html, article_id=article_id, author_id=author_id)


@override_settings(
    ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=(),
)
class TestSanitizeArticleHtml(SimpleTestCase):
    def setUp(self):
        super().setUp()
        _get_validated_internal_article_link_hosts.cache_clear()
        _get_validated_internal_article_link_prefixes.cache_clear()

    def tearDown(self):
        _get_validated_internal_article_link_hosts.cache_clear()
        _get_validated_internal_article_link_prefixes.cache_clear()
        super().tearDown()

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

    def test_keeps_https_anchor_attributes(self):
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

    def test_keeps_allowed_anchor_target_self(self):
        cleaned = clean('<a href="https://test.com" target="_self">Link</a>')

        self.assertIn('target="_self"', cleaned)
        self.assertIn(">Link</a>", cleaned)

    def test_removes_invalid_anchor_target(self):
        cleaned = clean('<a href="https://test.com" target="popup">Link</a>')

        self.assertIn('href="https://test.com"', cleaned)
        self.assertIn(">Link</a>", cleaned)
        self.assertNotIn("target=", cleaned)

    def test_removes_http_anchor_href_by_default(self):
        cleaned = clean('<a href="http://test.com">HTTP link</a>')

        self.assertIn(">HTTP link</a>", cleaned)
        self.assertNotIn('href="http://test.com"', cleaned)

    @override_settings(ARTICLES_ALLOWED_ARTICLE_CONTENT_URL_SCHEMES={"http"})
    def test_keeps_http_anchor_href_when_allowed_by_setting(self):
        cleaned = clean('<a href="http://test.com">HTTP link</a>')

        self.assertIn('href="http://test.com"', cleaned)
        self.assertIn(">HTTP link</a>", cleaned)

    def test_keeps_allowlisted_internal_article_anchor_href(self):
        cleaned = clean('<a href="/articles/abc/">Internal link</a>')

        self.assertIn('href="/articles/abc/"', cleaned)
        self.assertIn(">Internal link</a>", cleaned)

    def test_keeps_allowlisted_internal_author_anchor_href(self):
        cleaned = clean('<a href="/author/123/">Author link</a>')

        self.assertIn('href="/author/123/"', cleaned)
        self.assertIn(">Author link</a>", cleaned)

    def test_configured_internal_link_prefixes_are_valid(self):
        for prefix in ALLOWED_ARTICLE_INTERNAL_LINK_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertTrue(_is_valid_internal_link_prefix(prefix))

    def test_rejects_invalid_internal_link_prefixes(self):
        invalid_prefixes = (
            "/",
            "articles/",
            "/articles",
            "/articles/../admin/",
            "/articles/%2e%2e/admin/",
            "/articles/\x00",
            123,
        )

        for prefix in invalid_prefixes:
            with self.subTest(prefix=prefix):
                self.assertFalse(_is_valid_internal_link_prefix(prefix))

    def test_keeps_allowlisted_internal_anchor_href_with_query_string(self):
        cleaned = clean('<a href="/articles/abc/?page=2">Page 2</a>')

        self.assertIn('href="/articles/abc/?page=2"', cleaned)
        self.assertIn(">Page 2</a>", cleaned)

    def test_keeps_allowlisted_internal_anchor_href_with_fragment(self):
        cleaned = clean('<a href="/articles/abc/#section-1">Section</a>')

        self.assertIn('href="/articles/abc/#section-1"', cleaned)
        self.assertIn(">Section</a>", cleaned)

    def test_removes_unallowlisted_internal_anchor_href(self):
        cleaned = clean('<a href="/admin/">Admin link</a>')

        self.assertIn(">Admin link</a>", cleaned)
        self.assertNotIn('href="/admin/"', cleaned)

    def test_removes_logout_internal_anchor_href(self):
        cleaned = clean('<a href="/logout/">Logout link</a>')

        self.assertIn(">Logout link</a>", cleaned)
        self.assertNotIn('href="/logout/"', cleaned)

    def test_removes_accounts_internal_anchor_href(self):
        cleaned = clean('<a href="/accounts/password-change/">Password</a>')

        self.assertIn(">Password</a>", cleaned)
        self.assertNotIn('href="/accounts/password-change/"', cleaned)

    def test_removes_root_internal_anchor_href(self):
        cleaned = clean('<a href="/">Home</a>')

        self.assertIn(">Home</a>", cleaned)
        self.assertNotIn('href="/"', cleaned)

    def test_removes_relative_anchor_href_without_leading_slash(self):
        cleaned = clean('<a href="articles/abc/">Relative link</a>')

        self.assertIn(">Relative link</a>", cleaned)
        self.assertNotIn('href="articles/abc/"', cleaned)

    def test_removes_fragment_only_anchor_href(self):
        cleaned = clean('<a href="#section-1">Section</a>')

        self.assertIn(">Section</a>", cleaned)
        self.assertNotIn("href=", cleaned)

    def test_removes_query_only_anchor_href(self):
        cleaned = clean('<a href="?page=2">Page 2</a>')

        self.assertIn(">Page 2</a>", cleaned)
        self.assertNotIn('href="?page=2"', cleaned)

    def test_removes_empty_anchor_href(self):
        cleaned = clean('<a href="">Empty</a>')

        self.assertIn(">Empty</a>", cleaned)
        self.assertNotIn("href=", cleaned)

    def test_removes_anchor_href_with_newline(self):
        cleaned = clean('<a href="https://test.com/\npath">Bad link</a>')

        self.assertIn(">Bad link</a>", cleaned)
        self.assertNotIn("href=", cleaned)

    def test_removes_external_anchor_href_with_username(self):
        cleaned = clean('<a href="https://user@test.com/path">Bad link</a>')

        self.assertIn(">Bad link</a>", cleaned)
        self.assertNotIn("href=", cleaned)

    def test_removes_external_anchor_href_with_password(self):
        cleaned = clean('<a href="https://user:pass@test.com/path">Bad link</a>')

        self.assertIn(">Bad link</a>", cleaned)
        self.assertNotIn("href=", cleaned)

    def test_removes_internal_anchor_href_with_path_traversal(self):
        cleaned = clean('<a href="/articles/../admin/">Bad internal link</a>')

        self.assertIn(">Bad internal link</a>", cleaned)
        self.assertNotIn('href="/articles/../admin/"', cleaned)

    def test_removes_internal_anchor_href_with_encoded_path_traversal(self):
        cleaned = clean('<a href="/articles/%2e%2e/admin/">Bad internal link</a>')

        self.assertIn(">Bad internal link</a>", cleaned)
        self.assertNotIn('href="/articles/%2e%2e/admin/"', cleaned)

    def test_removes_internal_anchor_href_with_encoded_null_byte(self):
        cleaned = clean('<a href="/articles/%00abc/">Bad internal link</a>')

        self.assertIn(">Bad internal link</a>", cleaned)
        self.assertNotIn("href=", cleaned)

    def test_removes_protocol_relative_anchor_href(self):
        cleaned = clean('<a href="//evil.abc.com/path">Protocol-relative</a>')

        self.assertIn(">Protocol-relative</a>", cleaned)
        self.assertNotIn('href="//evil.abc.com/path"', cleaned)

    def test_removes_javascript_href(self):
        cleaned = clean('<a href="javascript:alert(1)">Bad link</a>')

        self.assertIn(">Bad link</a>", cleaned)
        self.assertNotIn("javascript:", cleaned)
        self.assertNotIn('href="', cleaned)

    def test_removes_mailto_href_by_default(self):
        cleaned = clean('<a href="mailto:test@test.com">Email</a>')

        self.assertIn(">Email</a>", cleaned)
        self.assertNotIn('href="mailto:test@test.com"', cleaned)

    @override_settings(ARTICLES_ALLOWED_ARTICLE_CONTENT_URL_SCHEMES={"mailto"})
    def test_keeps_mailto_anchor_href_when_allowed_by_setting(self):
        cleaned = clean('<a href="mailto:test@test.com">Email</a>')

        self.assertIn('href="mailto:test@test.com"', cleaned)
        self.assertIn(">Email</a>", cleaned)

    @override_settings(
        ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=("test.com",),
    )
    def test_keeps_allowed_absolute_internal_article_link(self):
        cleaned = clean('<a href="https://test.com/articles/abc/">Article</a>')

        self.assertIn('href="https://test.com/articles/abc/"', cleaned)
        self.assertIn(">Article</a>", cleaned)

    @override_settings(
        ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=("test.com",),
    )
    def test_keeps_allowed_absolute_internal_article_link_with_query_and_fragment(self):
        cleaned = clean(
            '<a href="https://test.com/articles/abc/?page=2#section">Article</a>'
        )

        self.assertIn('href="https://test.com/articles/abc/?page=2#section"', cleaned)
        self.assertIn(">Article</a>", cleaned)

    @override_settings(
        ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=("test.com",),
    )
    def test_removes_absolute_internal_link_to_unallowed_path(self):
        cleaned = clean('<a href="https://test.com/admin/">Admin</a>')

        self.assertIn(">Admin</a>", cleaned)
        self.assertNotIn("href=", cleaned)

    @override_settings(
        ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=("test.com",),
    )
    def test_removes_absolute_internal_link_with_path_traversal(self):
        cleaned = clean('<a href="https://test.com/articles/%2e%2e/admin/">Bad</a>')

        self.assertIn(">Bad</a>", cleaned)
        self.assertNotIn("href=", cleaned)

    @override_settings(ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=("test.com",))
    def test_treats_external_link_to_unconfigured_host_as_external_link(self):
        cleaned = clean('<a href="https://other.test.com/admin/">External</a>')

        self.assertIn('href="https://other.test.com/admin/"', cleaned)
        self.assertIn(">External</a>", cleaned)

    @override_settings(ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=("test.com:443",))
    def test_rejects_internal_link_host_with_port(self):
        with self.assertRaises(ImproperlyConfigured):
            clean('<a href="https://test.com/articles/abc/">Article</a>')

    @override_settings(
        ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=("https://test.com",)
    )
    def test_rejects_internal_link_host_with_scheme(self):
        with self.assertRaises(ImproperlyConfigured):
            clean('<a href="https://test.com/articles/abc/">Article</a>')

    @override_settings(ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=("test.com/path",))
    def test_rejects_internal_link_host_with_path(self):
        with self.assertRaises(ImproperlyConfigured):
            clean('<a href="https://test.com/articles/abc/">Article</a>')

    @override_settings(ARTICLES_ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS=(123,))
    def test_rejects_non_string_internal_link_host(self):
        with self.assertRaises(ImproperlyConfigured):
            clean('<a href="https://test.com/articles/abc/">Article</a>')

    def test_removes_id_attributes(self):
        cleaned = clean('<h2 id="section-1">Heading</h2><p id="x">Paragraph</p>')

        self.assertIn("<h2>Heading</h2>", cleaned)
        self.assertIn("<p>Paragraph</p>", cleaned)
        self.assertNotIn("id=", cleaned)

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
        html = '<img src="https://evil.abc.com/articles/uploads/1/2/test.jpg" alt="x">'

        cleaned = clean(html)

        self.assertNotIn("https://evil.abc.com", cleaned)
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
