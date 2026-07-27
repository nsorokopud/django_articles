from django.template import Context, Template
from django.test import SimpleTestCase

from articles.templatetags.number_tags import compact_count


class TestCompactCount(SimpleTestCase):
    def test_formats_counts_with_compact_units(self):
        cases = (
            (0, "0"),
            (999, "999"),
            (1_000, "1K"),
            (1_200, "1.2K"),
            (12_400, "12.4K"),
            (999_499, "999.5K"),
            (999_500, "999.5K"),
            (1_000_000, "1M"),
            (1_250_000, "1.2M"),
            (12_400_000, "12.4M"),
            (1_000_000_000, "1B"),
        )

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(compact_count(value), expected)

    def test_handles_non_numeric_and_missing_values(self):
        self.assertEqual(compact_count("unknown"), "unknown")
        self.assertEqual(compact_count(None), "")

    def test_filter_is_available_in_templates(self):
        rendered = Template("{% load number_tags %}{{ count|compact_count }}").render(
            Context({"count": 1_200})
        )

        self.assertEqual(rendered, "1.2K")
