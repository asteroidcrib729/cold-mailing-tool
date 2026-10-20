"""Pure campaign contracts. No Qt, database, or provider imports."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class ValidationError(ValueError):
    """An actionable input or state error, safe for the user interface."""


class Status(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENDING = "sending"
    ACCEPTED = "accepted"
    RETRYABLE = "retryable"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    SUPPRESSED = "suppressed"


class Outcome(StrEnum):
    ACCEPTED = "accepted"
    RETRYABLE = "retryable"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


def identifier() -> str:
    return uuid.uuid4().hex


def address(value: str) -> str:
    value = value.strip()
    if len(value) > 254 or not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", value
    ):
        raise ValidationError("Enter one valid ASCII email address without a display name.")
    local, domain = value.rsplit("@", 1)
    if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in value:
        raise ValidationError("The email address contains an invalid dot or local part.")
    if any(not part or part.startswith("-") or part.endswith("-") for part in domain.split(".")):
        raise ValidationError("The email domain is invalid.")
    return f"{local}@{domain.lower()}"


def header(value: str, label: str = "Subject") -> str:
    value = value.strip()
    if not value or len(value) > 998 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValidationError(
            f"{label} must be nonempty, single-line text (at most 998 characters)."
        )
    return value


def validate_content(subject: str, body: str) -> tuple[str, str]:
    subject = header(subject)
    body = body.strip()
    if not body or len(body) > 100_000 or "\x00" in body:
        raise ValidationError("The body must contain between 1 and 100,000 characters.")
    if any(
        token in (subject + body).lower()
        for token in ("[[ai", "{{", "}}", "generation unavailable")
    ):
        raise ValidationError("Resolve placeholders before saving or approving this message.")
    return subject, body


def fingerprint(sender: str, recipient: str, subject: str, body: str) -> str:
    return hashlib.sha256(
        json.dumps([sender, recipient, subject, body], ensure_ascii=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Sender:
    id: str
    email: str
    host: str
    port: int
    username: str
    tls: str = "starttls"
    daily_limit: int = 50
    interval: float = 30

    def validate(self) -> None:
        address(self.email)
        header(self.username, "Username")
        if not re.fullmatch(r"[A-Za-z0-9.-]+", self.host) or not 1 <= self.port <= 65535:
            raise ValidationError("Enter a valid SMTP hostname and port (1-65535).")
        if self.tls not in {"starttls", "tls"}:
            raise ValidationError("TLS mode must be starttls or tls.")
        if not 1 <= self.daily_limit <= 10_000 or not 0 <= self.interval <= 86400:
            raise ValidationError("Daily limit must be 1-10000 and interval 0-86400 seconds.")


@dataclass(frozen=True)
class Message:
    id: str
    campaign_id: str
    sender_id: str
    recipient: str
    contact: dict[str, str]
    subject: str
    body: str
    status: Status
    revision: int
    approval: str | None
    sender_email: str
    message_id: str
    created_us: int | None = None
    updated_us: int | None = None
    instructions: str = ""


@dataclass(frozen=True)
class SendResult:
    outcome: Outcome
    code: str


@dataclass
class RunSummary:
    generated: int = 0
    accepted: int = 0
    failed: int = 0
    retryable: int = 0
    uncertain: int = 0
    skipped: int = 0
    cancelled: bool = False


@dataclass(frozen=True)
class ImportIssue:
    row: int
    reason: str


@dataclass(frozen=True)
class ImportSource:
    label: str
    sha256: str
    permission_note: str = ""
    reviewed: bool = False

    def validate(self) -> None:
        if (
            not self.label.strip()
            or len(self.label) > 200
            or len(self.permission_note) > 2000
            or not re.fullmatch(r"[0-9a-f]{64}", self.sha256)
        ):
            raise ValidationError(
                "Import source needs a label (200 characters maximum), SHA-256, and permission notes of at most 2,000 characters."
            )


@dataclass
class ImportReport:
    contacts: list[dict[str, str]] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    duplicates: int = 0
    suppressed: int = 0
