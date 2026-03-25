import json
from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, TestCase

from core.services.email import (
    EmailConfig,
    build_email_message,
    mask_email,
    render_content,
    render_subject,
    send_email,
)


class TestEmailConfig(SimpleTestCase):
    def test_valid_config_with_direct_content(self):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test Subject",
            text_content="Test Content",
        )
        self.assertEqual(config.recipients, ["test@test.com"])
        self.assertEqual(config.subject, "Test Subject")

    def test_valid_config_with_templates(self):
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

    def test_recipients_string_is_rejected(self):
        with self.assertRaises(TypeError):
            EmailConfig(
                recipients="test@test.com",
                subject="Test",
                text_content="Test",
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

    def test_from_dict(self):
        config = EmailConfig.from_dict(
            {
                "recipients": ["test@test.com"],
                "subject": "Test Subject",
                "text_content": "Test Content",
            }
        )
        self.assertEqual(config.recipients, ["test@test.com"])
        self.assertEqual(config.subject, "Test Subject")
        self.assertEqual(config.text_content, "Test Content")

    def test_email_config_json_serialization(self):
        cfg = EmailConfig(
            recipients=["user@test.com"],
            subject="Test",
            text_content="Hello world",
            html_content="<p>Hello world</p>",
            context={"foo": "bar"},
            from_email="noreply@test.com",
            fail_silently=True,
        )

        data = cfg.__json__()

        assert isinstance(data, dict)

        assert data["recipients"] == ["user@test.com"]
        assert data["subject"] == "Test"
        assert data["text_content"] == "Hello world"
        assert data["html_content"] == "<p>Hello world</p>"
        assert data["context"] == {"foo": "bar"}
        assert data["from_email"] == "noreply@test.com"
        assert data["fail_silently"] is True

        json.dumps(data)

    def test_email_config_json_roundtrip(self):
        cfg = EmailConfig(recipients=["user@test.com"], subject="s", text_content="b")

        data = cfg.__json__()

        new_cfg = EmailConfig.from_dict(data)

        assert new_cfg.recipients == cfg.recipients
        assert new_cfg.subject == cfg.subject
        assert new_cfg.text_content == cfg.text_content


class TestBuildEmailMessage(SimpleTestCase):
    def test_build_email_message_with_direct_content(self):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test Subject",
            text_content="Test Content",
        )

        msg = build_email_message(config)

        self.assertEqual(msg.subject, "Test Subject")
        self.assertEqual(msg.body, "Test Content")
        self.assertEqual(msg.to, ["test@test.com"])
        self.assertEqual(msg.alternatives, [])

    def test_build_email_message_with_html(self):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test",
            text_content="Test",
            html_content="<p>Test HTML</p>",
        )

        msg = build_email_message(config)

        self.assertEqual(msg.subject, "Test")
        self.assertEqual(msg.body, "Test")
        self.assertEqual(msg.to, ["test@test.com"])
        self.assertEqual(msg.alternatives[0][0], "<p>Test HTML</p>")
        self.assertEqual(msg.alternatives[0][1], "text/html")

    @patch("core.services.email.render_to_string")
    def test_build_email_message_with_templates(self, mock_render_to_string):
        mock_render_to_string.side_effect = [
            "Rendered Subject",
            "Rendered Text",
            "<p>Rendered HTML</p>",
        ]

        config = EmailConfig(
            recipients=["test@test.com"],
            subject_template="email/subject.txt",
            text_template="email/content.txt",
            html_template="email/content.html",
            context={"name": "Test"},
        )

        msg = build_email_message(config)

        self.assertEqual(msg.subject, "Rendered Subject")
        self.assertEqual(msg.body, "Rendered Text")
        self.assertEqual(msg.to, ["test@test.com"])
        self.assertEqual(msg.alternatives[0][0], "<p>Rendered HTML</p>")
        self.assertEqual(msg.alternatives[0][1], "text/html")
        self.assertEqual(mock_render_to_string.call_count, 3)
        mock_render_to_string.assert_any_call("email/subject.txt", {"name": "Test"})
        mock_render_to_string.assert_any_call("email/content.txt", {"name": "Test"})
        mock_render_to_string.assert_any_call("email/content.html", {"name": "Test"})


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
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")

    def test_send_email_empty_subject(self):
        config = EmailConfig(
            recipients=["test@test.com"],
            text_content="Test Content",
        )
        send_email(config)
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertEqual(sent_mail.subject, "")
        self.assertEqual(sent_mail.body, "Test Content")
        self.assertEqual(sent_mail.to, ["test@test.com"])

    @patch("core.services.email.render_content", side_effect=ValueError)
    def test_send_email_fail_silently(self, _mock_render):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test",
            text_content="Test",
            fail_silently=True,
        )
        with self.assertLogs("core.services.email", level="ERROR"):
            send_email(config)

    @patch("core.services.email.render_content", side_effect=ValueError("Test"))
    def test_send_email_fail_loudly(self, _mock_render):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test",
            text_content="Test",
            fail_silently=False,
        )
        with (
            self.assertRaises(ValueError) as context,
            self.assertLogs("core.services.email", level="ERROR"),
        ):
            send_email(config)
        self.assertEqual(str(context.exception), "Test")

    @patch("core.services.email.EmailMultiAlternatives.send", return_value=0)
    def test_send_email_raises_when_backend_accepts_zero_messages(self, _mock_send):
        config = EmailConfig(
            recipients=["test@test.com"],
            subject="Test",
            text_content="Body",
        )
        with (
            self.assertRaises(RuntimeError),
            self.assertLogs("core.services.email", level="ERROR"),
        ):
            send_email(config)


class TestRenderContent(SimpleTestCase):
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


class TestRenderSubject(SimpleTestCase):
    def test_direct_subject(self):
        result = render_subject(content="Test Subject")
        self.assertEqual(result, "Test Subject")

    def test_render_subject_flattens_newlines(self):
        result = render_subject(content="Hello\nWorld\r\nAgain")
        self.assertEqual(result, "Hello World Again")

    @patch("core.services.email.render_to_string", return_value="  Hello\nWorld \n")
    def test_template_subject_is_normalized(self, mock_render):
        result = render_subject(template="email/subject.txt", context={"a": "A"})
        mock_render.assert_called_once_with("email/subject.txt", {"a": "A"})
        self.assertEqual(result, "Hello World")


class TestMaskEmail(SimpleTestCase):
    def test_mask_longer_local_part(self):
        result = mask_email("user@test.com")
        self.assertEqual(result, "us***@test.com")

    def test_mask_short_local_part(self):
        result = mask_email("a@test.com")
        self.assertEqual(result, "a***@test.com")

    def test_mask_invalid_email(self):
        result = mask_email("invalid")
        self.assertEqual(result, "***")
