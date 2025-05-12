from unittest.mock import patch

from django.core import mail
from django.test import TestCase

from core.services.email import EmailConfig, mask_email, render_content, send_email


class TestEmailConfig(TestCase):
    def test_valid_config_with_direct_content(self):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test Subject",
            text_content="Test Content",
        )
        self.assertEqual(config.recipients, ["test@test.com"])
        self.assertEqual(config.subject, "Test Subject")

    @patch("core.services.email.get_template", return_value="Test Content")
    def test_valid_config_with_templates(self, mock_get_template):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject_template="email/subject.txt",
            text_template="email/content.txt",
        )
        self.assertEqual(config.subject_template, "email/subject.txt")

    def test_invalid_recipients(self):
        with self.assertRaises(ValueError):
            EmailConfig(
                recipients=["invalid-email"], subject="Test", text_content="Test"
            )

    def test_empty_recipients(self):
        with self.assertRaises(ValueError):
            EmailConfig(recipients=[], subject="Test", text_content="Test")

    def test_invalid_context(self):
        with self.assertRaises(TypeError):
            EmailConfig(
                recipients=["test@test.com"],
                subject="Test",
                text_content="Test",
                context="invalid",
            )

    def test_subject_optional(self):
        config = EmailConfig(
            recipients=["test@test.com"], text_content="Test", html_content="Test"
        )
        self.assertIsNone(config.subject)
        self.assertIsNone(config.subject_template)

    def test_subject_mutual_exclusive(self):
        with self.assertRaises(ValueError):
            EmailConfig(
                recipients=["test@test.com"],
                subject="Test",
                subject_template="template.txt",
                text_content="Test",
                html_content="<p>Test</p>",
            )

    def test_text_required(self):
        with self.assertRaises(ValueError):
            EmailConfig(
                recipients=["test@test.com"],
                subject="Test",
                html_content="<p>Test</p>",
            )

    def test_text_mutual_exclusive(self):
        with self.assertRaises(ValueError):
            EmailConfig(
                recipients=["test@test.com"],
                subject="Test",
                text_content="Test",
                text_template="template.txt",
                html_content="<p>Test</p>",
            )

    def test_html_content_optional(self):
        config = EmailConfig(
            recipients=["test@test.com"], subject="Test", text_content="Test"
        )
        self.assertIsNone(config.html_content)
        self.assertIsNone(config.html_template)

    def test_html_content_mutual_exclusive(self):
        with self.assertRaises(ValueError):
            EmailConfig(
                recipients=["test@test.com"],
                subject="Test",
                text_content="Test",
                html_content="<p>Test</p>",
                html_template="email/content.html",
            )

    def test_nonexistent_subject_template(self):
        with self.assertRaises(ValueError) as context:
            EmailConfig(
                recipients=["test@test.com"],
                subject_template="nonexistent.txt",
                text_content="Test",
            )
        self.assertEqual(
            str(context.exception), "Subject template does not exist: nonexistent.txt"
        )

    def test_nonexistent_text_template(self):
        with self.assertRaises(ValueError) as context:
            EmailConfig(
                recipients=["test@test.com"],
                subject="Test",
                text_template="nonexistent.txt",
            )
        self.assertEqual(
            str(context.exception), "Text template does not exist: nonexistent.txt"
        )

    def test_nonexistent_html_template(self):
        with self.assertRaises(ValueError) as context:
            EmailConfig(
                recipients=["test@test.com"],
                subject="Test",
                text_content="Test",
                html_template="nonexistent.html",
            )
        self.assertEqual(
            str(context.exception), "Html template does not exist: nonexistent.html"
        )


class TestSendEmail(TestCase):
    def setUp(self):
        self.config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test Subject",
            text_content="Test Content",
        )

    def test_send_email_success(self):
        send_email(self.config)
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertEqual(sent_mail.subject, "Test Subject")
        self.assertEqual(sent_mail.body, "Test Content")
        self.assertEqual(sent_mail.to, ["test@test.com"])

    def test_send_email_with_html(self):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test",
            text_content="Test",
            html_content="<p>Test HTML</p>",
        )
        send_email(config)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].alternatives[0][0], "<p>Test HTML</p>")

    @patch("core.services.email.render_content", side_effect=ValueError)
    def test_send_email_fail_silently(self, mock_render):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test",
            text_content="Test",
            fail_silently=True,
        )
        with self.assertLogs("default_logger", level="ERROR"):
            send_email(config)

    @patch("core.services.email.render_content", side_effect=ValueError("Test"))
    def test_send_email_fail_loudly(self, mock_render):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test",
            text_content="Test",
            fail_silently=False,
        )
        with (
            self.assertRaises(ValueError) as context,
            self.assertLogs("default_logger", level="ERROR"),
        ):
            send_email(config)
        self.assertEqual(str(context.exception), "Test")


class TestRenderContent(TestCase):
    def test_direct_content(self):
        result = render_content(content="Test Content")
        self.assertEqual(result, "Test Content")

    @patch("core.services.email.render_to_string", return_value="Test Content")
    def test_template_content(self, mock_render):
        result = render_content(template="test.html", context={"a": "A"})
        mock_render.assert_called_once_with("test.html", {"a": "A"})
        self.assertEqual(result, "Test Content")

    def test_neither_content_nor_template(self):
        with self.assertRaises(ValueError):
            render_content()

    def test_both_content_and_template(self):
        with self.assertRaises(ValueError):
            render_content(content="Test", template="test.txt")


class TestMaskEmail(TestCase):
    def test_mask_longer_local_part(self):
        result = mask_email("user@test.com")
        self.assertEqual(result, "us***@test.com")

    def test_mask_short_local_part(self):
        result = mask_email("a@test.com")
        self.assertEqual(result, "a***@test.com")
