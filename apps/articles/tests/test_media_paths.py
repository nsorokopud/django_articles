from django.test import SimpleTestCase, override_settings

from articles.media_paths import (
    _extract_article_media_storage_name,
    extract_article_media_storage_name_for_article,
)


class TestExtractArticleMediaStorageName(SimpleTestCase):
    @override_settings(MEDIA_URL="/media/")
    def test_extracts_local_media_storage_name(self):
        result = _extract_article_media_storage_name(
            "/media/articles/uploads/1/2/img.jpeg"
        )

        self.assertEqual(result, "articles/uploads/1/2/img.jpeg")

    @override_settings(MEDIA_URL="/media/")
    def test_extracts_local_media_storage_name_with_query_string(self):
        result = _extract_article_media_storage_name(
            "/media/articles/uploads/1/2/img.jpeg?v=123"
        )

        self.assertEqual(result, "articles/uploads/1/2/img.jpeg")

    @override_settings(MEDIA_URL="/custom-media/")
    def test_respects_media_url_path(self):
        result = _extract_article_media_storage_name(
            "/custom-media/articles/uploads/1/2/img.jpeg"
        )

        self.assertEqual(result, "articles/uploads/1/2/img.jpeg")

    @override_settings(MEDIA_URL="/media/")
    def test_rejects_path_outside_media_url(self):
        result = _extract_article_media_storage_name(
            "/other/articles/uploads/1/2/img.jpeg"
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/"])
    def test_extracts_allowed_absolute_media_storage_name(self):
        result = _extract_article_media_storage_name(
            "https://bucket.s3.amazonaws.com/articles/uploads/1/2/img.jpeg"
        )

        self.assertEqual(result, "articles/uploads/1/2/img.jpeg")

    @override_settings(
        MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/media/"]
    )
    def test_extracts_allowed_absolute_media_storage_name_with_base_path(self):
        result = _extract_article_media_storage_name(
            "https://bucket.s3.amazonaws.com/media/articles/uploads/1/2/img.jpeg"
        )

        self.assertEqual(result, "articles/uploads/1/2/img.jpeg")

    @override_settings(
        MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/media/"]
    )
    def test_rejects_absolute_url_outside_allowed_base_path(self):
        result = _extract_article_media_storage_name(
            "https://bucket.s3.amazonaws.com/other/articles/uploads/1/2/img.jpeg"
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/"])
    def test_rejects_unallowed_absolute_host(self):
        result = _extract_article_media_storage_name(
            "https://evil.example.com/articles/uploads/1/2/img.jpeg"
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_ALLOWED_ROOT_URLS=["https://bucket.s3.amazonaws.com/"])
    def test_rejects_http_absolute_url(self):
        result = _extract_article_media_storage_name(
            "http://bucket.s3.amazonaws.com/articles/uploads/1/2/img.jpeg"
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_URL="/media/")
    def test_rejects_non_article_upload_path(self):
        result = _extract_article_media_storage_name("/media/other/img.jpeg")

        self.assertIsNone(result)

    @override_settings(MEDIA_URL="/media/")
    def test_rejects_path_traversal(self):
        result = _extract_article_media_storage_name(
            "/media/articles/uploads/1/2/../evil.jpeg"
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_URL="/media/")
    def test_rejects_encoded_path_traversal(self):
        result = _extract_article_media_storage_name(
            "/media/articles/uploads/1/2/%2e%2e/evil.jpeg"
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_URL="/media/")
    def test_rejects_null_byte(self):
        result = _extract_article_media_storage_name(
            "/media/articles/uploads/1/2/a%00.jpeg"
        )

        self.assertIsNone(result)

    def test_rejects_data_blob_and_javascript_urls(self):
        self.assertIsNone(_extract_article_media_storage_name("data:image/png,abc"))
        self.assertIsNone(_extract_article_media_storage_name("blob:http://x"))
        self.assertIsNone(_extract_article_media_storage_name("javascript:alert(1)"))

    def test_rejects_none_and_empty_string(self):
        self.assertIsNone(_extract_article_media_storage_name(None))
        self.assertIsNone(_extract_article_media_storage_name(""))


class TestExtractArticleMediaStorageNameForArticle(SimpleTestCase):
    @override_settings(MEDIA_URL="/media/")
    def test_extracts_storage_name_for_matching_article(self):
        result = extract_article_media_storage_name_for_article(
            "/media/articles/uploads/1/2/img.jpeg", article_id=2, author_id=1
        )

        self.assertEqual(result, "articles/uploads/1/2/img.jpeg")

    @override_settings(MEDIA_URL="/media/")
    def test_returns_none_for_different_article(self):
        result = extract_article_media_storage_name_for_article(
            "/media/articles/uploads/1/3/img.jpeg", article_id=2, author_id=1
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_URL="/media/")
    def test_returns_none_for_different_author(self):
        result = extract_article_media_storage_name_for_article(
            "/media/articles/uploads/9/2/img.jpeg", article_id=2, author_id=1
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_URL="/media/")
    def test_returns_none_when_article_context_missing(self):
        result = extract_article_media_storage_name_for_article(
            "/media/articles/uploads/1/2/img.jpeg", article_id=None, author_id=1
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_URL="/media/")
    def test_returns_none_when_author_context_missing(self):
        result = extract_article_media_storage_name_for_article(
            "/media/articles/uploads/1/2/img.jpeg", article_id=2, author_id=None
        )

        self.assertIsNone(result)

    @override_settings(MEDIA_URL="/media/")
    def test_returns_none_for_invalid_media_src(self):
        result = extract_article_media_storage_name_for_article(
            "/media/articles/uploads/1/2/../evil.jpeg", article_id=2, author_id=1
        )

        self.assertIsNone(result)
