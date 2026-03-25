import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional, Sequence, TypedDict

from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.template.loader import render_to_string


logger = logging.getLogger(__name__)


class EmailConfigDict(TypedDict, total=False):
    """A dictionary representation of the EmailConfig class."""

    recipients: Sequence[str]
    subject: Optional[str]
    subject_template: Optional[str]
    text_content: Optional[str]
    text_template: Optional[str]
    html_content: Optional[str]
    html_template: Optional[str]
    context: Optional[dict]
    from_email: Optional[str]
    fail_silently: bool


@dataclass
class EmailConfig:  # pylint: disable=too-many-instance-attributes
    """A container for email configuration. You can't provide both
    direct text value and a template at the same time for any of the
    following: subject, text, html.
    """

    recipients: Sequence[str]
    subject: Optional[str] = None
    subject_template: Optional[str] = None
    text_content: Optional[str] = None
    text_template: Optional[str] = None
    html_content: Optional[str] = None
    html_template: Optional[str] = None
    context: Optional[dict] = None
    from_email: Optional[str] = None
    fail_silently: bool = False

    def __post_init__(self) -> None:
        if self.context is not None and not isinstance(self.context, dict):
            raise TypeError("context must be a dictionary")

        self._validate_email_addresses()
        self._validate_mutual_exclusive(
            "subject", self.subject, self.subject_template, field_is_optional=True
        )
        self._validate_mutual_exclusive(
            "text", self.text_content, self.text_template, field_is_optional=False
        )
        self._validate_mutual_exclusive(
            "html", self.html_content, self.html_template, field_is_optional=True
        )

    def __json__(self) -> dict[str, Any]:
        """Makes the class JSON serializable."""
        return asdict(self)

    @staticmethod
    def from_dict(data: EmailConfigDict) -> "EmailConfig":
        return EmailConfig(**data)

    def _validate_email_addresses(self) -> None:
        if isinstance(self.recipients, str):
            raise TypeError(
                "recipients must be a sequence of email strings, not a string"
            )

        if not self.recipients:
            raise ValueError("recipients list cannot be empty")

        for email in self.recipients:
            try:
                validate_email(email)
            except ValidationError as exc:
                raise ValueError(f"invalid email address: {email}") from exc

    def _validate_mutual_exclusive(
        self,
        label: str,
        content: Optional[str],
        template: Optional[str],
        *,
        field_is_optional: bool,
    ) -> None:
        if content and template:
            raise ValueError(f"you can't provide both {label} content and template.")
        if not field_is_optional and not content and not template:
            raise ValueError(f"you must provide either {label} content or template.")


def send_email(config: EmailConfig) -> None:
    """Sends a single transactional email based on EmailConfig."""
    try:
        msg = build_email_message(config)
        sent_count = msg.send()
        if sent_count != 1:
            raise RuntimeError("email was not accepted by the backend")
    except Exception:  # pylint: disable=W0718
        masked_recipients = [mask_email(email) for email in config.recipients]
        logger.exception("Failed to send email to %s.", masked_recipients)
        if not config.fail_silently:
            raise


def build_email_message(config: EmailConfig) -> EmailMultiAlternatives:
    """Builds a single EmailMultiAlternatives from EmailConfig."""
    subject = ""
    if config.subject or config.subject_template:
        subject = render_subject(
            config.subject, config.subject_template, config.context
        )

    text_content = render_content(
        config.text_content, config.text_template, config.context
    )

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=config.from_email,
        to=list(config.recipients),
    )

    html_content = None
    if config.html_content or config.html_template:
        html_content = render_content(
            config.html_content, config.html_template, config.context
        )
    if html_content:
        email_message.attach_alternative(html_content, "text/html")

    return email_message


def render_content(
    content: Optional[str] = None,
    template: Optional[str] = None,
    context: Optional[dict] = None,
) -> str:
    """Returns either the content or the rendered template."""
    if content is not None and template is not None:
        raise ValueError("you can't provide both content and template")
    if content is None and template is None:
        raise ValueError("either content or template must be provided")
    if content is not None:
        return content
    return render_to_string(template, context or {}).strip()


def render_subject(
    content: Optional[str] = None,
    template: Optional[str] = None,
    context: Optional[dict] = None,
) -> str:
    rendered = render_content(content, template, context)
    return " ".join(rendered.splitlines()).strip()


def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    name, domain = email.split("@", 1)
    visible = name[:2] if len(name) >= 2 else name[:1]
    return f"{visible}***@{domain}"
