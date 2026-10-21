"""OAuth-only provider API transport with conservative POST failure outcomes."""

from __future__ import annotations

import base64
import math
import time
from email.utils import parsedate_to_datetime

import httpx

from cold_mailer.domain.models import Message, Outcome, Sender, SendResult
from cold_mailer.infrastructure.oauth_accounts import OAuthAccounts
from cold_mailer.infrastructure.smtp import compose
from cold_mailer.settings import Settings


def retry_delay(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(value).timestamp() - time.time()
        except ValueError, TypeError, OverflowError:
            return 60.0
    return max(60.0, seconds) if math.isfinite(seconds) else 60.0


class OAuthMailTransport:
    minimum_interval = 5.0

    def __init__(self, settings: Settings, accounts: OAuthAccounts) -> None:
        self.settings, self.accounts = settings, accounts

    def preflight(self) -> None:
        self.settings.require_network()

    def prepare(self, sender: Sender) -> str:
        return self.accounts.access_token(sender)

    def send(self, sender: Sender, credential: str, message: Message) -> SendResult:
        self.preflight()
        sender.validate()
        if (
            not sender.provider
            or not credential
            or message.sender_id != sender.id
            or message.sender_email != sender.email
        ):
            return SendResult(Outcome.FAILED, "authentication_failed")
        mail = compose(sender, message)
        encoded = (
            base64.urlsafe_b64encode(mail.as_bytes()).decode("ascii")
            if sender.provider == "google"
            else base64.b64encode(mail.as_bytes()).decode("ascii")
        )
        url = (
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
            if sender.provider == "google"
            else "https://graph.microsoft.com/v1.0/me/sendMail"
        )
        try:
            with httpx.Client(timeout=self.settings.timeout, follow_redirects=False) as client:
                headers = {"Authorization": "Bearer " + credential}
                if sender.provider == "google":
                    response = client.post(url, headers=headers, json={"raw": encoded})
                else:
                    headers["Content-Type"] = "text/plain"
                    response = client.post(url, headers=headers, content=encoded)
            if sender.provider == "google" and response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and data.get("id"):
                    return SendResult(Outcome.ACCEPTED, "provider_accepted")
                return SendResult(Outcome.UNCERTAIN, "provider_response_incomplete")
            if sender.provider == "microsoft" and response.status_code == 202:
                return SendResult(Outcome.ACCEPTED, "provider_accepted")
            if response.status_code in {401, 403}:
                return SendResult(Outcome.FAILED, "authentication_failed")
            if response.status_code == 429:
                return SendResult(
                    Outcome.RETRYABLE,
                    "provider_rate_limited",
                    retry_delay(response.headers.get("Retry-After", "")),
                )
            if response.status_code >= 500 or 200 <= response.status_code < 300:
                return SendResult(Outcome.UNCERTAIN, "provider_response_uncertain")
            return SendResult(Outcome.FAILED, "provider_rejected")
        except httpx.ConnectTimeout, httpx.ConnectError:
            return SendResult(Outcome.RETRYABLE, "provider_connect_failed")
        except httpx.HTTPError, ValueError:
            return SendResult(Outcome.UNCERTAIN, "provider_connection_interrupted")
