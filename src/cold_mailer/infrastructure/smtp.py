"""SMTP transport with explicit TLS and conservative transmission outcomes."""

from __future__ import annotations

import contextlib
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate

from cold_mailer.domain.models import (
    Message,
    Outcome,
    Sender,
    SendResult,
    address,
    validate_content,
)
from cold_mailer.settings import Settings


@dataclass
class SenderAccount:
    """Read-only legacy-import record; never persisted by the replacement app."""

    id: int | None
    email: str
    smtp_server: str
    port: int
    username: str
    password: str = field(repr=False)


def compose(sender: Sender, message: Message) -> EmailMessage:
    subject, body = validate_content(message.subject, message.body)
    mail = EmailMessage()
    mail["From"] = address(sender.email)
    mail["To"] = address(message.recipient)
    mail["Subject"] = subject
    mail["Date"] = formatdate(localtime=False)
    mail["Message-ID"] = message.message_id
    mail.set_content(body)
    return mail


class SMTPTransport:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def preflight(self) -> None:
        self.settings.require_network()

    def send(self, sender: Sender, password: str, message: Message) -> SendResult:
        self.settings.require_network()
        sender.validate()
        mail = compose(sender, message)
        server: smtplib.SMTP | None = None
        phase = "connect"
        try:
            context = ssl.create_default_context()
            if sender.tls == "tls":
                server = smtplib.SMTP_SSL(
                    sender.host, sender.port, timeout=self.settings.timeout, context=context
                )
            else:
                server = smtplib.SMTP(sender.host, sender.port, timeout=self.settings.timeout)
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            server.login(sender.username, password)
            phase = "data"
            refused = server.send_message(
                mail, from_addr=sender.email, to_addrs=[message.recipient]
            )
            if refused:
                return SendResult(Outcome.FAILED, "recipient_refused")
            return SendResult(Outcome.ACCEPTED, "smtp_accepted")
        except smtplib.SMTPAuthenticationError:
            return SendResult(Outcome.FAILED, "authentication_failed")
        except smtplib.SMTPRecipientsRefused as exc:
            codes = [value[0] for value in exc.recipients.values()]
            return SendResult(
                Outcome.RETRYABLE
                if codes and all(400 <= code < 500 for code in codes)
                else Outcome.FAILED,
                "recipient_refused",
            )
        except smtplib.SMTPResponseException as exc:
            return SendResult(
                Outcome.RETRYABLE if 400 <= exc.smtp_code < 500 else Outcome.FAILED,
                f"smtp_{exc.smtp_code}",
            )
        except ssl.SSLError, smtplib.SMTPNotSupportedError:
            return SendResult(Outcome.FAILED, "tls_or_protocol_error")
        except OSError, smtplib.SMTPException:
            return SendResult(
                Outcome.UNCERTAIN if phase == "data" else Outcome.RETRYABLE,
                "connection_interrupted",
            )
        finally:
            if server is not None:
                with contextlib.suppress(OSError, smtplib.SMTPException):
                    server.quit()
                with contextlib.suppress(OSError):
                    server.close()
