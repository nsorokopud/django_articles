import socket
from smtplib import SMTPAuthenticationError, SMTPException, SMTPServerDisconnected


EMAIL_PERMANENT_ERRORS = (SMTPAuthenticationError,)

EMAIL_TRANSIENT_ERRORS = (
    SMTPServerDisconnected,
    ConnectionError,
    TimeoutError,
    socket.gaierror,
    SMTPException,
)
