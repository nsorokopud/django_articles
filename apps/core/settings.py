import os
import socket
from smtplib import SMTPAuthenticationError, SMTPException, SMTPServerDisconnected


# Email task settings
EMAIL_TASK_MAX_RETRIES = int(os.getenv("EMAIL_TASK_MAX_RETRIES", "3"))
EMAIL_TASK_BASE_RETRY_DELAY = int(
    os.getenv("EMAIL_TASK_BASE_RETRY_DELAY", "60")
)  # seconds
EMAIL_TASK_EXPONENTIAL_BACKOFF_FACTOR = int(
    os.getenv("EMAIL_TASK_EXPONENTIAL_BACKOFF_FACTOR", "2")
)

# Email error classifications
EMAIL_PERMANENT_ERRORS = (SMTPAuthenticationError,)
EMAIL_TRANSIENT_ERRORS = (
    SMTPServerDisconnected,
    ConnectionError,
    TimeoutError,
    socket.gaierror,
    SMTPException,
)
