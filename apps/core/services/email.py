import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional, Sequence, TypedDict

from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.template import TemplateDoesNotExist
from django.template.loader import get_template, render_to_string


logger = logging.getLogger("default_logger")


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
            raise TypeError("Context must be a dictionary")
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
        self._validate_template_exists(self.subject_template, "subject")
        self._validate_template_exists(self.text_template, "text")
        self._validate_template_exists(self.html_template, "html")

    def __json__(self) -> dict[str, Any]:
        """Makes the class JSON serializable."""
        return asdict(self)

    @staticmethod
    def from_dict(data: EmailConfigDict) -> "EmailConfig":
        return EmailConfig(**data)

    def _validate_email_addresses(self) -> None:
        if not self.recipients:
            raise ValueError("Recipients list cannot be empty")
        for email in self.recipients:
            try:
                validate_email(email)
            except ValidationError as exc:
                raise ValueError(f"Invalid email address: {email}") from exc

    def _validate_mutual_exclusive(
        self,
        label: str,
        content: Optional[str],
        template: Optional[str],
        *,
        field_is_optional: bool,
    ) -> None:
        if content and template:
            raise ValueError(f"You can't provide both {label} content and template.")
        if not field_is_optional and not content and not template:
            raise ValueError(f"You must provide either {label} content or template.")

    def _validate_template_exists(self, template: Optional[str], label: str) -> None:
        if template:
            try:
                get_template(template)
            except TemplateDoesNotExist as exc:
                raise ValueError(
                    f"{label.title()} template does not exist: {template}"
                ) from exc


def send_email(config: EmailConfig) -> None:
    """Sends an email based on the given EmailConfig, handling subject,
    plain text, and optional HTML rendering."""
    try:
        subject = ""
        if config.subject or config.subject_template:
            subject = render_content(
                config.subject, config.subject_template, config.context
            )

        text_content = render_content(
            config.text_content, config.text_template, config.context
        )
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=config.from_email,
            to=config.recipients,
        )

        html_content = None
        if config.html_content or config.html_template:
            html_content = render_content(
                config.html_content, config.html_template, config.context
            )
        if html_content:
            email.attach_alternative(html_content, "text/html")

        email.send(fail_silently=config.fail_silently)
    except Exception:  # pylint: disable=broad-exception-caught
        masked_recipients = [mask_email(email) for email in config.recipients]
        logger.exception("Failed to send email to %s.", masked_recipients)
        if not config.fail_silently:
            raise


def render_content(
    content: Optional[str] = None,
    template: Optional[str] = None,
    context: Optional[dict] = None,
) -> str:
    """Returns either the content or the rendered template."""
    if content is not None and template is not None:
        raise ValueError("You can't provide both content and template.")
    if content is None and template is None:
        raise ValueError("Either content or template must be provided.")
    if content is not None:
        return content
    return render_to_string(template, context or {}).strip()


def mask_email(email: str) -> str:
    name, domain = email.split("@", 1)
    return f"{name[:2]}***@{domain}"
